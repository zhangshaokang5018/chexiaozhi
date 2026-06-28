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
from time import perf_counter

from flask import Blueprint, jsonify, request

from agents import dtc, maintain, part, symptom
from agents.scheduler import route
from services import context as ctx_service

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


def build_steps(agent_name: str, intent: str, confidence: float):
    confidence_text = f"{round(confidence * 100)}%"
    return [
        {"name": "意图识别", "status": "done", "detail": f"{intent}（{confidence_text}）"},
        {"name": f"分发至 {agent_name}", "status": "done"},
        {"name": "知识库检索", "status": "done"},
        {"name": "合成回复", "status": "done"},
    ]


def build_reply(agent: str, text: str, image_label: str):
    """占位/兜底文案：仅在 scheduler 兜底或智能体异常时使用。"""
    if agent == "scheduler":
        return {
            "title": "需要补充信息",
            "summary": "我还需要更具体的车辆症状、故障码、报价项目或图片类型。",
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


@chat_bp.post("/api/chat")
def chat():
    started_at = perf_counter()
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "") or "").strip()
    mode = str(data.get("mode", "text") or "text").strip()
    image_label = str(data.get("image_label", "") or "").strip()
    user_id = str(data.get("user_id", "") or "").strip() or DEFAULT_USER_ID

    route_result = route(text=text, mode=mode, image_label=image_label)
    agent = str(route_result["agent"])
    intent = str(route_result["intent"])
    confidence = float(route_result["confidence"])

    handler = AGENT_HANDLERS.get(agent)
    if handler is not None:
        try:
            # 车辆上下文（A-T5）：get_raw_context 返回深拷贝，可安全注入运行参数
            agent_context = ctx_service.get_raw_context(user_id)
            agent_context["image_label"] = image_label
            agent_context["mode"] = mode

            result = _normalize_agent_result(handler(text, agent_context))

            # 用智能体真实返回覆盖占位
            reply = result.get("reply") or build_reply(agent, text, image_label)
            steps = result.get("steps") or build_steps(AGENT_META[agent]["name"], intent, confidence)
            hit = bool(result.get("hit", agent != "scheduler"))
            agent_meta = result.get("agent_meta") or AGENT_META.get(agent, AGENT_META["scheduler"])
            confidence = float(result.get("confidence", confidence))
            intent = str(result.get("intent", intent))

            # 命中且带 receipt_item → 沉淀到 context（A-T5）
            receipt_item = result.get("receipt_item")
            if hit and isinstance(receipt_item, dict):
                ctx_service.add_receipt_item(user_id, receipt_item)

            elapsed_ms = int((perf_counter() - started_at) * 1000)
            return jsonify({
                "route": {"agent": agent, "intent": intent, "confidence": confidence},
                "agent": agent,
                "agent_meta": agent_meta,
                "hit": hit,
                "reply": reply,
                "steps": steps,
                "elapsed_ms": elapsed_ms,
                "legal_note": LEGAL_NOTE,
            })
        except Exception as exc:  # 智能体异常 → 回退占位，保证永远能跑
            print(f"[chat] agent={agent} handle 异常，回退占位: {exc}")

    # scheduler 兜底 / 智能体异常回退
    agent_meta = AGENT_META.get(agent, AGENT_META["scheduler"])
    elapsed_ms = int((perf_counter() - started_at) * 1000)
    return jsonify({
        "route": route_result,
        "agent": agent,
        "agent_meta": agent_meta,
        "hit": False,
        "reply": build_reply(agent, text, image_label),
        "steps": build_steps(agent_meta["name"], intent, confidence),
        "elapsed_ms": elapsed_ms,
        "legal_note": LEGAL_NOTE,
    })
