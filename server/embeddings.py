"""Local text embeddings (free, offline after the first download)."""
import hashlib
import logging
import os
import re
import threading

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np  # noqa: E402

log = logging.getLogger("copilot.embeddings")

MODEL_NAME = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
MAX_CHARS = 2000

_model = None
_lock = threading.Lock()
_cache: dict[str, np.ndarray] = {}
_load_failed = False
_TOKEN = re.compile(r"[^\W\d_][\w+#.]*", re.UNICODE)
_FALLBACK_DIM = 256


def _load_unlocked():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("loading embedding model %s (first run downloads it)", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        _model.max_seq_length = 512
        log.info("embedding model ready")
    return _model


def warm_up() -> None:
    """Load the model in the background so the first tool call is not slow."""
    global _load_failed
    try:
        with _lock:
            _load_unlocked()
    except Exception:
        _load_failed = True
        log.exception("could not pre-load the embedding model")


def _fallback_embed(texts: list[str]) -> np.ndarray:
    """Return a small local vector while the optional model is unavailable."""
    rows = []
    for text in texts:
        row = np.zeros(_FALLBACK_DIM, dtype=float)
        for token in _TOKEN.findall(text.lower()):
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % _FALLBACK_DIM
            row[index] += 1.0
        norm = np.linalg.norm(row)
        rows.append(row / norm if norm else row)
    return np.vstack(rows)


def embed(texts: list[str]) -> np.ndarray:
    """Return one normalized vector per text (rows). Results are cached."""
    global _load_failed
    texts = [t[:MAX_CHARS] for t in texts]
    keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
    todo: dict[str, str] = {k: t for k, t in zip(keys, texts) if k not in _cache}
    if todo:
        use_fallback = _model is None or _load_failed
        if _model is not None:
            try:
                with _lock:
                    vecs = _model.encode(
                        ["query: " + t for t in todo.values()],
                        normalize_embeddings=True,
                        batch_size=16,
                        show_progress_bar=False,
                    )
                for k, vec in zip(todo.keys(), vecs):
                    _cache[k] = np.asarray(vec, dtype=float)
            except Exception:
                _load_failed = True
                use_fallback = True
                log.exception("embedding failed; using local lexical matching")
        if use_fallback:
            log.warning("embedding model is not ready; using local lexical matching")
            return _fallback_embed(texts)
    return np.vstack([_cache[k] for k in keys])