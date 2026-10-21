"""Gemini adapter (free tier).

Keeps the model's own turns exactly as returned (Gemini 3 models need their hidden
"thought signature" sent back with tool calls), retries busy errors, and falls back
to other free models when one is overloaded or out of quota.
"""
import logging
import os
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types

log = logging.getLogger("copilot.llm")


class LLMError(Exception):
    """A problem with the AI model that is safe to show to the user."""


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


def _clean_schema(schema):
    """Reduce an MCP JSON Schema to the simple subset Gemini accepts."""
    if isinstance(schema, list):
        return [_clean_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    if "anyOf" in schema:  # Optional[...] -> the first real type
        options = [o for o in schema["anyOf"] if o.get("type") != "null"]
        if options:
            merged = {**{k: v for k, v in schema.items() if k != "anyOf"}, **options[0]}
            return _clean_schema(merged)
    keep = {"type", "properties", "required", "description", "enum", "items"}
    out = {}
    for key, value in schema.items():
        if key not in keep:
            continue
        if key == "properties":
            out[key] = {name: _clean_schema(sub) for name, sub in value.items()}
        else:
            out[key] = _clean_schema(value)
    return out


def _is_busy(error: Exception) -> bool:
    code = getattr(error, "code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    text = str(error).lower()
    return any(w in text for w in ("unavailable", "high demand", "overloaded", "timed out", "timeout"))


class GeminiLLM:
    def __init__(self, system_prompt: str, mcp_tools: list, client=None):
        primary = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
        fallbacks = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
        self.models = [primary] + [m for m in fallbacks if m != primary]

        if client is None:
            key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not key:
                raise LLMError("GEMINI_API_KEY is empty. Add your key to the .env file.")
            client = genai.Client(api_key=key)
        self.client = client

        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=(t.description or "")[:1500],
                parameters_json_schema=_clean_schema(t.input_schema),
            )
            for t in mcp_tools
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,
        )
        self.history: list[types.Content] = []

    # --- conversation state ---
    def mark(self) -> int:
        return len(self.history)

    def rollback(self, mark: int) -> None:
        del self.history[mark:]

    def reset(self) -> None:
        self.history.clear()

    def add_user(self, text: str) -> None:
        self.history.append(types.Content(role="user", parts=[types.Part(text=text)]))

    def add_tool_results(self, results: list[tuple[str, str, bool]]) -> None:
        """results: (tool name, text, is_error) in the same order as the model's calls."""
        parts = [
            types.Part.from_function_response(
                name=name, response={"error": text} if is_error else {"output": text}
            )
            for name, text, is_error in results
        ]
        self.history.append(types.Content(role="user", parts=parts))

    # --- one model call ---
    def generate(self) -> Turn:
        for model in self.models:
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model, contents=self.history, config=self.config
                    )
                    return self._accept(response)
                except LLMError:
                    raise
                except Exception as e:
                    if not _is_busy(e):
                        raise LLMError(f"The AI model rejected the request: {str(e)[:200]}")
                    log.warning("model %s busy or out of quota (try %d)", model, attempt + 1)
                    time.sleep(2 * (attempt + 1))
            log.warning("switching away from model %s", model)
        raise LLMError("All the free models are busy or out of quota. Wait a few minutes and try again.")

    def _accept(self, response) -> Turn:
        candidate = response.candidates[0] if response.candidates else None
        content = candidate.content if candidate else None
        if content is None or not content.parts:
            raise LLMError("The model returned no answer (it may have been blocked). Try rephrasing.")
        self.history.append(content)
        text = "".join(p.text for p in content.parts if p.text and not p.thought).strip()
        calls = [
            ToolCall(p.function_call.name, dict(p.function_call.args or {}))
            for p in content.parts
            if p.function_call
        ]
        return Turn(text, calls)