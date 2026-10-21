"""Input validation. Every tool input passes through here before use."""
import ipaddress
import re
from datetime import datetime
from urllib.parse import urlparse

from server.errors import InputError

CATEGORIES = {"scholarship", "internship", "job", "fellowship"}
STATUSES = {"saved", "applied", "interview", "accepted", "rejected"}

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str, field: str, max_len: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    value = _CONTROL_CHARS.sub("", value).strip()
    if required and not value:
        raise ValueError(f"{field} is required and cannot be empty.")
    if len(value) > max_len:
        raise ValueError(f"{field} is too long (max {max_len} characters).")
    return value


def validate_category(value: str) -> str:
    value = clean_text(value, "category", 30).lower()
    if value not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(sorted(CATEGORIES))}.")
    return value


def validate_status(value: str) -> str:
    value = clean_text(value, "status", 30).lower()
    if value not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(STATUSES))}.")
    return value


def validate_deadline(value: str) -> str:
    """Empty is allowed. Otherwise the format must be YYYY-MM-DD."""
    value = clean_text(value, "deadline", 10, required=False)
    if not value:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("deadline must be a real date in YYYY-MM-DD format, e.g. 2026-12-31.")
    return value


def validate_url(value: str, required: bool = False) -> str:
    """Only http/https. Blocks localhost and private network addresses."""
    value = clean_text(value, "url", 500, required=required)
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must start with http:// or https://.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url has no host name.")
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("url points to a local address, which is not allowed.")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("url points to a private network address, which is not allowed.")
    except ValueError as e:
        if "not allowed" in str(e):
            raise
    return value


def validate_limit(value: int, maximum: int = 50) -> int:
    if not isinstance(value, int) or value < 1 or value > maximum:
        raise ValueError(f"limit must be a whole number from 1 to {maximum}.")
    return value
def validate_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InputError(
            "opportunity_id must be a whole number of 1 or more. "
            "Use list_saved_opportunities to see the ids."
        )
    return value


def validate_days(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 90:
        raise InputError("days must be a whole number from 1 to 90.")
    return value