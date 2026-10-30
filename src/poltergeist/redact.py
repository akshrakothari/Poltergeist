"""Redact likely credentials from shell command text before it is persisted or sent."""

from __future__ import annotations

import re

REDACTED = "<REDACTED>"

_AUTHORIZATION = re.compile(r"(?i)(\bauthorization\s*:\s*)(.*)$")
_BEARER = re.compile(r"(?i)(\bbearer\s+)(.*)$")
_SECRET_FLAG = re.compile(
    r"(?i)(--?(?:password|passwd|token|api[-_]?key|secret|p)(?=\s|=)"
    r"(?:\s*=\s*|\s+))((?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|[^\s;&|]+)"
)
_URL_CREDENTIALS = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^\s/@:]+:)([^\s/@]+)(@)")
_TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"\bAQ\.[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
)
_ENV_ASSIGNMENT = re.compile(
    r"(?<![\w$])([A-Za-z_][A-Za-z0-9_]*)=((?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|[^\s;&|]+)"
)


def redact_command(command: str) -> str:
    """Return a redacted copy of *command*; never modify the caller's string."""
    result = _AUTHORIZATION.sub(lambda match: f"{match.group(1)}{REDACTED}", command)
    result = _BEARER.sub(lambda match: f"{match.group(1)}{REDACTED}", result)
    result = _SECRET_FLAG.sub(lambda match: f"{match.group(1)}{REDACTED}", result)
    result = _URL_CREDENTIALS.sub(
        lambda match: f"{match.group(1)}{REDACTED}{match.group(3)}", result
    )
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(REDACTED, result)
    result = _ENV_ASSIGNMENT.sub(lambda match: f"{match.group(1)}={REDACTED}", result)
    return result
