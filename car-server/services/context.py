# services/context.py —— 【B 角色】用户车辆上下文 + VIN 脱敏 + 诊断项沉淀
#
# MVP 用内存存储（进程内字典，服务重启即清空，满足演示与测试需求）。
# 对外能力：
#   get_context(user_id)           读取上下文（VIN 默认脱敏）
#   get_raw_context(user_id)       读取上下文（VIN 不脱敏，供 receipt 生成）
#   update_context(user_id, data)  更新上下文
#   mask_vin(vin)                  VIN 脱敏
#   add_receipt_item(user_id, it)  沉淀一条诊断维修项（A 的 chat 在诊断后调用）
#   get_receipt_items(user_id)     读取已沉淀维修项
#   reset_user(user_id)            重置某用户（测试前清理）

from copy import deepcopy

# 默认测试用户的初始上下文
_DEFAULT_CONTEXT = {
    "car_model": "2022款 丰田 卡罗拉 1.2T 豪华版",
    "vin": "LFMAP22CXXX123456",
    "mileage": "38,500 km",
    "location": "北京",
}

# user_id -> {"context": {...}, "receipt_items": [...]}
_STORE = {}


def _ensure(user_id: str):
    if user_id not in _STORE:
        _STORE[user_id] = {"context": deepcopy(_DEFAULT_CONTEXT), "receipt_items": []}
    return _STORE[user_id]


def mask_vin(vin: str) -> str:
    """VIN 脱敏：保留前 4 位和后 4 位，中间用 * 替换。"""
    if not vin:
        return ""
    if len(vin) <= 8:
        # 过短时退化处理，至少保留首尾
        keep = max(0, len(vin) - 4)
        return vin[:2] + "*" * keep + vin[-2:]
    return vin[:4] + "*" * (len(vin) - 8) + vin[-4:]


def get_context(user_id: str) -> dict:
    rec = _ensure(user_id)
    ctx = deepcopy(rec["context"])
    ctx["vin"] = mask_vin(ctx.get("vin", ""))
    ctx["receipts"] = list(rec["receipt_items"])
    return ctx


def get_raw_context(user_id: str) -> dict:
    return deepcopy(_ensure(user_id)["context"])


def update_context(user_id: str, data: dict) -> dict:
    rec = _ensure(user_id)
    for key in ("car_model", "vin", "mileage", "location"):
        if key in data and data[key] is not None:
            rec["context"][key] = data[key]
    return get_context(user_id)


def add_receipt_item(user_id: str, item: dict):
    rec = _ensure(user_id)
    rec["receipt_items"].append(item)
    return list(rec["receipt_items"])


def get_receipt_items(user_id: str) -> list:
    return list(_ensure(user_id)["receipt_items"])


def reset_user(user_id: str):
    _STORE.pop(user_id, None)
