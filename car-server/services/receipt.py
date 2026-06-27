# services/receipt.py —— 【B 角色】维修记录存根（核销单）生成
#
# 规则（总文档 6.4 / 11）：
#   - 根据用户已沉淀的诊断维修项生成存根
#   - 有诊断项 → items 非空、total>0；无诊断 → items=[]、total=0
#   - VIN 脱敏；MVP 阶段标注为模拟（simulated=True），不接真实门店

from datetime import datetime

from services import context as ctx_service

SHOP = "车智汇授权维修中心"
SHOP_CODE = "91110108MA01XXXXXXXX"  # 模拟门店编码


def build_receipt(user_id: str) -> dict:
    items = ctx_service.get_receipt_items(user_id)
    raw = ctx_service.get_raw_context(user_id)
    total = sum(int(it.get("avg", 0)) for it in items)
    return {
        "shop": SHOP,
        "shop_code": SHOP_CODE,
        "car_model": raw.get("car_model", ""),
        "vin": ctx_service.mask_vin(raw.get("vin", "")),
        "location": raw.get("location", ""),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
        "total": total,
        "simulated": True,
    }
