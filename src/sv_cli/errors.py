"""Typed exceptions and exit-code helpers for SV CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CLIError(Exception):
    """Base error carrying a process exit code."""

    message: str
    exit_code: int = 1

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class InvalidInputError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 2)


class AmbiguousMatchError(InvalidInputError):
    pass


class AuthError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 3)


class APIError(CLIError):
    def __init__(self, message: str, *, status_code: int | None = None, data: Any = None) -> None:
        super().__init__(message, 4)
        # Structured detail for callers that present errors themselves (sv-mcp turns
        # the API's own error message into a readable tool error). The message is
        # unchanged, so CLI output is unaffected.
        self.status_code = status_code
        self.data = data


class NetworkError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 5)


class TimeoutError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 6)


class ConfigError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 7)


class UnsupportedFeatureError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 8)
