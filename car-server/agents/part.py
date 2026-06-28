# agents/part.py —— 【A 角色】零件识别 / 图片模式 Agent（MVP 模拟）
#
# 职责（总文档 7 / 05 A-T7）：
#   mode=image 时，按图片标签(image_label)给出结构化的“模拟识别结果” + 核对提示。
#   真实图像识别本期不做，但保持与其他智能体一致的 handle() 契约和结构化输出，
#   方便后续替换为真实视觉模型。
#
# 对外契约（与 maintain/dtc/symptom 一致，见 03 §9）：
#   handle(text, context=None) -> dict
#   context 中可带 image_label（由 chat.py 注入）；价格区间留空（需结合报价单明细）。
#
# 说明：纯本地，不依赖 Flask / 网络 / 模型，永远能跑。

INTENT = "图像识别/零件匹配"
AGENT_META = {"name": "零件识别 Agent", "desc": "图像/名称匹配"}

# 按图片标签给出的结构化模拟参考（演示用）
_LABEL_HINTS = {
    "报价单": [
        {"type": "kv", "label": "识别类型", "value": "维修报价单"},
        {"type": "kv", "label": "建议核对项", "value": "项目名称、配件品牌/型号、工时费、税费、是否含旧件回收。"},
        {"type": "warn", "text": "避坑：把报价单各项发给我做逐项审核，重点核对工时与配件是否虚高。"},
    ],
    "零件": [
        {"type": "kv", "label": "识别类型", "value": "汽车零件"},
        {"type": "kv", "label": "建议核对项", "value": "零件编码(OEM)、品牌、适配车型、生产日期、是否原厂/副厂。"},
        {"type": "warn", "text": "避坑：核对零件包装与实物编码一致，警惕翻新件冒充全新件。"},
    ],
    "仪表盘": [
        {"type": "kv", "label": "识别类型", "value": "仪表盘故障灯"},
        {"type": "kv", "label": "建议核对项", "value": "亮起的指示灯颜色（黄=提示/红=警告）、是否常亮或闪烁。"},
        {"type": "warn", "text": "若为红色警告灯（如机油、水温），建议尽快靠边停车确认安全。"},
    ],
}

_DEFAULT_HINTS = [
    {"type": "kv", "label": "识别类型", "value": "通用图片"},
    {"type": "kv", "label": "建议核对项", "value": "请补充说明图片内容（报价单 / 零件 / 仪表盘灯）以便给出更准确参考。"},
    {"type": "warn", "text": "图片识别结果仅作参考，维修前仍需核对实物型号与报价单明细。"},
]


def _init_steps() -> list:
    return [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（95%）"},
        {"name": "分发至 零件识别 Agent", "status": "done"},
        {"name": "图片模拟识别", "status": "done", "detail": "MVP 模拟"},
        {"name": "合成回复", "status": "done"},
    ]


def handle(text: str, context=None) -> dict:
    """对外入口：按 image_label 输出结构化模拟识别 + 核对提示。"""
    context = context or {}
    label = str(context.get("image_label", "") or "").strip() or text or "报价单"

    blocks = list(_LABEL_HINTS.get(label, _DEFAULT_HINTS))
    blocks.append({
        "type": "warn",
        "text": "本结果为 MVP 阶段模拟识别，维修前请务必核对实物与报价单。",
    })

    return {
        "agent": "part",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.95,
        "hit": True,
        "reply": {
            "title": "图片识别 / 零件匹配",
            "summary": f"已按图片模式识别：{label}",
            "blocks": blocks,
            "price_text": "模拟识别结果，价格需结合报价单明细确认",
            "price_range": [],
        },
        "steps": _init_steps(),
    }
