"""Intent scheduler for the chat flow."""

import re
from typing import Dict


DTC_PATTERN = re.compile(r"(?<![A-Za-z0-9])[PBC]\d{4}(?![A-Za-z0-9])", re.IGNORECASE)
MAINTAIN_KEYWORDS = ("报价", "费用", "价格", "多少钱", "合理", "贵", "保养")
SYMPTOM_KEYWORDS = ("响", "抖", "顿挫", "报警", "灯亮", "水温", "机油", "刹车", "转向")


def route(text: str, mode: str = "text", image_label: str = "") -> Dict[str, object]:
    """Route user input to the target Agent using the stage-1 rule table."""
    content = f"{text or ''} {image_label or ''}".strip()

    if mode == "image":
        return {"agent": "part", "intent": "图像识别/零件匹配", "confidence": 0.95}

    if DTC_PATTERN.search(content):
        return {"agent": "dtc", "intent": "故障码解读", "confidence": 0.92}

    if any(keyword in content for keyword in MAINTAIN_KEYWORDS):
        return {"agent": "maintain", "intent": "保养建议/报价审核", "confidence": 0.9}

    if any(keyword in content for keyword in SYMPTOM_KEYWORDS):
        return {"agent": "symptom", "intent": "症状分析", "confidence": 0.86}

    return {"agent": "scheduler", "intent": "综合咨询/需补充信息", "confidence": 0.55}
