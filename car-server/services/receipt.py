# services/receipt.py —— 维修记录存根（核销单）生成
#
# 规则（总文档 6.4 / 11）：
#   - 根据用户已沉淀的诊断维修项生成存根
#   - 有诊断项 → items 非空、total>0；无诊断 → items=[]、total=0
#   - VIN 脱敏；MVP 阶段标注为模拟（simulated=True），不接真实门店

from datetime import datetime
import hashlib

from services import context as ctx_service

SHOP = "车智汇授权维修中心"
SHOP_CODE = "91110108MA01XXXXXXXX"  # 模拟门店编码


def _stable_receipt_id(user_id: str, items: list) -> str:
    raw_items = "|".join(
        f"{it.get('item', '')}:{it.get('part_range', '')}:{it.get('labor_range', '')}:{it.get('avg', '')}"
        for it in items
    )
    digest = hashlib.sha1(f"{user_id or ''}|{raw_items}".encode("utf-8")).hexdigest()[:12]
    return f"r_{digest}"


def build_receipt(user_id: str) -> dict:
    items = ctx_service.get_receipt_items(user_id)
    raw = ctx_service.get_raw_context(user_id)
    total = sum(int(it.get("avg", 0)) for it in items)
    return {
        "receipt_id": _stable_receipt_id(user_id, items),
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
