# agents/maintain.py —— 【B 角色】报价审核 / 保养建议 Agent（LangGraph 版）
#
# 职责（总文档 7.4）：
#   1. 从用户文本匹配维修项目（查 kb_cost 维修成本知识库）
#   2. 若用户给了报价，判断是否低于/高于合理区间
#   3. 输出报价审核、价格区间和避坑三件套
#
# 架构：用 LangGraph StateGraph 编排，流程为
#   START → extract（提价+匹配项目）→ 条件路由
#                                     ├─ 未命中 → clarify（不编造，给澄清）
#                                     └─ 命中  → assess（算区间+判报价+避坑）→ END
#   每个节点是纯函数，可单独 import 单测；状态在 MaintainState 中流转。
#   若 langgraph 不可用（未安装/加载失败），handle 自动退回顺序调用，保证服务永远能跑。
#
# 对外契约（保持不变）：handle(text, context=None) -> dict
#   返回 maintain Agent 负责的部分，供 A 的 routes/chat.py 在 maintain 分支直接合入响应：
#   {
#     "agent": "maintain",
#     "agent_meta": {...},
#     "intent": "...",            # 供 chat.py 组装 route
#     "confidence": 0.9,
#     "hit": bool,
#     "reply": {title, summary, blocks, price_text, price_range},
#     "steps": [...],
#     "receipt_item": {...}       # 命中时附带，供 context.add_receipt_item 使用
#   }
#
# 说明：本模块不依赖 Flask，可被直接 import 单测；A 不需要改本文件。

import re
from typing import Optional, TypedDict

from routes.kb import load_kb  # 复用知识库读取（B 同时维护 routes/kb.py）
from services import rag  # RAG 语义检索（不可用时自动退回关键词）

# 成本库语义检索的余弦距离阈值：超过则认为不相关，退回关键词匹配
# （本地 bge-small-zh 距离较压缩，取 0.55）
_COST_RAG_MAX_DISTANCE = 0.55

INTENT = "保养建议/报价审核"
AGENT_META = {"name": "保养建议 Agent", "desc": "报价/避坑指南"}
LEGAL_NOTE = "所有建议仅供参考，请以当地授权维修点为准。"


# ===================== 基础工具函数（与图无关，可独立单测） =====================

def _extract_price(text: str):
    """从文本提取报价金额，如 '800元' / '800 块' / '￥800'；提取不到返回 None。"""
    m = re.search(r"(?:￥|¥)\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块|RMB|rmb)", text)
    if m:
        return float(m.group(1))
    return None


def _match_item_by_keyword(text: str, cost_kb: list):
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


def _init_steps() -> list:
    return [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（90%）"},
        {"name": "分发至 保养建议 Agent", "status": "done"},
        {"name": "知识库检索", "status": "done"},
        {"name": "合成回复", "status": "done"},
    ]


# ===================== LangGraph 状态定义 =====================

class MaintainState(TypedDict, total=False):
    """图在节点间流转的状态。total=False 允许各节点只更新自己产出的字段。"""
    text: str                 # 输入：用户文本
    context: dict             # 输入：车辆上下文
    quoted: Optional[float]   # extract 产出：提取到的报价
    item: Optional[dict]      # extract/retrieve 产出：匹配到的维修项目（None=未命中）
    rag_hits: list            # retrieve 产出：RAG 命中列表 [{item, distance}]
    steps: list               # 思考步骤（贯穿全图）
    result: dict              # 终态：最终对外返回的完整 dict


# ===================== 节点实现（每个节点接收 state，返回部分更新） =====================

def extract_node(state: MaintainState) -> dict:
    """提取报价金额 + 关键词匹配维修项目，初始化思考步骤。

    只做“关键词精确匹配”；关键词未命中时由独立的 retrieve 节点走 RAG 语义检索，
    使检索成为图里一个显式可观测的步骤。
    """
    text = state.get("text", "") or ""
    cost_kb = load_kb("cost") or []
    item = _match_item_by_keyword(text, cost_kb)
    quoted = _extract_price(text)
    steps = _init_steps()
    if item is not None:
        steps[2]["detail"] = "关键词命中"
    return {"quoted": quoted, "item": item, "steps": steps}


def retrieve_node(state: MaintainState) -> dict:
    """RAG 语义检索节点（关键词未命中时调用）。

    复用 services/rag.py 的 LangGraph 检索节点工厂，对成本库做语义召回，写入 rag_hits。
    纯本地、无需 API Key。
    """
    text = state.get("text", "") or ""
    hits = rag.search("cost", text, top_k=1, max_distance=_COST_RAG_MAX_DISTANCE) or []
    steps = state.get("steps", _init_steps())
    if hits:
        steps[2]["detail"] = "RAG 语义命中"
    else:
        steps[2]["status"] = "miss"
    return {"rag_hits": hits, "steps": steps}


def _current_item(state: MaintainState):
    """图中“当前命中的维修项目”：优先关键词命中的 item，否则取 RAG 第一条。"""
    if state.get("item"):
        return state["item"]
    hits = state.get("rag_hits") or []
    return hits[0]["item"] if hits else None


def _route_after_extract(state: MaintainState) -> str:
    """关键词命中 → 直接 assess；未命中 → 走 retrieve 节点做语义检索。"""
    return "assess" if state.get("item") is not None else "retrieve"


def _route_after_retrieve(state: MaintainState) -> str:
    """RAG 命中 → assess；仍未命中 → clarify（不编造）。"""
    return "assess" if _current_item(state) is not None else "clarify"


def clarify_node(state: MaintainState) -> dict:
    """未命中：不编造，返回澄清提示（hit=false）。对应 B4-1 未命中回退。"""
    return {
        "result": {
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
            "steps": state.get("steps", _init_steps()),
        }
    }


def assess_node(state: MaintainState) -> dict:
    """命中：计算合理区间、判断报价、组装避坑三件套（hit=true）。"""
    item = _current_item(state)
    quoted = state.get("quoted")
    context = state.get("context") or {}
    location = context.get("location", "")

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

    # 供 A 的 chat.py 在诊断后调用 context.add_receipt_item(user_id, receipt_item)
    receipt_item = {
        "item": item["item"],
        "part_range": f"{part_low}-{part_high}",
        "labor_range": f"{labor_low}-{labor_high}",
        "avg": (total_low + total_high) // 2,
    }

    return {
        "result": {
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
            "steps": state.get("steps", _init_steps()),
            "receipt_item": receipt_item,
        }
    }


# ===================== 图的构建（编译一次，模块级缓存） =====================

_graph = None


def _build_graph():
    """构建并编译 maintain 的 StateGraph。langgraph 不可用时抛异常，由 handle 退回。

    流程：
        START → extract → [关键词命中? assess : retrieve]
                retrieve → [RAG命中? assess : clarify]
                assess / clarify → END
    """
    from langgraph.graph import StateGraph, START, END

    g = StateGraph(MaintainState)
    g.add_node("extract", extract_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("clarify", clarify_node)
    g.add_node("assess", assess_node)
    g.add_edge(START, "extract")
    g.add_conditional_edges(
        "extract",
        _route_after_extract,
        {"assess": "assess", "retrieve": "retrieve"},
    )
    g.add_conditional_edges(
        "retrieve",
        _route_after_retrieve,
        {"assess": "assess", "clarify": "clarify"},
    )
    g.add_edge("clarify", END)
    g.add_edge("assess", END)
    return g.compile()


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def _handle_fallback(text: str, context=None) -> dict:
    """langgraph 不可用时的顺序退回：手工串起 extract → retrieve → clarify/assess。

    逻辑与图完全一致，保证“永远能跑”。
    """
    state: MaintainState = {"text": text, "context": context or {}}
    state.update(extract_node(state))
    if _route_after_extract(state) == "retrieve":
        state.update(retrieve_node(state))
        nxt = _route_after_retrieve(state)
    else:
        nxt = "assess"
    if nxt == "clarify":
        state.update(clarify_node(state))
    else:
        state.update(assess_node(state))
    return state["result"]


def handle(text: str, context=None) -> dict:
    """对外入口：优先走 LangGraph 图；图不可用时优雅退回顺序执行。"""
    context = context or {}
    try:
        graph = _get_graph()
    except Exception as e:  # langgraph 未安装 / 加载失败
        print(f"[maintain] LangGraph 不可用，退回顺序执行，原因: {e}")
        return _handle_fallback(text, context)

    final_state = graph.invoke({"text": text, "context": context})
    return final_state["result"]
