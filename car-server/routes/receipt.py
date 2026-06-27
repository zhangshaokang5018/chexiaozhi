# routes/receipt.py —— 【B 角色负责】维修记录存根 /api/receipt
#
# 当前为占位实现(stub)。B 角色 TODO：
#   1. 在 services/receipt.py 根据用户最近一次诊断生成存根
#   2. 有诊断 → items 非空、total>0；无诊断 → items=[]、total=0
#   3. 返回 shop/shop_code/car_model/vin/location/created_at/items/total（见总文档 6.4）
#   4. MVP 标注为模拟，不接真实门店
#
# 注意：只改本文件 + services/ 下你负责的文件，不要改 app.py。

from flask import Blueprint, request, jsonify

receipt_bp = Blueprint("receipt", __name__)


@receipt_bp.post("/api/receipt")
def receipt():
    _ = request.get_json(silent=True) or {}
    # ===== 占位返回（B 接入 services/receipt.py 后替换）=====
    return jsonify(
        {
            "shop": "",
            "shop_code": "",
            "car_model": "",
            "vin": "",
            "location": "",
            "created_at": "",
            "items": [],
            "total": 0,
            "_stub": True,
        }
    )
