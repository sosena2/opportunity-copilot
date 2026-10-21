import pytest

from server import cv, github


def test_cv_reads_a_normal_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DIR", str(tmp_path))
    (tmp_path / "me.md").write_text("Python developer", encoding="utf-8")
    assert cv.read_cv_text("me.md") == ("me.md", "Python developer")


@pytest.mark.parametrize(
    "bad", ["../secret.txt", "..\\x.txt", "/etc/passwd", "a/b.md", "C:\\x.txt", ".env", "cv.exe"]
)
def test_cv_blocks_paths_and_bad_names(tmp_path, monkeypatch, bad):
    monkeypatch.setenv("CV_DIR", str(tmp_path))
    (tmp_path / "me.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        cv.read_cv_text(bad)


def test_cv_default_prefers_real_file_over_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DIR", str(tmp_path))
    (tmp_path / "sample_cv.md").write_text("fake", encoding="utf-8")
    (tmp_path / "mine.md").write_text("real", encoding="utf-8")
    assert cv.read_cv_text("")[0] == "mine.md"


def test_cv_empty_folder_gives_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        cv.read_cv_text("")


@pytest.mark.parametrize("name", ["octocat", "a-b", "User123"])
def test_github_valid_usernames(name):
    assert github.validate_username(name) == name


@pytest.mark.parametrize("name", ["", "-bad", "a b", "a/b", "x" * 40, "../x"])
def test_github_invalid_usernames(name):
    with pytest.raises(ValueError):
        github.validate_username(name)


def test_github_summary_ignores_forks_and_counts_languages():
    profile = {"login": "demo", "name": "Demo", "bio": "hi", "public_repos": 3, "followers": 2}
    repos = [
        {"name": "a", "language": "Python", "stargazers_count": 5, "fork": False,
         "pushed_at": "2026-09-01T00:00:00Z", "description": "first"},
        {"name": "b", "language": "Python", "stargazers_count": 1, "fork": False,
         "pushed_at": "2026-10-01T00:00:00Z", "description": None},
        {"name": "c", "language": "Go", "stargazers_count": 99, "fork": True,
         "pushed_at": "2026-10-20T00:00:00Z", "description": "forked"},
    ]
    out = github.build_summary(profile, repos)
    assert "Python (2)" in out
    assert "Go" not in out
    assert "2026-10-01" in out