"""CV reading, restricted to one folder. Accepts a file NAME only, never a path."""
import logging
import os
import re
from pathlib import Path

from server.errors import InputError

log = logging.getLogger("copilot.cv")

ALLOWED_EXT = {".txt", ".md", ".pdf"}
MAX_FILE_BYTES = 2_000_000
MAX_CHARS = 12_000
MAX_PDF_PAGES = 10
_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}$")


def cv_dir() -> Path:
    return Path(os.environ.get("CV_DIR", "data/cv"))


def list_files() -> list[str]:
    d = cv_dir()
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXT)


def _default_name(names: list[str]) -> str:
    real = [n for n in names if not n.lower().startswith("sample")]
    return (real or names)[0]


def resolve_cv_path(filename: str) -> Path:
    names = list_files()
    if not filename:
        if not names:
            raise InputError("No CV found. Put a .txt, .md or .pdf file in the data/cv folder.")
        filename = _default_name(names)
    if not isinstance(filename, str) or not _NAME_OK.match(filename) or ".." in filename:
        raise InputError(
            "filename may only contain letters, numbers, spaces, dots, dashes and underscores. "
            "Give a file name, not a path."
        )
    if Path(filename).suffix.lower() not in ALLOWED_EXT:
        raise InputError("Only .txt, .md and .pdf files can be read.")
    base = cv_dir().resolve()
    path = (base / filename).resolve()
    if not path.is_relative_to(base):
        raise InputError("That file is outside the CV folder.")
    if not path.is_file():
        raise InputError(f"File not found. Available CV files: {', '.join(names) or 'none'}.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise InputError("That file is too large (max 2 MB).")
    return path


def read_cv_text(filename: str = "") -> tuple[str, str]:
    """Return (file name, text)."""
    path = resolve_cv_path(filename)
    try:
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES])
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        log.exception("could not read CV file")
        raise InputError("Could not read that file. It may be damaged or password protected.")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise InputError(
            "No text found in the file. A scanned PDF has no readable text. "
            "Use a text-based PDF or a .md file."
        )
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...[truncated]"
    return path.name, text