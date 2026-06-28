"""B-owned user-system HTTP routes."""

from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request

from services.db import DatabaseUnavailable
from services import user as user_service


user_bp = Blueprint("user", __name__)


def _json_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _user_id_from_request(payload: dict[str, Any] | None = None) -> str:
    if request.method == "GET":
        return (request.args.get("user_id") or "").strip()
    return str((payload or {}).get("user_id") or "").strip()


def _ok(fn: Callable[[], dict[str, Any]]):
    try:
        return jsonify(fn())
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except DatabaseUnavailable as exc:
        return jsonify({"ok": False, "error": str(exc), "recoverable": True}), 503


def _require_user_id(user_id: str) -> None:
    if not user_id:
        raise ValueError("缺少 user_id")


@user_bp.post("/api/user/login")
def login():
    payload = _json_payload()
    return _ok(
        lambda: user_service.login(
            login_type=str(payload.get("login_type") or "guest"),
            code=str(payload.get("code") or ""),
            anonymous_id=str(payload.get("anonymous_id") or ""),
        )
    )


@user_bp.get("/api/user/profile")
def get_profile():
    user_id = _user_id_from_request()

    def action():
        _require_user_id(user_id)
        return user_service.get_profile(user_id)

    return _ok(action)


@user_bp.patch("/api/user/profile")
def update_profile():
    payload = _json_payload()
    user_id = _user_id_from_request(payload)

    def action():
        _require_user_id(user_id)
        return user_service.update_profile(user_id, payload)

    return _ok(action)


@user_bp.get("/api/user/privacy")
def get_privacy():
    user_id = _user_id_from_request()

    def action():
        _require_user_id(user_id)
        return user_service.get_privacy(user_id)

    return _ok(action)


@user_bp.patch("/api/user/privacy")
def update_privacy():
    payload = _json_payload()
    user_id = _user_id_from_request(payload)

    def action():
        _require_user_id(user_id)
        return user_service.update_privacy(user_id, payload)

    return _ok(action)


@user_bp.get("/api/user/stats")
def get_stats():
    user_id = _user_id_from_request()

    def action():
        _require_user_id(user_id)
        return user_service.get_stats(user_id)

    return _ok(action)


@user_bp.get("/api/user/vehicle")
def get_vehicle():
    user_id = _user_id_from_request()

    def action():
        _require_user_id(user_id)
        return user_service.get_vehicle(user_id)

    return _ok(action)


@user_bp.patch("/api/user/vehicle")
def update_vehicle():
    payload = _json_payload()
    user_id = _user_id_from_request(payload)

    def action():
        _require_user_id(user_id)
        return user_service.update_vehicle(user_id, payload)

    return _ok(action)


@user_bp.get("/api/user/repairs")
def get_repairs():
    user_id = _user_id_from_request()

    def action():
        _require_user_id(user_id)
        return user_service.get_repairs(user_id)

    return _ok(action)
