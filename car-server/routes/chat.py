# routes/chat.py -- 【A 角色负责】对话主入口 /api/chat
#
# 流程（05 A-T1/A-T2/A-T5）：
#   route() 意图分类 → 分发到对应智能体 handle(text, context) → 归一化输出契约
#   → 按 03 §2 外形组装响应 → 命中且带 receipt_item 时沉淀到 context
#
# 设计原则：
#   - 统一注册表 AGENT_HANDLERS 分发，新增智能体只需在此登记。
#   - 智能体抛异常 / agent==scheduler → 回退 build_reply() 占位，保证“永远能跑”。
#   - _normalize_agent_result() 把智能体返回里前端未覆盖的枚举（steps.status==miss、
#     blocks.type==good）规范成前端已支持的值，避免前端改动。

from copy import deepcopy
from datetime import datetime
import hashlib
import os
import tempfile
from time import perf_counter

from flask import Blueprint, jsonify, request

from agents import dtc, maintain, part, symptom
from agents.scheduler import route
from services import context as ctx_service
from services import llm

chat_bp = Blueprint("chat", __name__)

LEGAL_NOTE = "所有建议仅供参考，请以当地授权维修点为准。"
DEFAULT_USER_ID = "test_user_001"

# 智能体分发注册表：agent 名 -> handle(text, context) -> dict
AGENT_HANDLERS = {
    "maintain": maintain.handle,
    "dtc": dtc.handle,
    "symptom": symptom.handle,
    "part": part.handle,
}

AGENT_META = {
    "scheduler": {"name": "调度 Agent", "desc": "综合咨询/需补充信息"},
    "symptom": {"name": "症状分析 Agent", "desc": "异响/抖动/报警判断"},
    "dtc": {"name": "故障码解读 Agent", "desc": "DTC 代码解析"},
    "maintain": {"name": "保养建议 Agent", "desc": "报价/避坑指南"},
    "part": {"name": "零件识别 Agent", "desc": "图像/名称匹配"},
}

# 前端 utils/request.ts 支持的枚举（用于归一化校验）
_VALID_STEP_STATUS = {"done", "doing", "pending", "todo"}


def _stable_id(prefix: str, *parts: object) -> str:
    """生成可重复、足够稳定的记录 ID，供 B 侧按 ID 幂等保存。"""
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    day = datetime.now().strftime("%Y%m%d")
    return f"{prefix}_{day}_{digest}"


def _clean_sources(sources) -> list:
    """只透传 B 保存需要的来源字段，避免把 Agent 内部结构塞给前端。"""
    if not isinstance(sources, list):
        return []
    cleaned = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "") or "").strip()
        item_id = str(item.get("item_id", "") or "").strip()
        title = str(item.get("title", "") or "").strip()
        if kind and item_id:
            cleaned.append({"kind": kind, "item_id": item_id, "title": title})
    return cleaned


def build_steps(agent_name: str, intent: str, confidence: float):
    confidence_text = f"{round(confidence * 100)}%"
    return [
        {"name": "意图识别", "status": "done", "detail": f"{intent}（{confidence_text}）"},
        {"name": f"分发至 {agent_name}", "status": "done"},
        {"name": "知识库检索", "status": "done"},
        {"name": "合成回复", "status": "done"},
    ]


def build_reply(agent: str, text: str, image_label: str):
    """Clear fallback message used only when a real model/agent cannot answer."""
    if agent == "scheduler":
        return {
            "title": "需要补充信息",
            "summary": "我还需要更具体的车辆症状、故障码、报价项目或图片类型，或当前未能调用大模型。",
            "blocks": [
                {"type": "kv", "label": "可补充", "value": "车型、里程、故障灯、异响位置、报价项目或故障码。"},
                {"type": "warn", "text": "你可以直接输入 P0300、咕噜咕噜响、800 元换机油机滤合理吗，或点击拍报价单。"},
            ],
            "price_text": "",
            "price_range": [],
        }

    # 智能体异常时的兜底（极少触发）
    return {
        "title": "暂时无法完成分析",
        "summary": f"已识别到咨询：{text}",
        "blocks": [
            {"type": "warn", "text": "智能体处理出现问题，请稍后重试，或换一种描述方式。"},
        ],
        "price_text": "",
        "price_range": [],
    }


def _normalize_agent_result(result: dict) -> dict:
    """把智能体返回归一化为前端已支持的契约（A-T2）。

    - steps[].status 不在 {done,doing,pending,todo} 的（如 maintain/dtc/symptom 的 miss）
      → 映射为 pending，保留 detail 说明未命中。
    - blocks[].type == "good" → 转为 {type:"kv", label:"报价评估", value:<原 text>, good:true}，
      复用前端 WXML 已有的 b.good ? 'green' 上色分支。
    """
    if not isinstance(result, dict):
        return result

    steps = result.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict) and step.get("status") not in _VALID_STEP_STATUS:
                step["status"] = "pending"

    reply = result.get("reply")
    if isinstance(reply, dict):
        blocks = reply.get("blocks")
        if isinstance(blocks, list):
            for i, b in enumerate(blocks):
                if isinstance(b, dict) and b.get("type") == "good":
                    blocks[i] = {
                        "type": "kv",
                        "label": "报价评估",
                        "value": b.get("text", b.get("value", "")),
                        "good": True,
                    }
    return result


def _response_payload(
    started_at: float,
    user_id: str,
    text: str,
    mode: str,
    image_label: str,
    route_result: dict,
    result: dict,
) -> dict:
    agent = str(result.get("agent") or route_result["agent"])
    intent = str(result.get("intent") or route_result["intent"])
    confidence = float(result.get("confidence", route_result["confidence"]))
    hit = bool(result.get("hit", agent != "scheduler"))
    receipt_item = result.get("receipt_item")
    if hit and isinstance(receipt_item, dict):
        ctx_service.add_receipt_item(user_id, receipt_item)

    consultation_id = _stable_id("c", user_id, text, mode, image_label, agent, intent)
    return {
        "consultation_id": consultation_id,
        "route": {"agent": agent, "intent": intent, "confidence": confidence},
        "agent": agent,
        "agent_meta": result.get("agent_meta") or AGENT_META.get(agent, AGENT_META["scheduler"]),
        "hit": hit,
        "reply": result.get("reply") or build_reply(agent, text, image_label),
        "steps": result.get("steps") or build_steps(AGENT_META.get(agent, AGENT_META["scheduler"])["name"], intent, confidence),
        "sources": _clean_sources(result.get("sources")) if hit else [],
        "elapsed_ms": int((perf_counter() - started_at) * 1000),
        "legal_note": LEGAL_NOTE,
    }


def _general_llm_result(text: str, context: dict) -> dict | None:
    reply = llm.generate_general_vehicle_reply(text, context)
    if not reply:
        return None
    return {
        "agent": "scheduler",
        "agent_meta": AGENT_META["scheduler"],
        "intent": "通用汽车问答",
        "confidence": 0.72,
        "hit": True,
        "reply": reply,
        "steps": [
            {"name": "意图识别", "status": "done", "detail": "通用汽车问答（72%）"},
            {"name": "分发至 通用大模型", "status": "done"},
            {"name": "DashScope 文本模型", "status": "done", "detail": llm.TEXT_MODEL},
            {"name": "合成回复", "status": "done"},
        ],
        "sources": [{"kind": "model", "item_id": llm.TEXT_MODEL, "title": "DashScope 文本大模型"}],
        "model": llm.TEXT_MODEL,
    }


def _run_chat(payload: dict, image_path: str = ""):
    started_at = perf_counter()
    text = str(payload.get("text", "") or "").strip()
    mode = str(payload.get("mode", "text") or "text").strip()
    image_label = str(payload.get("image_label", "") or "").strip()
    user_id = str(payload.get("user_id", "") or "").strip() or DEFAULT_USER_ID

    route_result = route(text=text, mode=mode, image_label=image_label)
    agent = str(route_result["agent"])
    intent = str(route_result["intent"])
    confidence = float(route_result["confidence"])

    agent_context = ctx_service.get_raw_context(user_id)
    agent_context["image_label"] = image_label
    agent_context["image_path"] = image_path
    agent_context["mode"] = mode

    handler = AGENT_HANDLERS.get(agent)
    if handler is not None:
        try:
            result = _normalize_agent_result(handler(text, agent_context))
            return jsonify(_response_payload(started_at, user_id, text, mode, image_label, route_result, result))
        except Exception as exc:
            result = {
                "agent": agent,
                "agent_meta": AGENT_META.get(agent, AGENT_META["scheduler"]),
                "intent": intent,
                "confidence": confidence,
                "hit": False,
                "reply": build_reply(agent, text, image_label),
                "steps": build_steps(AGENT_META.get(agent, AGENT_META["scheduler"])["name"], intent, confidence),
                "sources": [],
                "error": str(exc),
            }
            return jsonify(_response_payload(started_at, user_id, text, mode, image_label, route_result, result))

    result = _general_llm_result(text, agent_context)
    if result is not None:
        return jsonify(_response_payload(started_at, user_id, text, mode, image_label, route_result, result))

    result = {
        "agent": agent,
        "agent_meta": AGENT_META.get(agent, AGENT_META["scheduler"]),
        "intent": intent,
        "confidence": confidence,
        "hit": False,
        "reply": build_reply(agent, text, image_label),
        "steps": build_steps(AGENT_META.get(agent, AGENT_META["scheduler"])["name"], intent, confidence),
        "sources": [],
    }
    return jsonify(_response_payload(started_at, user_id, text, mode, image_label, route_result, result))


@chat_bp.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    return _run_chat(data)


@chat_bp.post("/api/chat/image")
def chat_image():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"ok": False, "error": "未收到图片文件（字段名应为 file）"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        ext = ".jpg"

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        file.save(tmp_path)
        payload = {
            "user_id": request.form.get("user_id", DEFAULT_USER_ID),
            "text": request.form.get("text", ""),
            "mode": "image",
            "image_label": request.form.get("image_label", ""),
        }
        return _run_chat(payload, image_path=tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
