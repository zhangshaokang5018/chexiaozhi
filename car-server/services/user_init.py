"""Initialize the MySQL user database from sql/user_schema.sql.

Run from car-server:
    python -m services.user_init

This helper is optional. A's main business does not import it.
"""

from __future__ import annotations

from pathlib import Path

from services import db


def _split_sql(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False

    i = 0
    while i < len(script):
        ch = script[i]
        prev = script[i - 1] if i else ""
        if ch == "'" and not in_double and prev != "\\":
            in_single = not in_single
        elif ch == '"' and not in_single and prev != "\\":
            in_double = not in_double

        if ch == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _strip_line_comments(script: str) -> str:
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def init_schema() -> int:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "sql" / "user_schema.sql"
    script = _strip_line_comments(schema_path.read_text(encoding="utf-8"))
    statements = _split_sql(script)

    pymysql, dict_cursor = db._import_pymysql()
    cfg = db._config()
    cfg.pop("database", None)
    conn = pymysql.connect(cursorclass=dict_cursor, **cfg)
    try:
        with conn.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(statements)


if __name__ == "__main__":
    count = init_schema()
    print(f"Initialized user schema with {count} SQL statements.")
