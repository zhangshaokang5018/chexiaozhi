# routes/receipt.py —— 【B 角色】维修记录存根 /api/receipt
#
# POST /api/receipt  根据用户已沉淀诊断项生成核销单，见总文档 6.4
#   无诊断 → items=[]、total=0；有诊断 → items 非空、total>0

from flask import Blueprint, request, jsonify

from services import receipt as receipt_service

receipt_bp = Blueprint("receipt", __name__)


@receipt_bp.post("/api/receipt")
def receipt():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "")
    return jsonify(receipt_service.build_receipt(user_id))
