"""DashScope text model helpers.

The API key is fetched from MySQL for every model call. The local KB/RAG result
is treated as evidence, and the model is asked to rewrite it without inventing
new prices or diagnosis facts.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from http import HTTPStatus
from typing import Any

from services import model_keys

TEXT_MODEL = os.environ.get("DASHSCOPE_TEXT_MODEL", "qwen-plus")


class ModelKeyMissing(RuntimeError):
    """Raised when no enabled DashScope key is available in MySQL."""


class DashScopeCallError(RuntimeError):
    """Raised when DashScope returns an error or an unusable response."""


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _raise_for_dashscope_error(response: Any) -> None:
    status_code = _get(response, "status_code")
    if status_code in (None, HTTPStatus.OK, 200):
        return

    code = _get(response, "code", "") or ""
    message = _get(response, "message", "") or "DashScope 调用失败"
    raise DashScopeCallError(f"{code}: {message}".strip(": "))


def _extract_message_text(response: Any) -> str:
    output = _get(response, "output", {}) or {}
    text = _get(output, "text", "")
    if text:
        return str(text).strip()

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
            return "".join(parts).strip()

    raise DashScopeCallError("DashScope 响应中没有可用文本")


def generate_text(messages: list[dict], model: str | None = None, temperature: float = 0.2) -> str:
    """Call DashScope Generation with a DB-backed key."""
    api_key = model_keys.get_api_key()
    if not api_key:
        raise ModelKeyMissing("数据库未配置 dashscope API Key")

    import dashscope

    response = dashscope.Generation.call(
        model=model or TEXT_MODEL,
        api_key=api_key,
        messages=messages,
        result_format="message",
        temperature=temperature,
    )
    _raise_for_dashscope_error(response)
    return _extract_message_text(response)


def _extract_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _valid_block(block: Any) -> dict | None:
    if not isinstance(block, dict):
        return None
    kind = str(block.get("type", "kv") or "kv").lower()
    if kind not in {"kv", "warn", "danger"}:
        if kind in {"warning", "notice", "tip"}:
            kind = "warn"
        else:
            kind = "kv"
    out = {"type": kind}
    if kind == "kv":
        out["label"] = str(block.get("label", block.get("key", block.get("name", ""))) or "")[:40]
        out["value"] = str(block.get("value", block.get("text", block.get("content", ""))) or "")[:500]
        if not out["label"] or not out["value"]:
            return None
    else:
        out["text"] = str(block.get("text", block.get("value", block.get("content", ""))) or "")[:500]
        if not out["text"]:
            return None
    return out


def _coerce_reply(candidate: dict, fallback_reply: dict) -> dict | None:
    title = str(candidate.get("title", "") or "").strip()
    summary = str(candidate.get("summary", "") or "").strip()
    blocks = [_valid_block(block) for block in candidate.get("blocks", [])]
    blocks = [block for block in blocks if block]

    if not title or not summary:
        return None
    if not blocks:
        fallback_blocks = fallback_reply.get("blocks", [])
        blocks = [_valid_block(block) for block in fallback_blocks]
        blocks = [block for block in blocks if block]
    if not blocks:
        blocks = [{"type": "warn", "text": summary[:500]}]

    price_range = candidate.get("price_range", fallback_reply.get("price_range", []))
    if not isinstance(price_range, list):
        price_range = fallback_reply.get("price_range", [])

    return {
        "title": title[:80],
        "summary": summary[:240],
        "blocks": blocks,
        "price_text": str(candidate.get("price_text", fallback_reply.get("price_text", "")) or "")[:160],
        "price_range": price_range,
    }


def _mark_synthesis_step(result: dict, detail: str) -> None:
    steps = result.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and "合成回复" in str(step.get("name", "")):
            step["detail"] = detail
            return


def enhance_agent_result(agent: str, user_text: str, context: dict | None, result: dict) -> dict:
    """Use DashScope to synthesize a hit result, preserving KB evidence fields."""
    if os.environ.get("CXZ_DISABLE_LLM") == "1":
        return result
    if not isinstance(result, dict) or not result.get("hit"):
        return result

    output = deepcopy(result)
    fallback_reply = output.get("reply") or {}
    evidence = {
        "agent": agent,
        "question": user_text,
        "vehicle_context": context or {},
        "reply_from_kb": fallback_reply,
        "sources": output.get("sources", []),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是车小智汽车售后诊断助手。你必须只依据给定 evidence 回答，"
                "不得新增未给出的价格、故障原因或维修项目。"
                "只返回 JSON，字段为 title、summary、blocks、price_text、price_range。"
                "blocks 每项 type 只能是 kv/warn/danger；kv 需要 label/value，warn/danger 需要 text。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(evidence, ensure_ascii=False),
        },
    ]

    try:
        text = generate_text(messages, model=TEXT_MODEL, temperature=0.15)
        candidate = _extract_json_object(text)
        reply = _coerce_reply(candidate or {}, fallback_reply)
        if reply:
            output["reply"] = reply
            output["model"] = TEXT_MODEL
            _mark_synthesis_step(output, f"DashScope {TEXT_MODEL}")
            return output
    except Exception:
        pass

    _mark_synthesis_step(output, "大模型合成未完成，已返回知识库结果")
    return output


def generate_general_vehicle_reply(user_text: str, context: dict | None) -> dict | None:
    """Answer general automotive questions that do not match a structured agent."""
    if os.environ.get("CXZ_DISABLE_LLM") == "1":
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "你是车小智汽车售后助手。回答必须聚焦汽车使用、维修、保养、报价或故障排查。"
                "如果问题与汽车无关，简短说明只能处理汽车相关问题。"
                "不要编造具体价格；没有依据时提示需要补充车型、里程、故障现象或报价明细。"
                "只返回 JSON，字段为 title、summary、blocks、price_text、price_range。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"question": user_text, "vehicle_context": context or {}},
                ensure_ascii=False,
            ),
        },
    ]
    try:
        text = generate_text(messages, model=TEXT_MODEL, temperature=0.2)
        candidate = _extract_json_object(text)
        return _coerce_reply(candidate or {}, {"price_text": "", "price_range": []})
    except Exception:
        return None
