# Opportunity Copilot: MCP server and client

Opportunity Copilot is an AI assistant for students and early-career applicants. It
finds opportunities, compares them with a CV, summarizes public GitHub work, and
tracks applications in a local SQLite database.

The project demonstrates MCP end to end: a Python server exposes typed tools over
stdio or Streamable HTTP, and the custom Python client discovers those tools, passes
their schemas to Gemini, executes Gemini's function calls, and feeds the results
back for a final answer.

## Resources

1. **SQLite** (`data/copilot.db`) stores opportunities and status history.
2. **Public web search and pages** use DuckDuckGo and HTTP(S), with SSRF and prompt
   injection defenses.
3. **GitHub's public API** provides profile and repository summaries.
4. **Local CV files** in `data/cv/` provide matching context.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. `GITHUB_TOKEN` is optional but helps avoid anonymous
GitHub rate limits. Set `MCP_AUTH_TOKEN` to a long random value before using
Streamable HTTP. Never commit `.env` or API keys.

Put a text, Markdown, or text-based PDF CV in `data/cv/`. The checked-in
`sample_cv.md` is safe demo data.

## Run and inspect

The server uses stdio by default and logs to stderr, so stdout remains valid MCP
transport:

```powershell
python -m server.main
```

To use the Streamable HTTP transport, start the server in one terminal:

```powershell
python -m server.main --transport streamable-http --host 127.0.0.1 --port 8000
```

The MCP endpoint is then available at `http://127.0.0.1:8000/mcp` and requires
an Authorization bearer token matching `MCP_AUTH_TOKEN`. The server fails closed
when the token is missing, compares it in constant time, and never logs token
values. Stdio remains local-only and does not use HTTP authentication. For
anything beyond localhost, terminate TLS at a trusted reverse proxy and rotate
the token regularly; do not expose this demo directly over plain HTTP.

In MCP Inspector, configure Streamable HTTP for this URL and add the same bearer
token in its authentication/header field. A missing or invalid token returns 401.
The custom
Gemini client currently starts the local stdio server directly:

```powershell
python -m client.agent "Which saved opportunities should I apply to first?"
```

Use MCP Inspector to inspect either transport:

```powershell
npx @modelcontextprotocol/inspector python -m server.main
```

The agent can execute multiple read-only MCP tools concurrently when Gemini returns
a batch of calls. Write operations such as `save_opportunity` remain serialized and
require explicit approval. This supports workflows such as searching for several
opportunities, reading the strongest candidates, and saving the selected result.

The client asks for explicit approval before every `save_opportunity` or
`update_status` call. A denied write is returned to Gemini as a normal result so it
does not silently retry it.

## Tools

| Tool | Example purpose |
| --- | --- |
| `save_opportunity` | Save a validated scholarship, internship, job, or fellowship |
| `list_saved_opportunities` | Filter and list tracked opportunities |
| `web_search_opportunities` | Find new public opportunities |
| `fetch_page_text` | Read details from a public result |
| `read_cv` | Read a CV file from the restricted CV folder |
| `summarize_github_profile` | Summarize a public GitHub profile |
| `rank_opportunities` | Rank saved items against the CV |
| `explain_match` | Explain a CV/opportunity match |
| `update_status` | Move an item through the application pipeline |
| `pipeline_stats` | Show counts by stage and category |
| `upcoming_deadlines` | List saved deadlines in the next 1–90 days |

Every tool validates inputs. Validation, network, duplicate, and missing-record
failures are returned as MCP errors or error-shaped tool results, allowing Gemini
to explain the problem or recover.

## MCP resource and prompt

The server also exposes:

- Resource `opportunity://tracker`, a read-only text snapshot of saved opportunities
- Prompt `review-opportunities`, which asks an MCP host to summarize the tracker,
  deadlines, and next actions without mutating data

These can be inspected with MCP Inspector after connecting to either stdio or
Streamable HTTP.

Example tool arguments:

```json
{"name": "web_search_opportunities",
 "arguments": {"query": "machine learning internship Africa 2026", "max_results": 3}}
```

```json
{"name": "list_saved_opportunities",
 "arguments": {"status": "saved", "limit": 10}}
```

## Demo: multiple tools and failure recovery

The repeatable demo uses two tracker tools, intentionally makes one invalid tracker
call, and continues with a third tool after the error:

```powershell
python -m client.demo
```

The demo uses the local stdio server and does not need a Gemini key or network
access. The interactive Gemini agent supports the same multi-tool and recovery
pattern for live opportunity searches.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Project layout

- `server/main.py` - MCP server and tool definitions
- `server/db.py`, `server/web.py`, `server/github.py`, `server/cv.py` - resources
- `client/agent.py` - custom MCP + Gemini agent loop and save approval
- `client/llm.py` - Gemini adapter, schema handling, retries, and model fallback
- `tests/` - validation and resource unit tests
