# routes/chat.py -- 【A 角色负责】对话主入口 /api/chat
#
# 阶段 1：接入调度 Agent，按总文档 6.1 返回统一响应。

from time import perf_counter

from flask import Blueprint, jsonify, request

from agents.scheduler import route

chat_bp = Blueprint("chat", __name__)

LEGAL_NOTE = "所有建议仅供参考，请以当地授权维修点为准。"

AGENT_META = {
    "scheduler": {"name": "调度 Agent", "desc": "综合咨询/需补充信息"},
    "symptom": {"name": "症状分析 Agent", "desc": "异响/抖动/报警判断"},
    "dtc": {"name": "故障码解读 Agent", "desc": "DTC 代码解析"},
    "maintain": {"name": "保养建议 Agent", "desc": "报价/避坑指南"},
    "part": {"name": "零件识别 Agent", "desc": "图像/名称匹配"},
}


def build_steps(agent_name: str, intent: str, confidence: float):
    confidence_text = f"{round(confidence * 100)}%"
    return [
        {"name": "意图识别", "status": "done", "detail": f"{intent}（{confidence_text}）"},
        {"name": f"分发至 {agent_name}", "status": "done"},
        {"name": "知识库检索", "status": "done"},
        {"name": "合成回复", "status": "done"},
    ]


def build_reply(agent: str, text: str, image_label: str):
    if agent == "dtc":
        return {
            "title": "故障码解读",
            "summary": f"已识别到故障码咨询：{text}",
            "blocks": [
                {"type": "kv", "label": "处理方式", "value": "阶段 1 已完成路由，阶段 2 接入 DTC 知识库详情。"},
                {"type": "warn", "text": "如果故障灯闪烁或车辆明显抖动，建议减少行驶并尽快线下检测。"},
            ],
            "price_text": "",
            "price_range": [],
        }

    if agent == "symptom":
        return {
            "title": "症状分析",
            "summary": f"已识别到症状描述：{text}",
            "blocks": [
                {"type": "kv", "label": "处理方式", "value": "阶段 1 已完成路由，阶段 2 接入症状知识库详情。"},
                {"type": "warn", "text": "若伴随高温、红色报警灯或制动异常，建议先停车确认安全。"},
            ],
            "price_text": "",
            "price_range": [],
        }

    if agent == "maintain":
        return {
            "title": "保养建议 / 报价审核",
            "summary": f"已识别到报价/保养咨询：{text}",
            "blocks": [
                {"type": "kv", "label": "处理方式", "value": "已分发到 maintain 意图，后续由 B 的报价审核 Agent 补全。"},
                {"type": "warn", "text": "维修前建议确认项目明细、配件品牌、工时费和质保条款。"},
            ],
            "price_text": "",
            "price_range": [],
        }

    if agent == "part":
        label = image_label or "报价单"
        return {
            "title": "图片识别 / 零件匹配",
            "summary": f"已进入图片模式，图片标签：{label}",
            "blocks": [
                {"type": "kv", "label": "识别类型", "value": label},
                {"type": "kv", "label": "处理方式", "value": "阶段 1 已完成路由，阶段 2 接入零件识别模拟结果。"},
                {"type": "warn", "text": "图片识别结果仅作参考，维修前仍需核对实物型号与报价单。"},
            ],
            "price_text": "",
            "price_range": [],
        }

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


@chat_bp.post("/api/chat")
def chat():
    started_at = perf_counter()
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "") or "").strip()
    mode = str(data.get("mode", "text") or "text").strip()
    image_label = str(data.get("image_label", "") or "").strip()

    route_result = route(text=text, mode=mode, image_label=image_label)
    agent = str(route_result["agent"])
    intent = str(route_result["intent"])
    confidence = float(route_result["confidence"])
    agent_meta = AGENT_META.get(agent, AGENT_META["scheduler"])
    elapsed_ms = int((perf_counter() - started_at) * 1000)

    return jsonify(
        {
            "route": route_result,
            "agent": agent,
            "agent_meta": agent_meta,
            "hit": agent != "scheduler",
            "reply": build_reply(agent, text, image_label),
            "steps": build_steps(agent_meta["name"], intent, confidence),
            "elapsed_ms": elapsed_ms,
            "legal_note": LEGAL_NOTE,
        }
    )
