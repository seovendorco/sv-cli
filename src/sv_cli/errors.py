"""Typed exceptions and exit-code helpers for SV CLI."""

from __future__ import annotations

from dataclasses import dataclass


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
    def __init__(self, message: str) -> None:
        super().__init__(message, 4)


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
