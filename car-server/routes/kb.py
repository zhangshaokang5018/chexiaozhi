# routes/kb.py —— 【B 角色负责】知识库查询 /api/kb/<kind>
#
# 这里提供了一个"读取 knowledge/*.json 并返回"的基础实现，B 可在此基础上扩展
# （MVP 不需要搜索/分页，那些是后续阶段）。kind = dtc / cost / symptom。
#
# 注意：只改本文件，不要改 app.py。知识库 JSON 由 B 独家维护（A 只读）。

import json
import os

from flask import Blueprint, jsonify

kb_bp = Blueprint("kb", __name__)

_KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
_FILES = {"dtc": "kb_dtc.json", "cost": "kb_cost.json", "symptom": "kb_symptom.json"}


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


@kb_bp.get("/api/kb/<kind>")
def get_kb(kind):
    items = load_kb(kind)
    if items is None:
        return jsonify({"count": 0, "items": [], "error": f"unknown kind: {kind}"}), 404
    return jsonify({"count": len(items), "items": items})
