# routes/kb.py -- Knowledge base API: /api/kb/<kind>
#
# Reads knowledge/*.json, supports exact/RAG/fallback search, and returns the
# normalized card structure expected by the miniapp knowledge-base page.

import json
import os
import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

kb_bp = Blueprint("kb", __name__)

_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
_FILES = {"dtc": "kb_dtc.json", "cost": "kb_cost.json", "symptom": "kb_symptom.json"}
_LABELS = {"dtc": "故障码", "cost": "维修成本", "symptom": "症状关联"}
_SEARCH_MAX_DISTANCE = 0.55
_DTC_CODE_RE = re.compile(r"[PBCUpbcu]\d{4}")


def load_kb(kind: str) -> Optional[List[Dict[str, Any]]]:
    """Read a knowledge-base JSON file. Unknown kind returns None."""
    filename = _FILES.get(kind)
    if not filename:
        return None
    path = os.path.join(_KB_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def search_raw_kb(kind: str, query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hybrid search: DTC exact code -> local RAG -> JSON substring fallback."""
    if not query:
        return items

    if kind == "dtc":
        codes = [code.upper() for code in _DTC_CODE_RE.findall(query)]
        if codes:
            exact_hits = [item for item in items if str(item.get("code", "")).upper() in codes]
            if exact_hits:
                return exact_hits

    # Delay import because services.rag imports load_kb from this module.
    from services import rag

    rag_hits = rag.search(kind, query, top_k=5, max_distance=_SEARCH_MAX_DISTANCE)
    if rag_hits:
        return [hit["item"] for hit in rag_hits]

    lowered = query.lower()
    return [item for item in items if lowered in json.dumps(item, ensure_ascii=False).lower()]


def price_range_text(part_low: Any, part_high: Any, labor_low: Any, labor_high: Any) -> str:
    return f"零件 {part_low}-{part_high} 元 · 工时 {labor_low}-{labor_high} 元"


def stars(level: int) -> str:
    value = max(0, min(5, int(level or 0)))
    return "★" * value + "☆" * (5 - value)


def normalize_dtc(item: Dict[str, Any]) -> Dict[str, Any]:
    code = str(item.get("code", ""))
    level = int(item.get("level", 0) or 0)
    price_text = price_range_text(
        item.get("price_part_low", 0),
        item.get("price_part_high", 0),
        item.get("price_labor_low", 0),
        item.get("price_labor_high", 0),
    )
    return {
        "id": code,
        "kind": "dtc",
        "title": code,
        "subtitle": "DTC",
        "summary": item.get("desc", ""),
        "detail": item.get("logic", ""),
        "level": level,
        "level_text": f"难度 {level}/5",
        "level_class": "danger" if level >= 4 else "",
        "stars": stars(level),
        "price_text": price_text,
        "tip": f"可能原因：{item.get('cause', '')}",
        "ask_text": f"{code} 是什么意思？",
        "tags": ["故障码", "知识库匹配"],
        "raw": item,
    }


def normalize_cost(item: Dict[str, Any]) -> Dict[str, Any]:
    title = str(item.get("item", "维修项目"))
    price_text = price_range_text(
        item.get("part_low", 0),
        item.get("part_high", 0),
        item.get("labor_low", 0),
        item.get("labor_high", 0),
    )
    return {
        "id": title,
        "kind": "cost",
        "title": title,
        "subtitle": item.get("cat", "全部车型"),
        "summary": f"{item.get('cat', '全部车型')} · {title}",
        "detail": (
            f"零件 {item.get('part_low', 0)}-{item.get('part_high', 0)} 元，"
            f"工时 {item.get('labor_low', 0)}-{item.get('labor_high', 0)} 元。"
        ),
        "level": "",
        "level_text": "参考价",
        "level_class": "",
        "stars": "",
        "price_text": price_text,
        "tip": item.get("tip", ""),
        "ask_text": f"{title} 多少钱合理？",
        "tags": ["成本", "报价避坑"],
        "raw": item,
    }


def normalize_symptom(item: Dict[str, Any]) -> Dict[str, Any]:
    keywords = item.get("keywords", [])
    title = " / ".join(keywords[:3]) if keywords else "症状"
    level = str(item.get("level", ""))
    price_text = price_range_text(
        item.get("part_low", 0),
        item.get("part_high", 0),
        item.get("labor_low", 0),
        item.get("labor_high", 0),
    )
    return {
        "id": title,
        "kind": "symptom",
        "title": title,
        "subtitle": "症状",
        "summary": f"关联：{item.get('fault', '')}",
        "detail": f"紧急程度：{level}。{item.get('tip', '')}",
        "level": level,
        "level_text": level,
        "level_class": "danger" if level == "高" else "",
        "stars": "",
        "price_text": price_text,
        "tip": item.get("tip", ""),
        "ask_text": f"{title} 是什么问题？",
        "tags": ["症状关联", f"{level}风险"],
        "raw": item,
    }


def normalize_item(kind: str, item: Dict[str, Any]) -> Dict[str, Any]:
    if kind == "dtc":
        return normalize_dtc(item)
    if kind == "cost":
        return normalize_cost(item)
    return normalize_symptom(item)


def normalized_kb(kind: str) -> Optional[List[Dict[str, Any]]]:
    items = load_kb(kind)
    if items is None:
        return None
    return [normalize_item(kind, item) for item in items]


def matches_level(item: Dict[str, Any], level: str) -> bool:
    if not level:
        return True
    raw_level = item.get("level")
    if level == "high":
        if isinstance(raw_level, int):
            return raw_level >= 4
        return raw_level == "高"
    return str(raw_level) == level or item.get("level_text") == level


def tabs_payload() -> List[Dict[str, Any]]:
    tabs = []
    for kind, label in _LABELS.items():
        items = load_kb(kind) or []
        tabs.append({"kind": kind, "label": label, "count": len(items)})
    return tabs


@kb_bp.get("/api/kb/<kind>")
def get_kb(kind):
    raw_items = load_kb(kind)
    if raw_items is None:
        return jsonify({"count": 0, "items": [], "error": f"unknown kind: {kind}"}), 404

    query = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    page_size = min(100, max(1, request.args.get("page_size", default=50, type=int) or 50))

    searched = search_raw_kb(kind, query, raw_items) if query else raw_items
    normalized = [normalize_item(kind, item) for item in searched]
    filtered = [item for item in normalized if matches_level(item, level)]

    total = len(filtered)
    start = (page - 1) * page_size
    current = filtered[start : start + page_size]

    return jsonify(
        {
            "kind": kind,
            "count": len(current),
            "total": total,
            "page": page,
            "page_size": page_size,
            "query": query,
            "items": current,
            "tabs": tabs_payload(),
        }
    )


@kb_bp.get("/api/kb/<kind>/<item_id>")
def get_kb_detail(kind, item_id):
    items = normalized_kb(kind)
    if items is None:
        return jsonify({"error": f"unknown kind: {kind}"}), 404

    decoded_id = item_id.strip()
    for item in items:
        if item["id"] == decoded_id or item["title"] == decoded_id:
            return jsonify(item)

    return jsonify({"error": f"not found: {decoded_id}"}), 404
