# routes/context.py —— 【B 角色负责】车辆上下文 /api/context
#
# 当前为占位实现(stub)。B 角色 TODO：
#   1. 在 services/context.py 实现 get_context/update_context + mask_vin（VIN 脱敏）
#   2. GET 返回 car_model/vin(脱敏)/mileage/location/receipts（见总文档 6.2）
#   3. POST 更新上下文（见总文档 6.3）
#   4. 默认测试用户 test_user_001 给一份初始数据
#
# 注意：只改本文件 + services/ 下你负责的文件，不要改 app.py。

from flask import Blueprint, request, jsonify

context_bp = Blueprint("context", __name__)


@context_bp.get("/api/context")
def get_context():
    # ===== 占位返回（B 接入 services/context.py 后替换）=====
    return jsonify(
        {
            "car_model": "",
            "vin": "",
            "mileage": "",
            "location": "",
            "receipts": [],
            "_stub": True,
        }
    )


@context_bp.post("/api/context")
def update_context():
    _ = request.get_json(silent=True) or {}
    # ===== 占位返回 =====
    return jsonify({"ok": True, "_stub": True})
