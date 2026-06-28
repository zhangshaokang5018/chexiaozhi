"""Database-backed model API key access.

All DashScope calls must read the API key from MySQL at call time. This module
never logs or returns masked key material to API responses.
"""

from __future__ import annotations

from services.db import DatabaseUnavailable, get_connection

DEFAULT_PROVIDER = "dashscope"


def get_api_key(provider: str = DEFAULT_PROVIDER) -> str | None:
    """Return an enabled provider key from MySQL, or None if unavailable."""
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    if not provider:
        return None

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT api_key
                    FROM model_api_keys
                    WHERE provider=%s AND enabled=1
                    LIMIT 1
                    """,
                    (provider,),
                )
                row = cursor.fetchone()
    except DatabaseUnavailable:
        return None
    except Exception:
        return None

    key = str((row or {}).get("api_key", "") or "").strip()
    return key or None


def upsert_api_key(provider: str, api_key: str, remark: str = "") -> None:
    """Create or update a provider key in MySQL."""
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    api_key = (api_key or "").strip()
    remark = (remark or "").strip()
    if not provider:
        raise ValueError("provider 不能为空")
    if not api_key:
        raise ValueError("api_key 不能为空")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO model_api_keys (provider, api_key, enabled, remark)
                VALUES (%s, %s, 1, %s)
                ON DUPLICATE KEY UPDATE
                  api_key=VALUES(api_key),
                  enabled=1,
                  remark=VALUES(remark),
                  updated_at=CURRENT_TIMESTAMP
                """,
                (provider, api_key, remark),
            )
