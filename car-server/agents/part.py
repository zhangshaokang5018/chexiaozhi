"""Image / part recognition Agent backed by DashScope vision."""

from __future__ import annotations

from services import vision

INTENT = "图像识别/零件匹配"
AGENT_META = {"name": "零件识别 Agent", "desc": "图像/名称匹配"}


def _missing_image_result() -> dict:
    return {
        "agent": "part",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.0,
        "hit": False,
        "reply": {
            "title": "请上传图片",
            "summary": "图片识别需要真实图片文件，不能只靠标签完成。",
            "blocks": [{"type": "warn", "text": "请重新拍摄或从相册选择报价单、零件、仪表盘等图片。"}],
            "price_text": "",
            "price_range": [],
        },
        "steps": [
            {"name": "意图识别", "status": "done", "detail": f"{INTENT}（95%）"},
            {"name": "分发至 零件识别 Agent", "status": "done"},
            {"name": "DashScope 视觉识别", "status": "pending", "detail": "缺少图片文件"},
            {"name": "合成回复", "status": "done"},
        ],
        "sources": [],
    }


def handle(text: str, context=None) -> dict:
    """Analyze an uploaded vehicle image through the vision service."""
    context = context or {}
    image_path = str(context.get("image_path", "") or "").strip()
    image_label = str(context.get("image_label", "") or "").strip()
    if not image_path:
        return _missing_image_result()
    return vision.analyze_vehicle_image(
        image_path=image_path,
        image_label=image_label,
        text=text or "",
        context=context,
    )
