"""DashScope vision model helpers for vehicle image analysis."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from http import HTTPStatus
from pathlib import Path
from typing import Any

from services import model_keys
from services.llm import DashScopeCallError, ModelKeyMissing, _coerce_reply, _extract_json_object

VISION_MODEL = os.environ.get("DASHSCOPE_VISION_MODEL", "qwen-vl-plus")

INTENT = "图像识别/零件匹配"
AGENT_META = {"name": "零件识别 Agent", "desc": "图像/名称匹配"}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _raise_for_dashscope_error(response: Any) -> None:
    status_code = _get(response, "status_code")
    if status_code in (None, HTTPStatus.OK, 200):
        return
    code = _get(response, "code", "") or ""
    message = _get(response, "message", "") or "DashScope 视觉模型调用失败"
    raise DashScopeCallError(f"{code}: {message}".strip(": "))


def _extract_text(response: Any) -> str:
    output = _get(response, "output", {}) or {}
    choices = _get(output, "choices", []) or []
    if choices:
        message = _get(choices[0], "message", {}) or {}
        content = _get(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "") or ""))
                else:
                    parts.append(str(item or ""))
            text = "".join(parts).strip()
            if text:
                return text

    text = _get(output, "text", "")
    if text:
        return str(text).strip()
    raise DashScopeCallError("DashScope 视觉响应中没有可用文本")


def _image_payload(image_path: str) -> str:
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError("图片文件不存在")
    return str(path)


def _base_steps(detail: str) -> list[dict]:
    return [
        {"name": "意图识别", "status": "done", "detail": f"{INTENT}（95%）"},
        {"name": "分发至 零件识别 Agent", "status": "done"},
        {"name": "DashScope 视觉识别", "status": "done", "detail": detail},
        {"name": "合成回复", "status": "done"},
    ]


def _error_result(message: str) -> dict:
    return {
        "agent": "part",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.0,
        "hit": False,
        "reply": {
            "title": "图片识别失败",
            "summary": message,
            "blocks": [{"type": "warn", "text": message}],
            "price_text": "",
            "price_range": [],
        },
        "steps": _base_steps("未完成"),
        "sources": [],
        "model": VISION_MODEL,
        "error": message,
    }


def _fallback_reply(raw_text: str, image_label: str) -> dict:
    label = image_label or "车辆图片"
    return {
        "title": "图片识别 / 零件匹配",
        "summary": raw_text[:220] or f"已识别 {label}",
        "blocks": [
            {"type": "kv", "label": "图片类型", "value": label},
            {"type": "kv", "label": "模型识别", "value": raw_text[:500]},
            {"type": "warn", "text": "维修前请继续核对实物型号、配件编码、报价单项目和工时费。"},
        ],
        "price_text": "",
        "price_range": [],
    }


def analyze_vehicle_image(
    image_path: str,
    image_label: str = "",
    text: str = "",
    context: dict | None = None,
) -> dict:
    """Analyze a vehicle-related image with DashScope Qwen-VL."""
    api_key = model_keys.get_api_key()
    if not api_key:
        return _error_result("数据库未配置 dashscope API Key，无法进行真实图片识别")

    import dashscope

    label = (image_label or "车辆图片").strip()
    prompt = {
        "task": "识别汽车售后相关图片并给维修核对建议",
        "image_label": label,
        "user_text": text or "",
        "vehicle_context": context or {},
        "output_contract": {
            "title": "string",
            "summary": "string",
            "blocks": "array of kv/warn/danger blocks",
            "price_text": "string",
            "price_range": "array, empty if no reliable price",
        },
        "requirements": [
            "只根据图片可见内容和用户文字回答。",
            "如果是报价单，提取可见项目、金额、品牌型号并指出需要核对的点。",
            "如果是零件或仪表盘，识别可见名称/编码/故障灯并给出安全建议。",
            "看不清时明确说明看不清，不要编造。",
            "只返回 JSON。",
        ],
    }
    messages = [
        {
            "role": "user",
            "content": [
                {"image": _image_payload(image_path)},
                {"text": json.dumps(prompt, ensure_ascii=False)},
            ],
        }
    ]

    try:
        response = dashscope.MultiModalConversation.call(
            model=VISION_MODEL,
            api_key=api_key,
            messages=messages,
        )
        _raise_for_dashscope_error(response)
        raw_text = _extract_text(response)
    except (ModelKeyMissing, DashScopeCallError, FileNotFoundError) as exc:
        return _error_result(str(exc))
    except Exception as exc:
        return _error_result(f"DashScope 视觉模型调用失败：{exc}")

    reply = _coerce_reply(_extract_json_object(raw_text) or {}, _fallback_reply(raw_text, label))
    if not reply:
        reply = _fallback_reply(raw_text, label)

    result = {
        "agent": "part",
        "agent_meta": AGENT_META,
        "intent": INTENT,
        "confidence": 0.9,
        "hit": True,
        "reply": reply,
        "steps": _base_steps(f"DashScope {VISION_MODEL}"),
        "sources": [{"kind": "vision", "item_id": VISION_MODEL, "title": label}],
        "model": VISION_MODEL,
    }
    return deepcopy(result)
