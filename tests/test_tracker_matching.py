import datetime as dt

import numpy as np
import pytest

from server import db, embeddings, matching


@pytest.fixture
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()


def add(title, deadline="", category="job"):
    return db.insert_opportunity(title, "Org", category, deadline, "", "")


def test_set_status_and_counts(tmpdb):
    a = add("A")
    add("B")
    assert db.set_status(a, "applied") == "saved"
    counts = db.status_counts()
    assert counts["applied"] == 1 and counts["saved"] == 1


def test_same_status_and_unknown_id_are_errors(tmpdb):
    a = add("A")
    with pytest.raises(ValueError):
        db.set_status(a, "saved")
    with pytest.raises(ValueError):
        db.set_status(999, "applied")


def test_upcoming_only_saved_and_in_window(tmpdb):
    today = dt.date.today()
    soon = (today + dt.timedelta(days=3)).isoformat()
    far = (today + dt.timedelta(days=60)).isoformat()
    a = add("Soon", soon)
    add("Far", far)
    b = add("Applied soon", soon)
    db.set_status(b, "applied")
    titles = [r["title"] for r in db.upcoming(14)]
    assert titles == ["Soon"] and a


def test_keywords_and_shared():
    assert "python" in matching.keywords("Python developer, with SQL")
    assert "the" not in matching.keywords("the python")
    assert matching.shared_keywords("Python and React", "React internship") == ["react"]


def test_cv_lines_skip_short_and_strip_bullets():
    text = "# Skills\n- Python, PyTorch, SQL and Git\nshort\n"
    assert matching.cv_lines(text) == ["Python, PyTorch, SQL and Git"]


def test_rank_orders_by_similarity(monkeypatch):
    vocab = ["python", "ml", "react", "law"]

    def fake_embed(texts):
        rows = []
        for t in texts:
            vec = np.array([1.0 if w in t.lower() else 0.0 for w in vocab])
            norm = np.linalg.norm(vec)
            rows.append(vec / norm if norm else vec)
        return np.vstack(rows)

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    opps = [
        {"title": "Law clerk", "organization": "X", "category": "job", "description": "law"},
        {"title": "ML intern", "organization": "Y", "category": "internship", "description": "python ml"},
    ]
    ranked = matching.rank("I know python and ml", opps)
    assert ranked[0][0]["title"] == "ML intern"