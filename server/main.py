"""Opportunity Copilot MCP server (stdio).

IMPORTANT: never print() in this file. stdout carries the MCP messages,
so printing would corrupt them. Log to stderr only.
"""
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from mcp.server import MCPServer  # noqa: E402

from server import db, validation as v  # noqa: E402

log = logging.getLogger("copilot.server")
mcp = MCPServer("opportunity-copilot")
db.init_db()


@mcp.tool()
def save_opportunity(
    title: str,
    organization: str,
    category: str,
    deadline: str = "",
    url: str = "",
    description: str = "",
) -> str:
    """Save one opportunity (scholarship, internship, job or fellowship) to the user's tracker.

    Use this when the user wants to keep an opportunity for later, or after finding
    one worth tracking. Do not use it to search for opportunities.

    Args:
        title: Name of the opportunity, e.g. "Google STEP Internship".
        organization: Who offers it, e.g. "Google".
        category: One of: scholarship, internship, job, fellowship.
        deadline: Application deadline as YYYY-MM-DD. Leave empty if unknown.
        url: Link to the official page (http or https only).
        description: Short notes or requirements (max 2000 characters).
    """
    title = v.clean_text(title, "title", 200)
    organization = v.clean_text(organization, "organization", 200)
    category = v.validate_category(category)
    deadline = v.validate_deadline(deadline)
    url = v.validate_url(url)
    description = v.clean_text(description, "description", 2000, required=False)

    try:
        new_id = db.insert_opportunity(title, organization, category, deadline, url, description)
    except db.DuplicateOpportunityError as exc:
        log.info("opportunity already saved: %s", exc)
        return f"Already saved: {exc}"

    log.info("saved opportunity id=%s", new_id)
    return f"Saved #{new_id}: {title} at {organization} ({category}). Deadline: {deadline or 'not set'}."


@mcp.tool()
def list_saved_opportunities(status: str = "", category: str = "", limit: int = 20) -> str:
    """List opportunities the user has saved, soonest deadline first.

    Use this when the user asks what they have saved, what is in their tracker,
    or wants to review their list. Both filters are optional.

    Args:
        status: Optional filter: saved, applied, interview, accepted or rejected.
        category: Optional filter: scholarship, internship, job or fellowship.
        limit: How many to return, from 1 to 50 (default 20).
    """
    status = v.validate_status(status) if status else ""
    category = v.validate_category(category) if category else ""
    limit = v.validate_limit(limit)

    rows = db.fetch_opportunities(status, category, limit)
    if not rows:
        return "No saved opportunities match. The tracker is empty or the filters are too narrow."

    lines = []
    for r in rows:
        lines.append(
            f"#{r['id']} [{r['status']}] {r['title']} at {r['organization']} "
            f"({r['category']}) | deadline: {r['deadline'] or 'not set'}"
            + (f" | {r['url']}" if r["url"] else "")
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")