"""Application-level errors exposed by the server modules."""
from mcp.server.mcpserver.exceptions import ToolError


class InputError(ToolError, ValueError):
    """Expected tool failure whose safe message can be shown to the model."""
