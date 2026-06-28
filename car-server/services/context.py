# services/context.py —— 用户车辆上下文 + VIN 脱敏 + 诊断项沉淀
#
# 连调阶段优先读取 MySQL user_vehicle；MySQL 不可用或用户不存在时降级到内存。
# 对外能力：
#   get_context(user_id)           读取上下文（VIN 默认脱敏）
#   get_raw_context(user_id)       读取上下文（VIN 不脱敏，供 receipt 生成）
#   update_context(user_id, data)  更新上下文
#   mask_vin(vin)                  VIN 脱敏
#   add_receipt_item(user_id, it)  沉淀一条诊断维修项（chat 在诊断后调用）
#   get_receipt_items(user_id)     读取已沉淀维修项
#   reset_user(user_id)            重置某用户（测试前清理）

from copy import deepcopy
from time import monotonic

from services.db import DatabaseUnavailable, get_connection

# 默认测试用户的初始上下文
_DEFAULT_CONTEXT = {
    "car_model": "2022款 丰田 卡罗拉 1.2T 豪华版",
    "vin": "LFMAP22CXXX123456",
    "mileage": "38,500 km",
    "location": "北京",
}

# user_id -> {"context": {...}, "receipt_items": [...]}
_STORE = {}
_MYSQL_RETRY_AFTER = 0.0
_MYSQL_RETRY_COOLDOWN_SECONDS = 5.0


def _ensure(user_id: str):
    if user_id not in _STORE:
        _STORE[user_id] = {"context": deepcopy(_DEFAULT_CONTEXT), "receipt_items": []}
    return _STORE[user_id]


def _normalize_vehicle(row: dict | None) -> dict:
    row = row or {}
    return {
        "car_model": row.get("car_model") or "",
        "vin": row.get("vin") or "",
        "mileage": row.get("mileage") or "",
        "location": row.get("location") or "",
    }


def _read_mysql_vehicle(user_id: str) -> dict | None:
    global _MYSQL_RETRY_AFTER
    if not user_id:
        return None
    if monotonic() < _MYSQL_RETRY_AFTER:
        return None
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                if not cursor.fetchone():
                    return None
                cursor.execute("INSERT IGNORE INTO user_vehicle (user_id) VALUES (%s)", (user_id,))
                cursor.execute("SELECT * FROM user_vehicle WHERE user_id=%s", (user_id,))
                return _normalize_vehicle(cursor.fetchone())
    except DatabaseUnavailable:
        _MYSQL_RETRY_AFTER = monotonic() + _MYSQL_RETRY_COOLDOWN_SECONDS
        return None
    except Exception:  # noqa: BLE001
        _MYSQL_RETRY_AFTER = monotonic() + _MYSQL_RETRY_COOLDOWN_SECONDS
        return None


def _update_mysql_vehicle(user_id: str, data: dict) -> dict | None:
    global _MYSQL_RETRY_AFTER
    if not user_id:
        return None
    if monotonic() < _MYSQL_RETRY_AFTER:
        return None

    fields = []
    values = []
    for key in ("car_model", "vin", "mileage", "location"):
        if key in data and data[key] is not None:
            fields.append(f"{key}=%s")
            values.append(str(data[key]))

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                if not cursor.fetchone():
                    return None
                cursor.execute("INSERT IGNORE INTO user_vehicle (user_id) VALUES (%s)", (user_id,))
                if fields:
                    cursor.execute(
                        f"UPDATE user_vehicle SET {', '.join(fields)} WHERE user_id=%s",
                        (*values, user_id),
                    )
                cursor.execute("SELECT * FROM user_vehicle WHERE user_id=%s", (user_id,))
                return _normalize_vehicle(cursor.fetchone())
    except DatabaseUnavailable:
        _MYSQL_RETRY_AFTER = monotonic() + _MYSQL_RETRY_COOLDOWN_SECONDS
        return None
    except Exception:  # noqa: BLE001
        _MYSQL_RETRY_AFTER = monotonic() + _MYSQL_RETRY_COOLDOWN_SECONDS
        return None


def _context_for_user(user_id: str) -> dict:
    return _read_mysql_vehicle(user_id) or deepcopy(_ensure(user_id)["context"])


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
    ctx = _context_for_user(user_id)
    ctx["vin"] = mask_vin(ctx.get("vin", ""))
    ctx["receipts"] = list(rec["receipt_items"])
    return ctx


def get_raw_context(user_id: str) -> dict:
    return _context_for_user(user_id)


def update_context(user_id: str, data: dict) -> dict:
    mysql_ctx = _update_mysql_vehicle(user_id, data)
    if mysql_ctx is not None:
        return get_context(user_id)

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
    global _MYSQL_RETRY_AFTER
    _STORE.pop(user_id, None)
    _MYSQL_RETRY_AFTER = 0.0
