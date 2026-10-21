"""GitHub profile summary. Public data only. The token (optional) comes from the environment."""
import logging
import os
import re
from collections import Counter

import httpx

from server.errors import InputError
from server.web import _cache_get, _cache_set, wrap_untrusted

log = logging.getLogger("copilot.github")

API = "https://api.github.com"
TIMEOUT = 10.0
_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def validate_username(username: str) -> str:
    if not isinstance(username, str):
        raise InputError("username must be text.")
    username = username.strip()
    if not _USER_RE.match(username):
        raise InputError(
            "That is not a valid GitHub username (letters, numbers and dashes, max 39 characters)."
        )
    return username


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpportunityCopilot/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(client: httpx.Client, path: str, params: dict | None = None):
    r = client.get(f"{API}{path}", params=params)
    if r.status_code == 404:
        raise InputError("GitHub user not found. Check the spelling of the username.")
    if r.status_code in (403, 429):
        raise InputError(
            "GitHub rate limit reached. Wait a few minutes, or add a GITHUB_TOKEN to the .env file."
        )
    if r.status_code >= 400:
        raise InputError(f"GitHub returned HTTP {r.status_code}. Try again later.")
    return r.json()


def build_summary(profile: dict, repos: list[dict]) -> str:
    own = [r for r in repos if not r.get("fork")]
    langs = Counter(r["language"] for r in own if r.get("language"))
    top = sorted(own, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
    recent = max((r.get("pushed_at") or "" for r in own), default="")

    lines = [
        f"GitHub profile: {profile.get('login')}",
        f"Name: {profile.get('name') or 'not set'}",
        f"Bio: {(profile.get('bio') or 'not set')[:300]}",
        f"Public repos: {profile.get('public_repos', 0)} | Followers: {profile.get('followers', 0)}",
        f"Original (non-fork) repos analysed: {len(own)} (up to the 100 most recently updated)",
        "Top languages: " + (", ".join(f"{l} ({n})" for l, n in langs.most_common(5)) or "none"),
        f"Most recent push: {recent[:10] or 'unknown'}",
        "Top repos by stars:",
    ]
    for r in top:
        desc = (r.get("description") or "no description")[:150]
        lines.append(
            f"- {r.get('name')} ({r.get('language') or 'n/a'}, "
            f"{r.get('stargazers_count', 0)} stars): {desc}"
        )
    return "\n".join(lines)


def profile_summary(username: str) -> str:
    username = validate_username(username)
    key = "github:" + username.lower()
    cached = _cache_get(key)
    if cached:
        return cached
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_headers()) as client:
            profile = _get(client, f"/users/{username}")
            repos = _get(client, f"/users/{username}/repos", {"per_page": 100, "sort": "updated"})
    except httpx.TimeoutException:
        raise InputError("GitHub took too long to respond. Try again.")
    except httpx.HTTPError:
        log.warning("network error while contacting GitHub")
        raise InputError("Could not reach GitHub.")

    out = wrap_untrusted(build_summary(profile, repos), f"github.com/{username}")
    _cache_set(key, out)
    return out