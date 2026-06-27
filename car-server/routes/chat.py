# routes/chat.py —— 【A 角色负责】对话主入口 /api/chat
#
# 当前为占位实现(stub)，目的是让接口先通、A 的前端能联调。
# A 角色 TODO：
#   1. 调用 agents/scheduler.py 做意图路由（见总文档 7.1）
#   2. 按 route.agent 分发到 symptom/dtc/part（A）或 maintain（B）
#   3. 按总文档 6.1 组装真实的 route/agent_meta/reply/steps 返回
#
# 注意：只改本文件 + agents/ 下你负责的文件，不要改 app.py。

from flask import Blueprint, request, jsonify

chat_bp = Blueprint("chat", __name__)

LEGAL_NOTE = "所有建议仅供参考，请以当地授权维修点为准。"


@chat_bp.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    mode = data.get("mode", "text")

    # ===== 占位返回（A 接入调度后替换为真实逻辑）=====
    return jsonify(
        {
            "route": {"agent": "scheduler", "intent": "待实现（占位）", "confidence": 0.0},
            "agent": "scheduler",
            "agent_meta": {"name": "调度 Agent（占位）", "desc": "A 角色待实现"},
            "hit": False,
            "reply": {
                "title": "占位回复",
                "summary": f"已收到输入：{text}（mode={mode}）",
                "blocks": [
                    {"type": "warn", "text": "这是 /api/chat 占位实现，A 角色待接入调度与诊断 Agent。"}
                ],
                "price_text": "",
                "price_range": [],
            },
            "steps": [
                {"name": "意图识别", "status": "todo"},
                {"name": "分发至 Agent", "status": "todo"},
                {"name": "知识库检索", "status": "todo"},
                {"name": "合成回复", "status": "todo"},
            ],
            "elapsed_ms": 0,
            "legal_note": LEGAL_NOTE,
            "_stub": True,
        }
    )
