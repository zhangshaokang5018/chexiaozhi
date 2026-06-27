# agents/maintain.py —— 【B 角色】报价审核 / 保养建议 Agent
#
# 职责（总文档 7.4）：
#   1. 从用户文本匹配维修项目（查 kb_cost 维修成本知识库）
#   2. 若用户给了报价，判断是否低于/高于合理区间
#   3. 输出报价审核、价格区间和避坑三件套
#
# 对外契约：handle(text, context=None) -> dict
#   返回 maintain Agent 负责的部分，供 A 的 routes/chat.py 在 maintain 分支直接合入响应：
#   {
#     "agent": "maintain",
#     "agent_meta": {...},
#     "intent": "...",            # 供 chat.py 组装 route
#     "confidence": 0.9,
#     "hit": bool,
#     "reply": {title, summary, blocks, price_text, price_range},
#     "steps": [...]
#   }
#
# 说明：本模块不依赖 Flask，可被直接 import 单测；A 不需要改本文件。

import re

from routes.kb import load_kb  # 复用知识库读取（B 同时维护 routes/kb.py）

INTENT = "保养建议/报价审核"
AGENT_META = {"name": "保养建议 Agent", "desc": "报价/避坑指南"}
LEGAL_NOTE = "所有建议仅供参考，请以当地授权维修点为准。"


def _extract_price(text: str):
    """从文本提取报价金额，如 '800元' / '800 块' / '￥800'；提取不到返回 None。"""
    m = re.search(r"(?:￥|¥)\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块|RMB|rmb)", text)
    if m:
        return float(m.group(1))
    return None


def _match_item(text: str, cost_kb: list):
    """关键词匹配维修项目，取匹配最强(最长命中)的一条；匹配不到返回 None。"""
    best, best_score = None, 0
    for item in cost_kb:
        core = item["item"].replace("更换", "").replace("更新", "").strip()
        score = 0
        if core and core in text:
            score = len(core)
        else:
            # 退化为 2-gram 滑窗匹配，命中即记 2 分
            for i in range(len(core) - 1):
                if core[i:i + 2] in text:
                    score = max(score, 2)
        if score > best_score:
            best, best_score = item, score
    return best


def _fmt_range(low, high) -> str:
    return f"{low}-{high} 元"


def handle(text: str, context=None) -> dict:
    context = context or {}
    location = context.get("location", "")
    cost_kb = load_kb("cost") or []

    item = _match_item(text, cost_kb)
    quoted = _extract_price(text)

    steps = [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（90%）"},
        {"name": "分发至 保养建议 Agent", "status": "done"},
        {"name": "知识库检索", "status": "done"},
        {"name": "合成回复", "status": "done"},
    ]

    # ---- 未匹配到项目：不编造，给澄清 ----
    if item is None:
        steps[2]["status"] = "miss"
        return {
            "agent": "maintain",
            "agent_meta": AGENT_META,
            "intent": INTENT,
            "confidence": 0.5,
            "hit": False,
            "reply": {
                "title": "需要补充信息",
                "summary": "未能识别具体维修项目",
                "blocks": [
                    {"type": "warn", "text": "暂未匹配到对应维修项目，请补充：要做什么保养/维修项目？车型类别是什么？"}
                ],
                "price_text": "",
                "price_range": [],
            },
            "steps": steps,
        }

    # ---- 匹配到项目：计算合理区间 ----
    part_low, part_high = item["part_low"], item["part_high"]
    labor_low, labor_high = item["labor_low"], item["labor_high"]
    total_low = part_low + labor_low
    total_high = part_high + labor_high

    blocks = [
        {"type": "kv", "label": "维修项目", "value": f'{item["item"]}（{item["cat"]}）'},
        {"type": "kv", "label": "零件参考价", "value": _fmt_range(part_low, part_high)},
        {"type": "kv", "label": "工时参考价", "value": _fmt_range(labor_low, labor_high)},
    ]

    # 报价判断（避坑三件套之一）
    if quoted is not None:
        blocks.append({"type": "kv", "label": "商家报价", "value": f"{int(quoted)} 元"})
        if quoted > total_high:
            blocks.append({
                "type": "warn",
                "text": f"报价 {int(quoted)} 元超出市场价上限（{total_high} 元），建议再找 2-3 家报价对比。",
            })
        elif quoted < total_low:
            blocks.append({
                "type": "warn",
                "text": f"报价 {int(quoted)} 元低于市场价下限（{total_low} 元），警惕副厂件/翻新件或漏项。",
            })
        else:
            blocks.append({
                "type": "good",
                "text": f"报价 {int(quoted)} 元在合理区间（{total_low}-{total_high} 元）内，价格基本正常。",
            })

    # 避坑三件套之二：知识库 tip
    blocks.append({"type": "warn", "text": f'避坑提示：{item["tip"]}'})
    # 避坑三件套之三：通用建议
    blocks.append({"type": "warn", "text": "保留工单与旧件，要求注明配件品牌与型号，方便后续维权与比价。"})

    summary_prefix = f"{location} · " if location else ""
    price_text = (
        f"{_fmt_range(total_low, total_high)}"
        f"（零件 {part_low}-{part_high} + 工时 {labor_low}-{labor_high}）"
    )

    return {
        "agent": "maintain",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.9,
        "hit": True,
        "reply": {
            "title": "保养建议 / 报价审核",
            "summary": f'{summary_prefix}{item["item"]} · 参考 {total_low}-{total_high} 元',
            "blocks": blocks,
            "price_text": price_text,
            "price_range": [total_low, total_high],
        },
        "steps": steps,
    }
