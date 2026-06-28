"""Small helpers for keeping secrets out of logs and API responses."""

from __future__ import annotations

import re

_DASHSCOPE_KEY_RE = re.compile(r"sk-[A-Za-z0-9]{12,}")


def redact_secret(value: object) -> str:
    """Return a string with DashScope-like keys redacted."""
    return _DASHSCOPE_KEY_RE.sub("sk-***", str(value or ""))
