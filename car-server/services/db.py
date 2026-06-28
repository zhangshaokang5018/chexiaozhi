"""MySQL access layer for the B-owned user system.

The module intentionally avoids connecting during import. A's main business can
start without MySQL, and database failures are reported only when /api/user/*
calls actually need the connection.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterable


class DatabaseUnavailable(RuntimeError):
    """Raised when the user-system database cannot be used."""


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise DatabaseUnavailable("缺少用户体系依赖 python-dotenv，请先安装 requirements-user.txt") from exc

    load_dotenv()


def _import_pymysql():
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:
        raise DatabaseUnavailable("缺少用户体系依赖 PyMySQL，请先安装 requirements-user.txt") from exc

    return pymysql, DictCursor


def _config() -> dict[str, Any]:
    _load_env()
    cfg = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "cxz_user"),
        "password": os.getenv("DB_PASSWORD", "cxz_user_dev_2026"),
        "database": os.getenv("DB_NAME", "chexiaozhi_user"),
        "charset": "utf8mb4",
        "autocommit": False,
    }
    missing = [key for key in ("user", "password", "database") if not cfg[key]]
    if missing:
        raise DatabaseUnavailable(f"用户体系数据库配置缺失：{', '.join(missing)}")
    return cfg


def connect():
    pymysql, dict_cursor = _import_pymysql()
    try:
        return pymysql.connect(cursorclass=dict_cursor, **_config())
    except Exception as exc:  # noqa: BLE001
        raise DatabaseUnavailable(f"用户体系数据库连接失败：{exc}") from exc


@contextmanager
def get_connection():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] | dict[str, Any] | None = None) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()


def query_all(sql: str, params: Iterable[Any] | dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())


def execute(sql: str, params: Iterable[Any] | dict[str, Any] | None = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            return cursor.execute(sql, params)
