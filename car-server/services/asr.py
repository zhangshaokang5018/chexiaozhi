# services/asr.py —— 语音转文字（ASR）服务
#
# 对外主入口：transcribe(audio_path: str) -> dict
#   返回 {"text": str, "simulated": bool, "model": str, "error": str|None}
#
# 真实调用要求：每次识别前从 MySQL model_api_keys 读取 dashscope Key。
# 没有 Key / 调用失败时返回明确错误，不再生成演示占位文本。

import os
from typing import Optional, TypedDict

from services import model_keys
from services.secret_utils import redact_secret

ASR_MODEL = os.environ.get("ASR_MODEL", "paraformer-realtime-v2")

# 录音格式 → paraformer format 参数
_EXT_FORMAT = {".wav": "wav", ".mp3": "mp3", ".pcm": "pcm", ".aac": "aac", ".m4a": "m4a", ".amr": "amr"}


def detect_audio_format(audio_path: str) -> str:
    """Infer DashScope ASR format from file header first, then extension."""
    try:
        with open(audio_path, "rb") as f:
            header = f.read(16)
    except OSError:
        header = b""

    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "wav"
    if header.startswith(b"ID3") or header[:2] == b"\xff\xfb" or header[:2] == b"\xff\xf3" or header[:2] == b"\xff\xf2":
        return "mp3"
    if header.startswith(b"#!AMR"):
        return "amr"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "m4a"
    if header.startswith(b"ADIF") or header[:2] == b"\xff\xf1" or header[:2] == b"\xff\xf9":
        return "aac"
    return _guess_format(audio_path)


def has_api_key() -> bool:
    """数据库中是否启用了阿里云 DashScope API Key。"""
    return bool(model_keys.get_api_key())


def _guess_format(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[1].lower()
    return _EXT_FORMAT.get(ext, "mp3")


def _extract_sentence_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"].strip()
        sentences = value.get("sentences") or value.get("sentence") or value.get("output")
        return _extract_sentence_text(sentences)
    if isinstance(value, list):
        return "".join(_extract_sentence_text(item) for item in value).strip()
    return ""


def _transcribe_with_dashscope(audio_path: str, api_key: str) -> dict:
    """调用阿里云百炼 paraformer 做真实语音识别。失败时抛异常。"""
    from dashscope.audio.asr import Recognition

    recognition = Recognition(
        model=ASR_MODEL,
        format=detect_audio_format(audio_path),
        sample_rate=16000,
        api_key=api_key,
        callback=None,
    )
    result = recognition.call(file=audio_path)

    # 兼容 SDK 不同返回结构：拼接所有句子的 text
    text = ""
    try:
        text = _extract_sentence_text(result.get_sentence())
    except Exception:
        text = ""
    if not text:
        text = _extract_sentence_text(getattr(result, "output", None))
    if not text:
        text = _extract_sentence_text(getattr(result, "message", None))
    return {"text": text, "simulated": False, "model": ASR_MODEL, "error": None}


def transcribe(audio_path: str) -> dict:
    """语音转文字主入口。只返回真实识别结果或明确错误。"""
    if not audio_path or not os.path.exists(audio_path):
        return {"text": "", "simulated": False, "model": "none", "error": "音频文件不存在"}

    api_key = model_keys.get_api_key()
    if not api_key:
        return {"text": "", "simulated": False, "model": ASR_MODEL, "error": "数据库未配置 dashscope API Key"}

    try:
        out = _transcribe_with_dashscope(audio_path, api_key)
        if out["text"]:
            return out
        return {"text": "", "simulated": False, "model": ASR_MODEL, "error": "识别结果为空，请换一段清晰语音重试"}
    except Exception as e:
        return {"text": "", "simulated": False, "model": ASR_MODEL, "error": redact_secret(e)}


# ===================== LangGraph 节点封装（统一在图上管理） =====================

class AsrState(TypedDict, total=False):
    audio_path: str    # 输入：音频文件路径
    text: str          # 输出：转写文本
    simulated: bool    # 输出：兼容字段，真实调用中为 False
    asr_error: Optional[str]


def make_transcribe_node(audio_key: str = "audio_path", out_key: str = "text"):
    """生成一个 LangGraph 语音转写节点：读 state[audio_key] → 写 state[out_key] 等。"""
    def _node(state: dict) -> dict:
        out = transcribe(state.get(audio_key, ""))
        return {out_key: out["text"], "simulated": out["simulated"], "asr_error": out["error"]}

    return _node


_asr_graph = None


def build_asr_graph():
    """把 ASR 编译成一张独立的 LangGraph 图（START→transcribe→END），可单独 invoke。"""
    global _asr_graph
    if _asr_graph is None:
        from langgraph.graph import StateGraph, START, END

        g = StateGraph(AsrState)
        g.add_node("transcribe", make_transcribe_node())
        g.add_edge(START, "transcribe")
        g.add_edge("transcribe", END)
        _asr_graph = g.compile()
    return _asr_graph
