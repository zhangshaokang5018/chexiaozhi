"""Store a DashScope API key in MySQL without committing it to source.

Usage from car-server:
    .venv\\Scripts\\python tools\\set_model_key.py

For non-interactive local setup, set DASHSCOPE_API_KEY in the current shell and
run this script. The key is never printed.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import db, model_keys, user_init  # noqa: E402


def _model_key_table_exists() -> bool:
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES LIKE 'model_api_keys'")
                return bool(cursor.fetchone())
    except Exception:
        return False


def main() -> int:
    provider = os.environ.get("MODEL_KEY_PROVIDER", "dashscope").strip().lower()
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        api_key = getpass.getpass("DashScope API Key: ").strip()
    if not api_key:
        print("No API key provided.")
        return 2

    if not _model_key_table_exists():
        user_init.init_schema()
    model_keys.upsert_api_key(provider, api_key, "local integration key")
    print(f"Stored {provider} key in MySQL model_api_keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
