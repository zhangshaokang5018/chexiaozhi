"""B user-system tests.

These tests use a tiny in-memory DB double so they verify B-owned routes and
service logic without requiring a local MySQL server.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from flask import Flask  # noqa: E402
from routes.user import user_bp  # noqa: E402
from services import db as db_service  # noqa: E402
from services import user as user_service  # noqa: E402


def _now():
    return datetime(2026, 6, 28, 10, 0, 0)


def _initial_state():
    return {
        "users": {
            "user_10001": {
                "user_id": "user_10001",
                "login_type": "wechat",
                "openid": None,
                "anonymous_id": None,
                "session_token": "",
                "nickname": "车小智用户",
                "avatar_url": "",
                "phone": "13800008000",
                "profile_completed": 1,
                "created_at": _now(),
            }
        },
        "user_privacy": {},
        "user_vehicle": {},
        "user_stats": {},
        "user_repairs": {},
        "user_consultations": {},
    }


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self._one = None
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def fetchone(self):
        return copy.deepcopy(self._one)

    def fetchall(self):
        return copy.deepcopy(self._many)

    def execute(self, sql, params=None):  # noqa: C901, PLR0912, PLR0915
        normalized = " ".join(sql.strip().split()).lower()
        params = params or ()
        self._one = None
        self._many = []

        if normalized.startswith("select * from users where user_id="):
            self._one = self.state["users"].get(params[0])
            return 1 if self._one else 0

        if "select * from users where login_type='guest' and anonymous_id=" in normalized:
            anonymous_id = params[0]
            self._one = next(
                (
                    row
                    for row in self.state["users"].values()
                    if row.get("login_type") == "guest" and row.get("anonymous_id") == anonymous_id
                ),
                None,
            )
            return 1 if self._one else 0

        if normalized.startswith("update users set session_token="):
            session_token, login_type, user_id = params
            row = self.state["users"][user_id]
            row["session_token"] = session_token
            row["login_type"] = login_type
            return 1

        if normalized.startswith("insert into users"):
            user_id, login_type, openid, anonymous_id, session_token, nickname, profile_completed = params
            self.state["users"][user_id] = {
                "user_id": user_id,
                "login_type": login_type,
                "openid": openid,
                "anonymous_id": anonymous_id,
                "session_token": session_token,
                "nickname": nickname,
                "avatar_url": "",
                "phone": "",
                "profile_completed": profile_completed,
                "created_at": _now(),
            }
            return 1

        if normalized.startswith("insert ignore into user_privacy"):
            self.state["user_privacy"].setdefault(
                params[0],
                {
                    "user_id": params[0],
                    "phone_authorized": 0,
                    "show_vin": 0,
                    "share_diagnosis_for_improvement": 0,
                    "data_retention_days": 180,
                },
            )
            return 1

        if normalized.startswith("insert ignore into user_vehicle"):
            self.state["user_vehicle"].setdefault(
                params[0],
                {"user_id": params[0], "car_model": "", "vin": "", "mileage": "", "location": ""},
            )
            return 1

        if normalized.startswith("insert ignore into user_stats"):
            self.state["user_stats"].setdefault(
                params[0],
                {"user_id": params[0], "consult_count": 0, "receipt_count": 0, "estimated_saved": 0, "favorite_count": 0},
            )
            return 1

        if normalized.startswith("select * from user_privacy where user_id="):
            self._one = self.state["user_privacy"].get(params[0])
            return 1 if self._one else 0

        if normalized.startswith("select * from user_stats where user_id="):
            self._one = self.state["user_stats"].get(params[0])
            return 1 if self._one else 0

        if normalized.startswith("select * from user_vehicle where user_id="):
            self._one = self.state["user_vehicle"].get(params[0])
            return 1 if self._one else 0

        if normalized.startswith("select * from user_repairs where receipt_id="):
            self._one = self.state["user_repairs"].get(params[0])
            return 1 if self._one else 0

        if normalized.startswith("select * from user_repairs where user_id=") and "and receipt_id=" in normalized:
            user_id, receipt_id = params
            row = self.state["user_repairs"].get(receipt_id)
            self._one = row if row and row["user_id"] == user_id else None
            return 1 if self._one else 0

        if normalized.startswith("select count(*) as total from user_repairs"):
            user_id = params[0]
            self._one = {"total": sum(1 for row in self.state["user_repairs"].values() if row["user_id"] == user_id)}
            return 1

        if normalized.startswith("select * from user_repairs where user_id="):
            user_id, limit, offset = params
            rows = [row for row in self.state["user_repairs"].values() if row["user_id"] == user_id]
            rows.sort(key=lambda row: (row["created_at"], row["receipt_id"]), reverse=True)
            self._many = rows[offset : offset + limit]
            return len(self._many)

        if normalized.startswith("insert into user_repairs"):
            if len(params) == 7:
                receipt_id, user_id, title, summary, total, snapshot, created_at = params
            else:
                receipt_id, user_id, title, summary, total, snapshot = params
                created_at = _now()
            self.state["user_repairs"][receipt_id] = {
                "receipt_id": receipt_id,
                "user_id": user_id,
                "title": title,
                "summary": summary,
                "total": total,
                "receipt_snapshot": snapshot,
                "created_at": created_at,
            }
            return 1

        if normalized.startswith("update user_stats set receipt_count=receipt_count+1"):
            self.state["user_stats"][params[0]]["receipt_count"] += 1
            return 1

        if normalized.startswith("select * from user_consultations where consultation_id="):
            self._one = self.state["user_consultations"].get(params[0])
            return 1 if self._one else 0

        if normalized.startswith("select * from user_consultations where user_id=") and "and consultation_id=" in normalized:
            user_id, consultation_id = params
            row = self.state["user_consultations"].get(consultation_id)
            self._one = row if row and row["user_id"] == user_id else None
            return 1 if self._one else 0

        if normalized.startswith("select count(*) as total from user_consultations"):
            user_id = params[0]
            self._one = {"total": sum(1 for row in self.state["user_consultations"].values() if row["user_id"] == user_id)}
            return 1

        if normalized.startswith("select * from user_consultations where user_id="):
            user_id, limit, offset = params
            rows = [row for row in self.state["user_consultations"].values() if row["user_id"] == user_id]
            rows.sort(key=lambda row: (row["created_at"], row["consultation_id"]), reverse=True)
            self._many = rows[offset : offset + limit]
            return len(self._many)

        if normalized.startswith("insert into user_consultations"):
            if len(params) == 10:
                consultation_id, user_id, question, agent, intent, title, summary, reply, sources, created_at = params
            else:
                consultation_id, user_id, question, agent, intent, title, summary, reply, sources = params
                created_at = _now()
            self.state["user_consultations"][consultation_id] = {
                "consultation_id": consultation_id,
                "user_id": user_id,
                "question": question,
                "agent": agent,
                "intent": intent,
                "title": title,
                "summary": summary,
                "reply_snapshot": reply,
                "sources": sources,
                "created_at": created_at,
            }
            return 1

        if normalized.startswith("update user_stats set consult_count=consult_count+1"):
            self.state["user_stats"][params[0]]["consult_count"] += 1
            return 1

        raise AssertionError(f"Unhandled SQL in fake DB: {sql}")


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return FakeCursor(self.state)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


@contextmanager
def fake_connection(state):
    yield FakeConnection(state)


@pytest.fixture()
def user_client(monkeypatch):
    state = _initial_state()
    monkeypatch.setattr(db_service, "get_connection", lambda: fake_connection(state))
    monkeypatch.setattr(user_service, "get_connection", lambda: fake_connection(state))
    app = Flask(__name__)
    app.register_blueprint(user_bp)
    app.config.update(TESTING=True)
    return app.test_client(), state


def test_guest_login_is_stable(user_client):
    client, state = user_client
    payload = {"login_type": "guest", "anonymous_id": "anon_test"}

    first = client.post("/api/user/login", json=payload)
    second = client.post("/api/user/login", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["user_id"] == second.get_json()["user_id"]
    assert first.get_json()["user_id"] in state["users"]


def test_save_repair_is_idempotent_and_updates_stats_once(user_client):
    client, state = user_client
    user_service._ensure_child_rows(FakeCursor(state), "user_10001")
    payload = {
        "user_id": "user_10001",
        "receipt_id": "r_test_001",
        "receipt_snapshot": {"shop": "测试门店", "total": 880, "items": [{"item": "火花塞"}]},
        "created_at": "2026-06-28T10:35:00+08:00",
    }

    first = client.post("/api/user/repairs", json=payload)
    second = client.post("/api/user/repairs", json=payload)
    listing = client.get("/api/user/repairs", query_string={"user_id": "user_10001"})

    assert first.status_code == 200
    assert first.get_json()["created"] is True
    assert second.get_json()["created"] is False
    assert state["user_stats"]["user_10001"]["receipt_count"] == 1
    assert listing.get_json()["total"] == 1
    assert listing.get_json()["items"][0]["receipt_id"] == "r_test_001"


def test_save_consultation_is_idempotent_and_updates_stats_once(user_client):
    client, state = user_client
    user_service._ensure_child_rows(FakeCursor(state), "user_10001")
    payload = {
        "user_id": "user_10001",
        "consultation_id": "c_test_001",
        "question": "P0300 是什么意思",
        "agent": "dtc",
        "intent": "故障码解读",
        "reply_snapshot": {"title": "P0300", "summary": "缺火", "price_range": [1000, 2500]},
        "sources": [{"kind": "dtc", "item_id": "P0300", "title": "发动机缺火"}],
        "created_at": "2026-06-28T10:30:00+08:00",
    }

    first = client.post("/api/user/consultations", json=payload)
    second = client.post("/api/user/consultations", json=payload)
    listing = client.get("/api/user/consultations", query_string={"user_id": "user_10001"})

    assert first.status_code == 200
    assert first.get_json()["created"] is True
    assert second.get_json()["created"] is False
    assert state["user_stats"]["user_10001"]["consult_count"] == 1
    item = listing.get_json()["items"][0]
    assert item["consultation_id"] == "c_test_001"
    assert item["reply_snapshot"]["summary"] == "缺火"
    assert item["sources"][0]["item_id"] == "P0300"


def test_user_schema_contains_six_tables_and_demo_records():
    schema = (_SERVER_ROOT / "sql" / "user_schema.sql").read_text(encoding="utf-8")
    for table in (
        "users",
        "user_privacy",
        "user_vehicle",
        "user_stats",
        "user_repairs",
        "user_consultations",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "c_demo_001" in schema
    assert "r_demo_001" in schema


def test_missing_record_tables_return_empty_lists(monkeypatch):
    @contextmanager
    def missing_table_connection():
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, sql, params=None):
                if "FROM users" in sql:
                    self._one = {"user_id": "user_10001"}
                    return 1
                if "user_consultations" in sql:
                    raise RuntimeError("Table 'chexiaozhi_user.user_consultations' doesn't exist (1146)")
                raise RuntimeError("Table 'chexiaozhi_user.user_repairs' doesn't exist (1146)")

            def fetchone(self):
                return self._one

        class Conn:
            def cursor(self):
                return Cursor()

            def commit(self):
                return None

            def rollback(self):
                return None

            def close(self):
                return None

        yield Conn()

    monkeypatch.setattr(user_service, "get_connection", missing_table_connection)

    repairs = user_service.get_repairs("user_10001", page=1, page_size=3)
    consultations = user_service.get_consultations("user_10001", page=1, page_size=3)

    assert repairs["items"] == []
    assert repairs["total"] == 0
    assert consultations["items"] == []
    assert consultations["total"] == 0
