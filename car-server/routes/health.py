# routes/health.py —— 公共健康检查接口（基座阶段已完成，一般无需改动）
from flask import Blueprint, jsonify

APP_NAME = "chexiaozhi-server"
APP_VERSION = "0.1.0"

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/ping")
def ping():
    """验证小程序与服务端联通。返回固定 JSON。"""
    return jsonify({"ok": True, "name": APP_NAME, "version": APP_VERSION})


@health_bp.get("/")
def index():
    """根路径，便于浏览器直接确认服务已启动。"""
    return jsonify(
        {
            "ok": True,
            "name": APP_NAME,
            "version": APP_VERSION,
            "endpoints": [
                "/api/ping",
                "/api/chat",
                "/api/chat/image",
                "/api/asr",
                "/api/context",
                "/api/receipt",
                "/api/kb/<kind>",
                "/api/kb/<kind>/<item_id>",
                "/api/user/login",
                "/api/user/profile",
                "/api/user/privacy",
                "/api/user/stats",
                "/api/user/vehicle",
                "/api/user/consultations",
                "/api/user/repairs",
            ],
        }
    )
