# routes/context.py —— 【B 角色】车辆上下文 /api/context
#
# GET  /api/context?user_id=  读取上下文（VIN 脱敏），见总文档 6.2
# POST /api/context           更新上下文，见总文档 6.3

from flask import Blueprint, request, jsonify

from services import context as ctx_service

context_bp = Blueprint("context", __name__)


@context_bp.get("/api/context")
def get_context():
    user_id = request.args.get("user_id", "")
    return jsonify(ctx_service.get_context(user_id))


@context_bp.post("/api/context")
def update_context():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "")
    ctx = ctx_service.update_context(user_id, data)
    return jsonify({"ok": True, "context": ctx})
