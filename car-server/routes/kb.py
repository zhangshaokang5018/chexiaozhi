# routes/kb.py —— 【B 角色】知识库查询 /api/kb/<kind>
#
# kind = dtc / cost / symptom。
#   - 不带 q：返回该类全部条目（{count, items}）
#   - 带 q（?q=关键词或描述）：混合搜索
#       dtc 优先精确码匹配（如 P0300）→ RAG 语义检索 → 关键词子串兜底
#       搜索任一绑定字段（故障码/对应故障/小白解释）都能召回整条
#
# 注意：只改本文件，不要改 app.py。知识库 JSON 由 B 独家维护（A 只读）。

import json
import os
import re

from flask import Blueprint, jsonify, request

kb_bp = Blueprint("kb", __name__)

_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
_FILES = {"dtc": "kb_dtc.json", "cost": "kb_cost.json", "symptom": "kb_symptom.json"}
_SEARCH_MAX_DISTANCE = 0.55  # 知识库语义搜索距离阈值（本地 bge-small-zh，偏召回）
_DTC_CODE_RE = re.compile(r"[PBCUpbcu]\d{4}")


def load_kb(kind: str):
    """读取某类知识库，返回 list；kind 非法返回 None。供其他模块复用。"""
    filename = _FILES.get(kind)
    if not filename:
        return None
    path = os.path.join(_KB_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _search_kb(kind: str, query: str, items: list) -> list:
    """混合搜索：DTC 精确码优先 → RAG 语义 → 关键词子串兜底。"""
    # 1) DTC 精确码匹配优先
    if kind == "dtc":
        codes = [c.upper() for c in _DTC_CODE_RE.findall(query)]
        if codes:
            hit = [it for it in items if it.get("code", "").upper() in codes]
            if hit:
                return hit

    # 2) RAG 语义检索（延迟导入避免与 rag.py 的循环依赖）
    from services import rag

    rag_hits = rag.search(kind, query, top_k=5, max_distance=_SEARCH_MAX_DISTANCE)
    if rag_hits:
        return [h["item"] for h in rag_hits]

    # 3) 关键词子串兜底（在整条 JSON 文本里找）
    q = query.lower()
    return [it for it in items if q in json.dumps(it, ensure_ascii=False).lower()]


@kb_bp.get("/api/kb/<kind>")
def get_kb(kind):
    items = load_kb(kind)
    if items is None:
        return jsonify({"count": 0, "items": [], "error": f"unknown kind: {kind}"}), 404

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"count": len(items), "items": items})

    matched = _search_kb(kind, query, items)
    return jsonify({"count": len(matched), "items": matched, "query": query})
