"""Matching logic: rank opportunities against a CV and explain why."""
import re

from server import embeddings

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "from", "that", "this",
    "have", "has", "was", "were", "who", "they", "their", "about", "into", "more", "such",
    "can", "all", "any", "not", "but", "per", "via", "new", "work", "working", "team", "role",
    "year", "years", "based", "include", "including", "experience", "ability", "strong",
    "skills", "also", "its", "use", "using", "used", "etc", "other", "than", "then", "them",
}
_TOKEN = re.compile(r"[^\W\d_][\w+#.]*", re.UNICODE)


def opportunity_text(o: dict) -> str:
    return f"{o['title']}. {o['organization']}. {o['category']}. {o['description']}"[:2000]


def keywords(text: str) -> set[str]:
    out = set()
    for token in _TOKEN.findall(text.lower()):
        token = token.rstrip(".")
        if len(token) >= 2 and token not in STOPWORDS:
            out.add(token)
    return out


def shared_keywords(cv_text: str, opp_text: str, limit: int = 8) -> list[str]:
    return sorted(keywords(cv_text) & keywords(opp_text))[:limit]


def cv_lines(cv_text: str, max_lines: int = 60) -> list[str]:
    lines = []
    for line in cv_text.splitlines():
        line = line.strip().lstrip("#-*\u2022 ").strip()
        if len(line) >= 15:
            lines.append(line)
    return lines[:max_lines]


def rank(cv_text: str, opps: list[dict]) -> list[tuple[dict, float]]:
    vecs = embeddings.embed([cv_text] + [opportunity_text(o) for o in opps])
    scores = vecs[1:] @ vecs[0]
    pairs = [(o, float(s)) for o, s in zip(opps, scores)]
    return sorted(pairs, key=lambda p: p[1], reverse=True)


def explain(cv_text: str, opp: dict, top_n: int = 3) -> tuple[float, list[tuple[str, float]], list[str]]:
    opp_text = opportunity_text(opp)
    lines = cv_lines(cv_text)
    vecs = embeddings.embed([opp_text, cv_text] + lines)
    overall = float(vecs[1] @ vecs[0])
    best: list[tuple[str, float]] = []
    if lines:
        sims = vecs[2:] @ vecs[0]
        order = sims.argsort()[::-1][:top_n]
        best = [(lines[i], float(sims[i])) for i in order]
    return overall, best, shared_keywords(cv_text, opp_text)