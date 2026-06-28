"""User-system service layer backed by MySQL."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from services.db import DatabaseUnavailable
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


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def _json_loads(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _page(value: Any, default: int = 1) -> int:
    return max(1, _as_int(value, default))


def _page_size(value: Any, default: int = 20) -> int:
    return max(1, min(_as_int(value, default), 50))


def _created_at_from(payload: dict[str, Any], snapshot: dict[str, Any] | None = None) -> str:
    raw = str(payload.get("created_at") or (snapshot or {}).get("created_at") or "").strip()
    if not raw:
        return ""
    raw = raw.replace("T", " ").replace("Z", "")
    if "+" in raw:
        raw = raw.split("+", 1)[0]
    return raw[:19]


def _is_missing_record_table_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        ("user_repairs" in text or "user_consultations" in text)
        and ("doesn't exist" in text or "does not exist" in text or "1146" in text or "no such table" in text)
    )


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


def _format_repair(row: dict[str, Any], include_snapshot: bool = True) -> dict[str, Any]:
    item = {
        "id": row["receipt_id"],
        "receipt_id": row["receipt_id"],
        "title": row.get("title") or "维修记录",
        "summary": row.get("summary") or "",
        "created_at": _format_dt(row.get("created_at")),
        "total": int(row.get("total") or 0),
    }
    if include_snapshot:
        item["receipt_snapshot"] = _json_loads(row.get("receipt_snapshot"), {})
    return item


def _format_consultation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "consultation_id": row["consultation_id"],
        "question": row.get("question") or "",
        "agent": row.get("agent") or "",
        "intent": row.get("intent") or "",
        "title": row.get("title") or "",
        "summary": row.get("summary") or "",
        "reply_snapshot": _json_loads(row.get("reply_snapshot"), {}),
        "sources": _json_loads(row.get("sources"), []),
        "created_at": _format_dt(row.get("created_at")),
    }


def _empty_repairs(user_id: str, page: int, page_size: int) -> dict[str, Any]:
    return {"user_id": user_id, "total": 0, "page": page, "page_size": page_size, "count": 0, "items": []}


def get_repairs(user_id: str, page: int = 1, page_size: int = 20, receipt_id: str = "") -> dict[str, Any]:
    page = _page(page)
    page_size = _page_size(page_size)
    receipt_id = (receipt_id or "").strip()

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                _require_user(cursor, user_id)
                if receipt_id:
                    cursor.execute(
                        "SELECT * FROM user_repairs WHERE user_id=%s AND receipt_id=%s",
                        (user_id, receipt_id),
                    )
                    row = cursor.fetchone()
                    items = [_format_repair(row)] if row else []
                    return {"user_id": user_id, "total": len(items), "page": 1, "page_size": 1, "count": len(items), "items": items}

                cursor.execute("SELECT COUNT(*) AS total FROM user_repairs WHERE user_id=%s", (user_id,))
                total = int((cursor.fetchone() or {}).get("total") or 0)
                cursor.execute(
                    """
                    SELECT * FROM user_repairs
                    WHERE user_id=%s
                    ORDER BY created_at DESC, receipt_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, page_size, (page - 1) * page_size),
                )
                items = [_format_repair(row, include_snapshot=False) for row in cursor.fetchall()]
    except DatabaseUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        if _is_missing_record_table_error(exc):
            return _empty_repairs(user_id, page, page_size)
        raise

    return {"user_id": user_id, "total": total, "page": page, "page_size": page_size, "count": len(items), "items": items}


def save_repair(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("user_id") or "").strip()
    receipt_id = str(payload.get("receipt_id") or "").strip()
    if not user_id:
        raise ValueError("缺少 user_id")
    if not receipt_id:
        raise ValueError("缺少 receipt_id")

    snapshot = payload.get("receipt_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    total = _as_int(snapshot.get("total") or payload.get("total"), 0)
    title = str(payload.get("title") or snapshot.get("title") or snapshot.get("shop") or "维修记录").strip()
    items = snapshot.get("items")
    item_count = len(items) if isinstance(items, list) else 0
    summary = str(payload.get("summary") or f"{snapshot.get('shop') or '维修存根'} · {item_count} 个项目").strip()
    created_at = _created_at_from(payload, snapshot)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            _require_user(cursor, user_id)
            _ensure_child_rows(cursor, user_id)
            cursor.execute("SELECT * FROM user_repairs WHERE receipt_id=%s", (receipt_id,))
            existing = cursor.fetchone()
            if existing:
                return {"ok": True, "created": False, "item": _format_repair(existing)}

            if created_at:
                cursor.execute(
                    """
                    INSERT INTO user_repairs
                      (receipt_id, user_id, title, summary, total, receipt_snapshot, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (receipt_id, user_id, title, summary, total, _json_dumps(snapshot), created_at),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_repairs
                      (receipt_id, user_id, title, summary, total, receipt_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (receipt_id, user_id, title, summary, total, _json_dumps(snapshot)),
                )
            cursor.execute(
                "UPDATE user_stats SET receipt_count=receipt_count+1 WHERE user_id=%s",
                (user_id,),
            )
            cursor.execute("SELECT * FROM user_repairs WHERE receipt_id=%s", (receipt_id,))
            row = cursor.fetchone()

    return {"ok": True, "created": True, "item": _format_repair(row)}


def _empty_consultations(user_id: str, page: int, page_size: int) -> dict[str, Any]:
    return {"user_id": user_id, "total": 0, "page": page, "page_size": page_size, "count": 0, "items": []}


def get_consultations(user_id: str, page: int = 1, page_size: int = 20, consultation_id: str = "") -> dict[str, Any]:
    page = _page(page)
    page_size = _page_size(page_size)
    consultation_id = (consultation_id or "").strip()

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                _require_user(cursor, user_id)
                if consultation_id:
                    cursor.execute(
                        "SELECT * FROM user_consultations WHERE user_id=%s AND consultation_id=%s",
                        (user_id, consultation_id),
                    )
                    row = cursor.fetchone()
                    items = [_format_consultation(row)] if row else []
                    return {"user_id": user_id, "total": len(items), "page": 1, "page_size": 1, "count": len(items), "items": items}

                cursor.execute("SELECT COUNT(*) AS total FROM user_consultations WHERE user_id=%s", (user_id,))
                total = int((cursor.fetchone() or {}).get("total") or 0)
                cursor.execute(
                    """
                    SELECT * FROM user_consultations
                    WHERE user_id=%s
                    ORDER BY created_at DESC, consultation_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, page_size, (page - 1) * page_size),
                )
                items = [_format_consultation(row) for row in cursor.fetchall()]
    except DatabaseUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        if _is_missing_record_table_error(exc):
            return _empty_consultations(user_id, page, page_size)
        raise

    return {"user_id": user_id, "total": total, "page": page, "page_size": page_size, "count": len(items), "items": items}


def save_consultation(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("user_id") or "").strip()
    consultation_id = str(payload.get("consultation_id") or "").strip()
    if not user_id:
        raise ValueError("缺少 user_id")
    if not consultation_id:
        raise ValueError("缺少 consultation_id")

    reply_snapshot = payload.get("reply_snapshot")
    if not isinstance(reply_snapshot, dict):
        reply_snapshot = {}
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    question = str(payload.get("question") or "").strip()
    agent = str(payload.get("agent") or "").strip()
    intent = str(payload.get("intent") or "").strip()
    title = str(payload.get("title") or reply_snapshot.get("title") or question or "咨询记录").strip()
    summary = str(payload.get("summary") or reply_snapshot.get("summary") or "").strip()
    created_at = _created_at_from(payload)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            _require_user(cursor, user_id)
            _ensure_child_rows(cursor, user_id)
            cursor.execute("SELECT * FROM user_consultations WHERE consultation_id=%s", (consultation_id,))
            existing = cursor.fetchone()
            if existing:
                return {"ok": True, "created": False, "item": _format_consultation(existing)}

            if created_at:
                cursor.execute(
                    """
                    INSERT INTO user_consultations
                      (consultation_id, user_id, question, agent, intent, title, summary, reply_snapshot, sources, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        consultation_id,
                        user_id,
                        question,
                        agent,
                        intent,
                        title,
                        summary,
                        _json_dumps(reply_snapshot),
                        _json_dumps(sources),
                        created_at,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_consultations
                      (consultation_id, user_id, question, agent, intent, title, summary, reply_snapshot, sources)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        consultation_id,
                        user_id,
                        question,
                        agent,
                        intent,
                        title,
                        summary,
                        _json_dumps(reply_snapshot),
                        _json_dumps(sources),
                    ),
                )
            cursor.execute(
                "UPDATE user_stats SET consult_count=consult_count+1 WHERE user_id=%s",
                (user_id,),
            )
            cursor.execute("SELECT * FROM user_consultations WHERE consultation_id=%s", (consultation_id,))
            row = cursor.fetchone()

    return {"ok": True, "created": True, "item": _format_consultation(row)}
