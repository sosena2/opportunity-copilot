"""Application-level errors exposed by the server modules."""


class InputError(ValueError):
    """Raised when a tool argument is invalid or cannot be processed."""
