# agents/symptom.py —— 【A 角色】症状分析 Agent
#
# 职责（总文档 7 / 05 A-T4）：
#   1. 从用户口语症状描述匹配 kb_symptom 知识库（异响/抖动/报警/水温等）
#   2. 命中：给出可能故障(fault)、紧急程度(level 高/中/低)、排查建议(tip)、价格区间
#      level=="高" 时必须输出红色 danger 强提醒（高风险场景）
#   3. 关键词未命中 → 走 RAG 语义检索；仍未命中 → 澄清（不编造）
#
# 对外契约（与 maintain/dtc 完全一致，见 03 §9）：
#   handle(text, context=None) -> dict
#
# 说明：本模块不依赖 Flask，可被直接 import 单测。RAG 不可用时自动退回关键词。

from routes.kb import load_kb
from services import rag

_SYMPTOM_RAG_MAX_DISTANCE = 0.55

INTENT = "症状分析"
AGENT_META = {"name": "症状分析 Agent", "desc": "异响/抖动/报警判断"}


def _match_by_keyword(text: str, symptom_kb: list):
    """关键词匹配症状，取命中关键词最长的一条；匹配不到返回 None。"""
    best, best_score = None, 0
    for item in symptom_kb:
        for kw in item.get("keywords", []):
            if kw and kw in text and len(kw) > best_score:
                best, best_score = item, len(kw)
    return best


def _init_steps(detail_retrieve: str = "知识库检索") -> list:
    return [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（86%）"},
        {"name": "分发至 症状分析 Agent", "status": "done"},
        {"name": "知识库检索", "status": "done", "detail": detail_retrieve},
        {"name": "合成回复", "status": "done"},
    ]


def _build_hit(item: dict, steps: list, confidence: float) -> dict:
    """命中一条症状知识，组装统一返回结构。"""
    level = str(item.get("level", "")).strip()
    fault = item.get("fault", "")
    tip = item.get("tip", "")
    keywords = item.get("keywords", [])
    title_kw = " / ".join(keywords[:3]) if keywords else "症状"

    part_low = item.get("part_low", 0)
    part_high = item.get("part_high", 0)
    labor_low = item.get("labor_low", 0)
    labor_high = item.get("labor_high", 0)
    total_low = part_low + labor_low
    total_high = part_high + labor_high

    blocks = [
        {"type": "kv", "label": "可能故障", "value": fault},
    ]

    # 紧急程度：高 → 红色 danger 强提醒；中/低 → 黄色 warn
    if level == "高":
        blocks.append({
            "type": "danger",
            "text": f"🚨 紧急程度：高。{tip}",
        })
    else:
        blocks.append({"type": "kv", "label": "紧急程度", "value": level or "中"})
        if tip:
            blocks.append({"type": "warn", "text": f"排查建议：{tip}"})

    blocks.append({"type": "kv", "label": "零件参考价", "value": f"{part_low}-{part_high} 元"})
    blocks.append({"type": "kv", "label": "工时参考价", "value": f"{labor_low}-{labor_high} 元"})
    blocks.append({"type": "warn", "text": "避坑：先做检测定位再决定维修项目，保留旧件与检测记录。"})

    receipt_item = {
        "item": f"{title_kw} 诊断",
        "part_range": f"{part_low}-{part_high}",
        "labor_range": f"{labor_low}-{labor_high}",
        "avg": (total_low + total_high) // 2,
    }

    return {
        "agent": "symptom",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": confidence,
        "hit": True,
        "reply": {
            "title": "症状分析",
            "summary": f"{title_kw} · {fault} · 紧急程度 {level or '中'}",
            "blocks": blocks,
            "price_text": f"{total_low}-{total_high} 元（零件 {part_low}-{part_high} + 工时 {labor_low}-{labor_high}）",
            "price_range": [total_low, total_high],
        },
        "steps": steps,
        "receipt_item": receipt_item,
    }


def _build_clarify(steps: list) -> dict:
    """未命中：不编造，给澄清提示（hit=false）。"""
    return {
        "agent": "symptom",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.5,
        "hit": False,
        "reply": {
            "title": "需要补充信息",
            "summary": "未能识别具体症状",
            "blocks": [
                {"type": "warn", "text": "请补充描述：异响/抖动出现的位置、时机（怠速/加速/刹车）、是否伴随报警灯，方便进一步判断。"},
            ],
            "price_text": "",
            "price_range": [],
        },
        "steps": steps,
    }


def handle(text: str, context=None) -> dict:
    """对外入口：关键词匹配 → RAG 语义检索 → 澄清。"""
    text = text or ""
    symptom_kb = load_kb("symptom") or []

    # 1) 关键词精确匹配
    item = _match_by_keyword(text, symptom_kb)
    if item is not None:
        return _build_hit(item, _init_steps("关键词命中"), 0.86)

    # 2) RAG 语义检索
    hits = rag.search("symptom", text, top_k=1, max_distance=_SYMPTOM_RAG_MAX_DISTANCE) or []
    if hits:
        return _build_hit(hits[0]["item"], _init_steps("RAG 语义命中"), 0.78)

    # 3) 未命中：澄清
    steps = _init_steps("未命中")
    steps[2]["status"] = "miss"
    return _build_clarify(steps)
