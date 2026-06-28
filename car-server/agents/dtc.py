# agents/dtc.py —— 故障码（DTC）解读 Agent
#
# 职责：
#   1. 从用户文本提取 [PBCU]\d{4} 故障码 → 精确查 kb_dtc 知识库
#   2. 命中：给出释义(desc)、大白话(plain)、可能原因(cause)、风险等级(level 1-5)、价格区间
#      level>=4 时输出红色 danger 强提醒
#   3. 未提到代码 / 代码未收录 → 走 RAG 语义检索（用专业描述或大白话也能命中）
#   4. 仍未命中 → 澄清（不编造）
#
# 对外契约（与 maintain.handle 完全一致，见 03 §9）：
#   handle(text, context=None) -> dict
#   {
#     "agent": "dtc", "agent_meta": {...}, "intent": "...", "confidence": float,
#     "hit": bool,
#     "reply": {title, summary, blocks, price_text, price_range},
#     "steps": [...],
#     "receipt_item": {...}   # 仅命中时附带，供 chat.py add_receipt_item 沉淀
#   }
#
# 说明：本模块不依赖 Flask，可被直接 import 单测。RAG 不可用时自动退回，保证永远能跑。

import re

from routes.kb import load_kb
from services import llm, rag

# DTC 语义检索余弦距离阈值（与 routes/kb.py 保持一致）
_DTC_RAG_MAX_DISTANCE = 0.55
# 故障码正则：P/B/C/U + 4 位数字，前后无字母数字，忽略大小写
_DTC_CODE_RE = re.compile(r"(?<![A-Za-z0-9])([PBCUpbcu]\d{4})(?![A-Za-z0-9])")

INTENT = "故障码解读"
AGENT_META = {"name": "故障码解读 Agent", "desc": "DTC 代码解析"}

# 风险等级（1-5）→ 文本描述
_LEVEL_TEXT = {
    1: "1/5 · 轻微，可择期处理",
    2: "2/5 · 较轻，建议尽快检查",
    3: "3/5 · 中等，影响驾驶体验，建议尽快处理",
    4: "4/5 · 较高，长期行驶可能扩大损伤",
    5: "5/5 · 严重，建议立即停驶检修",
}


def _extract_code(text: str):
    """提取首个故障码并大写化；提取不到返回 None。"""
    m = _DTC_CODE_RE.search(text or "")
    return m.group(1).upper() if m else None


def _find_by_code(code: str, dtc_kb: list):
    for item in dtc_kb:
        if str(item.get("code", "")).upper() == code:
            return item
    return None


def _level_text(level: int) -> str:
    return _LEVEL_TEXT.get(int(level or 0), f"{int(level or 0)}/5")


def _init_steps(detail_retrieve: str = "知识库检索") -> list:
    return [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（92%）"},
        {"name": "分发至 故障码解读 Agent", "status": "done"},
        {"name": "知识库检索", "status": "done", "detail": detail_retrieve},
        {"name": "合成回复", "status": "done"},
    ]


def _build_hit(item: dict, code: str, steps: list, confidence: float) -> dict:
    """命中一条 DTC 知识，组装统一返回结构。"""
    level = int(item.get("level", 0) or 0)
    part_low = item.get("price_part_low", 0)
    part_high = item.get("price_part_high", 0)
    labor_low = item.get("price_labor_low", 0)
    labor_high = item.get("price_labor_high", 0)
    total_low = part_low + labor_low
    total_high = part_high + labor_high

    blocks = [
        {"type": "kv", "label": "故障码", "value": f'{code} · {item.get("desc", "")}'},
        {"type": "kv", "label": "通俗解释", "value": item.get("plain", "")},
        {"type": "kv", "label": "可能原因", "value": item.get("cause", "")},
        {"type": "kv", "label": "排查建议", "value": item.get("logic", "")},
        {"type": "kv", "label": "零件参考价", "value": f"{part_low}-{part_high} 元"},
        {"type": "kv", "label": "工时参考价", "value": f"{labor_low}-{labor_high} 元"},
    ]

    # 风险等级：高危（level>=4）红色 danger，其余黄色 warn
    if level >= 4:
        blocks.insert(1, {
            "type": "danger",
            "text": f"🚨 风险等级 {_level_text(level)}。建议尽快到正规维修点检测，避免扩大损伤。",
        })
    else:
        blocks.insert(1, {
            "type": "warn",
            "text": f"风险等级 {_level_text(level)}。",
        })

    blocks.append({"type": "warn", "text": "避坑：要求维修店先出示读码与逐项检测记录，不要一上来就大拆解。"})

    receipt_item = {
        "item": f"故障码 {code} 诊断",
        "part_range": f"{part_low}-{part_high}",
        "labor_range": f"{labor_low}-{labor_high}",
        "avg": (total_low + total_high) // 2,
    }

    return {
        "agent": "dtc",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": confidence,
        "hit": True,
        "reply": {
            "title": f"{code} 故障码解读",
            "summary": f'{code} · {item.get("desc", "")} · 参考 {total_low}-{total_high} 元',
            "blocks": blocks,
            "price_text": f"{total_low}-{total_high} 元（零件 {part_low}-{part_high} + 工时 {labor_low}-{labor_high}）",
            "price_range": [total_low, total_high],
        },
        "steps": steps,
        "sources": [{"kind": "dtc", "item_id": code, "title": item.get("desc", "")}],
        "receipt_item": receipt_item,
    }


def _build_clarify(text: str, steps: list) -> dict:
    """未命中：不编造，给澄清提示（hit=false）。"""
    return {
        "agent": "dtc",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.5,
        "hit": False,
        "reply": {
            "title": "需要补充信息",
            "summary": "未能匹配到对应故障码",
            "blocks": [
                {"type": "warn", "text": "暂未收录该故障码或未识别到代码。请提供完整故障码（如 P0300），或描述具体故障现象。"},
            ],
            "price_text": "",
            "price_range": [],
        },
        "steps": steps,
    }


def handle(text: str, context=None) -> dict:
    """对外入口：提码精确匹配 → RAG 语义检索 → 澄清。"""
    text = text or ""
    dtc_kb = load_kb("dtc") or []

    # 1) 提取故障码并精确匹配
    code = _extract_code(text)
    if code:
        item = _find_by_code(code, dtc_kb)
        if item is not None:
            result = _build_hit(item, code, _init_steps("代码精确命中"), 0.92)
            return llm.enhance_agent_result("dtc", text, context or {}, result)

    # 2) RAG 语义检索（用专业描述或大白话检索）
    hits = rag.search("dtc", text, top_k=1, max_distance=_DTC_RAG_MAX_DISTANCE) or []
    if hits:
        item = hits[0]["item"]
        hit_code = str(item.get("code", code or "")).upper()
        result = _build_hit(item, hit_code, _init_steps("RAG 语义命中"), 0.8)
        return llm.enhance_agent_result("dtc", text, context or {}, result)

    # 3) 未命中：澄清（标记检索未命中）
    steps = _init_steps("未命中")
    steps[2]["status"] = "miss"
    return _build_clarify(text, steps)
