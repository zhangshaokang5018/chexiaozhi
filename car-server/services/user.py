"""B-owned user-system service layer backed by MySQL."""

from __future__ import annotations

import secrets
import time
from typing import Any

from services.db import get_connection


DEFAULT_USER_ID = "user_10001"


def _bool(value: Any) -> bool:
    return bool(int(value or 0))


def _mask_phone(phone: str | None) -> str:
    phone = phone or ""
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _mask_vin(vin: str | None) -> str:
    vin = vin or ""
    if len(vin) <= 8:
        return vin
    return f"{vin[:4]}*********{vin[-4:]}"


def _format_dt(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _new_user_id() -> str:
    return f"user_{int(time.time() * 1000)}_{secrets.token_hex(2)}"


def _new_session_token() -> str:
    return f"dev-{secrets.token_urlsafe(24)}"


def _ensure_child_rows(cursor, user_id: str) -> None:
    cursor.execute("INSERT IGNORE INTO user_privacy (user_id) VALUES (%s)", (user_id,))
    cursor.execute("INSERT IGNORE INTO user_vehicle (user_id) VALUES (%s)", (user_id,))
    cursor.execute("INSERT IGNORE INTO user_stats (user_id) VALUES (%s)", (user_id,))


def _get_user(cursor, user_id: str) -> dict[str, Any] | None:
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    return cursor.fetchone()


def _require_user(cursor, user_id: str) -> dict[str, Any]:
    user = _get_user(cursor, user_id)
    if not user:
        raise ValueError("用户不存在")
    return user


def login(login_type: str, code: str = "", anonymous_id: str = "") -> dict[str, Any]:
    login_type = login_type if login_type in {"wechat", "guest"} else "guest"
    code = (code or "").strip()
    anonymous_id = (anonymous_id or "").strip()
    session_token = _new_session_token()
    is_new_user = False

    with get_connection() as conn:
        with conn.cursor() as cursor:
            user: dict[str, Any] | None = None
            if login_type == "wechat":
                # MVP: before real wx.code2Session is wired, reuse the demo user.
                user = _get_user(cursor, DEFAULT_USER_ID)
            elif anonymous_id:
                cursor.execute(
                    "SELECT * FROM users WHERE login_type='guest' AND anonymous_id=%s LIMIT 1",
                    (anonymous_id,),
                )
                user = cursor.fetchone()

            if user:
                user_id = user["user_id"]
                cursor.execute(
                    "UPDATE users SET session_token=%s, login_type=%s WHERE user_id=%s",
                    (session_token, login_type, user_id),
                )
            else:
                user_id = _new_user_id()
                nickname = "车小智用户" if login_type == "wechat" else "游客车主"
                openid = code or None if login_type == "wechat" else None
                cursor.execute(
                    """
                    INSERT INTO users
                      (user_id, login_type, openid, anonymous_id, session_token, nickname, profile_completed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        login_type,
                        openid,
                        anonymous_id or None,
                        session_token,
                        nickname,
                        1 if login_type == "wechat" else 0,
                    ),
                )
                is_new_user = True

            _ensure_child_rows(cursor, user_id)
            user = _require_user(cursor, user_id)

    return {
        "ok": True,
        "user_id": user_id,
        "session_token": session_token,
        "is_new_user": is_new_user,
        "profile_completed": _bool(user.get("profile_completed")),
    }


def get_profile(user_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            user = _require_user(cursor, user_id)

    return {
        "user_id": user["user_id"],
        "nickname": user.get("nickname") or "车小智用户",
        "avatar_url": user.get("avatar_url") or "",
        "phone_masked": _mask_phone(user.get("phone")),
        "created_at": _format_dt(user.get("created_at")),
        "profile_completed": _bool(user.get("profile_completed")),
    }


def update_profile(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields: list[str] = []
    values: list[Any] = []
    for key in ("nickname", "avatar_url"):
        if key in payload:
            fields.append(f"{key}=%s")
            values.append(str(payload.get(key) or "").strip())

    if fields:
        fields.append("profile_completed=1")
        with get_connection() as conn:
            with conn.cursor() as cursor:
                _require_user(cursor, user_id)
                cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id=%s", (*values, user_id))

    return get_profile(user_id)


def get_privacy(user_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            _require_user(cursor, user_id)
            _ensure_child_rows(cursor, user_id)
            cursor.execute("SELECT * FROM user_privacy WHERE user_id=%s", (user_id,))
            privacy = cursor.fetchone() or {}

    return {
        "user_id": user_id,
        "phone_authorized": _bool(privacy.get("phone_authorized")),
        "show_vin": _bool(privacy.get("show_vin")),
        "share_diagnosis_for_improvement": _bool(privacy.get("share_diagnosis_for_improvement")),
        "data_retention_days": int(privacy.get("data_retention_days") or 180),
    }


def update_privacy(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "phone_authorized": lambda value: 1 if bool(value) else 0,
        "show_vin": lambda value: 1 if bool(value) else 0,
        "share_diagnosis_for_improvement": lambda value: 1 if bool(value) else 0,
        "data_retention_days": lambda value: max(30, min(int(value), 3650)),
    }
    fields: list[str] = []
    values: list[Any] = []
    for key, coerce in allowed.items():
        if key in payload:
            fields.append(f"{key}=%s")
            values.append(coerce(payload[key]))

    if fields:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                _require_user(cursor, user_id)
                _ensure_child_rows(cursor, user_id)
                cursor.execute(f"UPDATE user_privacy SET {', '.join(fields)} WHERE user_id=%s", (*values, user_id))

    return get_privacy(user_id)


def get_stats(user_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            _require_user(cursor, user_id)
            _ensure_child_rows(cursor, user_id)
            cursor.execute("SELECT * FROM user_stats WHERE user_id=%s", (user_id,))
            stats = cursor.fetchone() or {}

    return {
        "consult_count": int(stats.get("consult_count") or 0),
        "receipt_count": int(stats.get("receipt_count") or 0),
        "estimated_saved": int(stats.get("estimated_saved") or 0),
        "favorite_count": int(stats.get("favorite_count") or 0),
    }


def get_vehicle(user_id: str) -> dict[str, Any]:
    privacy = get_privacy(user_id)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            _require_user(cursor, user_id)
            _ensure_child_rows(cursor, user_id)
            cursor.execute("SELECT * FROM user_vehicle WHERE user_id=%s", (user_id,))
            vehicle = cursor.fetchone() or {}

    vin = vehicle.get("vin") or ""
    return {
        "user_id": user_id,
        "car_model": vehicle.get("car_model") or "",
        "vin": vin if privacy["show_vin"] else _mask_vin(vin),
        "mileage": vehicle.get("mileage") or "",
        "location": vehicle.get("location") or "",
    }


def update_vehicle(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields: list[str] = []
    values: list[Any] = []
    for key in ("car_model", "vin", "mileage", "location"):
        if key in payload:
            fields.append(f"{key}=%s")
            values.append(str(payload.get(key) or "").strip())

    if fields:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                _require_user(cursor, user_id)
                _ensure_child_rows(cursor, user_id)
                cursor.execute(f"UPDATE user_vehicle SET {', '.join(fields)} WHERE user_id=%s", (*values, user_id))

    return get_vehicle(user_id)


def get_repairs(user_id: str) -> dict[str, Any]:
    stats = get_stats(user_id)
    count = stats["receipt_count"]
    items: list[dict[str, Any]] = []
    if count > 0:
        items = [
            {
                "id": "repair_demo_001",
                "title": "机油机滤保养建议",
                "summary": "来自用户体系的演示维修记录入口，详情仍由 A 的存根页承接。",
                "created_at": "2026-06-27 10:00:00",
                "total": 550,
            }
        ]

    return {"user_id": user_id, "count": len(items), "items": items}
