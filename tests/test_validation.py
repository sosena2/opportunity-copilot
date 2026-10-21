import pytest

from server import validation as v


def test_blocks_file_url():
    with pytest.raises(ValueError):
        v.validate_url("file:///etc/passwd")


def test_blocks_localhost_and_private_ip():
    for bad in ["http://localhost/admin", "http://127.0.0.1/", "http://192.168.1.5/"]:
        with pytest.raises(ValueError):
            v.validate_url(bad)


def test_accepts_normal_url():
    assert v.validate_url("https://example.com/apply") == "https://example.com/apply"


def test_bad_category():
    with pytest.raises(ValueError):
        v.validate_category("lottery")


def test_bad_deadline():
    with pytest.raises(ValueError):
        v.validate_deadline("31/12/2026")


def test_too_long_text():
    with pytest.raises(ValueError):
        v.clean_text("x" * 300, "title", 200)