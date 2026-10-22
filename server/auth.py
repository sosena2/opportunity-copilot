"""Authentication helpers for the Streamable HTTP MCP transport."""
import hmac
import logging
import os


log = logging.getLogger("copilot.auth")


def configured_token() -> str:
    """Return the configured HTTP token or fail closed."""
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is required for Streamable HTTP. "
            "Set it in the environment or use stdio for local access."
        )
    return token


def valid_bearer_header(header: str, expected_token: str) -> bool:
    """Validate an Authorization header without revealing token values."""
    scheme, separator, supplied = header.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(supplied.strip(), expected_token)


class BearerAuthMiddleware:
    """Protect the MCP endpoint while leaving non-MCP routes untouched."""

    def __init__(self, app, expected_token: str, path: str = "/mcp"):
        self.app = app
        self.expected_token = expected_token
        self.path = path

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") != self.path:
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        if not valid_bearer_header(headers.get("authorization", ""), self.expected_token):
            log.warning("rejected MCP HTTP request: invalid bearer token")
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"authentication required"}',
                }
            )
            return

        log.info("accepted authenticated MCP HTTP request")
        await self.app(scope, receive, send)
