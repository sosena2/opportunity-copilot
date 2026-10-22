import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

from client import agent
from client import llm as llm_module
from client.llm import GeminiLLM, LLMError, ToolCall, _clean_schema

TOOL = SimpleNamespace(
    name="save_opportunity",
    description="Save one opportunity.",
    input_schema={
        "type": "object",
        "title": "x",
        "properties": {"title": {"type": "string", "title": "Title"}},
        "required": ["title"],
    },
)


class Busy(Exception):
    code = 503


class FakeModels:
    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        step = self.plan.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def text_response(text):
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def make_llm(plan, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "m1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "m2")
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: None)
    client = SimpleNamespace(models=FakeModels(plan))
    return GeminiLLM("system", [TOOL], client=client), client


def test_clean_schema_keeps_only_simple_keywords():
    schema = {
        "title": "X",
        "type": "object",
        "properties": {"a": {"type": "string", "title": "A", "default": ""}},
        "required": ["a"],
        "additionalProperties": False,
    }
    assert _clean_schema(schema) == {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }


def test_falls_back_to_next_model_when_busy(monkeypatch):
    llm, client = make_llm([Busy("high demand"), Busy("high demand"), text_response("hi")], monkeypatch)
    llm.add_user("hello")
    assert llm.generate().text == "hi"
    assert client.models.calls == ["m1", "m1", "m2"]


def test_all_models_busy_gives_clear_error(monkeypatch):
    llm, _ = make_llm([Busy("x")] * 4, monkeypatch)
    llm.add_user("hello")
    with pytest.raises(LLMError):
        llm.generate()


def test_empty_answer_is_an_error(monkeypatch):
    empty = types.GenerateContentResponse(candidates=[])
    llm, _ = make_llm([empty], monkeypatch)
    llm.add_user("hello")
    with pytest.raises(LLMError):
        llm.generate()


class FakeSession:
    def __init__(self, text="ok", is_error=False):
        self.calls = []
        self.text, self.is_error = text, is_error

    async def call_tool(self, name, args):
        self.calls.append(name)
        block = SimpleNamespace(type="text", text=self.text)
        return SimpleNamespace(content=[block], is_error=self.is_error)


def run(coro):
    return asyncio.run(coro)


def test_write_tool_needs_approval_and_declined_is_not_run():
    session = FakeSession()

    async def no(name, args):
        return False

    name, text, is_error = run(
        agent.execute_tool(session, ToolCall("save_opportunity", {}), {"save_opportunity"}, no)
    )
    assert session.calls == [] and "declined" in text and not is_error


def test_approved_write_tool_runs():
    session = FakeSession("Saved #1")

    async def yes(name, args):
        return True

    _, text, _ = run(agent.execute_tool(session, ToolCall("save_opportunity", {}), {"save_opportunity"}, yes))
    assert session.calls == ["save_opportunity"] and text == "Saved #1"


def test_read_tool_runs_without_approval():
    session = FakeSession("results")
    _, text, _ = run(agent.execute_tool(session, ToolCall("read_cv", {}), {"read_cv"}))
    assert text == "results"


def test_unknown_tool_is_rejected():
    session = FakeSession()
    _, text, is_error = run(agent.execute_tool(session, ToolCall("rm_rf", {}), {"read_cv"}))
    assert is_error and session.calls == []


def test_error_result_is_passed_back_and_long_output_is_cut():
    session = FakeSession("x" * 10000, is_error=True)
    _, text, is_error = run(agent.execute_tool(session, ToolCall("read_cv", {}), {"read_cv"}))
    assert is_error and len(text) < 6100 and text.endswith("[truncated]")


def test_tool_error_text_is_preserved_for_the_model():
    session = FakeSession(
        "Error executing tool update_status: no saved opportunity with id 999.",
        is_error=True,
    )
    _, text, is_error = run(
        agent.execute_tool(
            session,
            ToolCall("update_status", {"opportunity_id": 999}),
            {"update_status"},
            approve=lambda name, args: _approved(),
        )
    )
    assert is_error
    assert "no saved opportunity with id 999" in text


async def _approved():
    return True


def test_read_tools_can_run_as_one_model_batch():
    session = FakeSession("results")
    calls = [ToolCall("read_cv", {}), ToolCall("read_cv", {})]
    results = run(agent.execute_tools(session, calls, {"read_cv"}))
    assert [result[0] for result in results] == ["read_cv", "read_cv"]
    assert session.calls == ["read_cv", "read_cv"]


def test_write_tools_in_a_batch_are_serialized_and_approved():
    session = FakeSession("saved")
    calls = [ToolCall("save_opportunity", {}), ToolCall("update_status", {})]
    approved = []

    async def yes(name, args):
        approved.append(name)
        return True

    results = run(agent.execute_tools(session, calls, {"save_opportunity", "update_status"}, yes))
    assert [result[0] for result in results] == ["save_opportunity", "update_status"]
    assert approved == ["save_opportunity", "update_status"]