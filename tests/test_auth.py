import pytest

from server.auth import BearerAuthMiddleware, configured_token, valid_bearer_header


def test_bearer_header_is_case_insensitive_for_scheme():
    assert valid_bearer_header("bEaReR secret", "secret")


@pytest.mark.parametrize("header", ["", "Basic secret", "Bearer", "Bearer wrong", "Bearer secret extra"])
def test_invalid_bearer_headers_are_rejected(header):
    assert not valid_bearer_header(header, "secret")


def test_configured_token_fails_closed(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="MCP_AUTH_TOKEN"):
        configured_token()


def test_configured_token_is_trimmed(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "  secret  ")
    assert configured_token() == "secret"


def test_middleware_is_available_for_http_app():
    assert BearerAuthMiddleware.__name__ == "BearerAuthMiddleware"
