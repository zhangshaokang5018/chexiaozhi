# services/asr.py —— 语音转文字（ASR）服务
#
# 设计原则（与 services/rag.py 一致：永远能跑 + 预留阿里接入位）：
#   - 有 DASHSCOPE_API_KEY：调阿里云百炼 paraformer 语音模型做真实识别
#   - 无 Key / 调用失败：走“降级转写”，返回可演示的占位文本（simulated=True），
#     保证前端「录音 → 转文字 → 回填输入框」整条链路在没有 Key 时也能跑通、可演示
#
# 同时提供 LangGraph 节点封装（make_transcribe_node / build_asr_graph），
# 让语音转写和 RAG、智能体一样统一在图上管理、可单独 invoke。
#
# 对外主入口：transcribe(audio_path: str) -> dict
#   返回 {"text": str, "simulated": bool, "model": str, "error": str|None}

import os
from typing import Optional, TypedDict

# 阿里云百炼统一 Key（语音/多模态/对话大模型共用），与总文档第 9 节一致
_API_KEY_ENV = "DASHSCOPE_API_KEY"
# 语音识别模型，可用环境变量覆盖；默认 paraformer 实时识别 v2
ASR_MODEL = os.environ.get("ASR_MODEL", "paraformer-realtime-v2")
# 无 Key 时的降级占位转写（带“语音示例”标记，提醒这是未配置 Key 的演示结果）
_FALLBACK_TEXT = os.environ.get("ASR_FALLBACK_TEXT", "发动机怠速时咕噜咕噜响（语音示例）")

# 录音格式 → paraformer format 参数
_EXT_FORMAT = {".wav": "wav", ".mp3": "mp3", ".pcm": "pcm", ".aac": "aac", ".m4a": "m4a"}


def has_api_key() -> bool:
    """是否配置了阿里云 DASHSCOPE_API_KEY。"""
    return bool(os.environ.get(_API_KEY_ENV, "").strip())


def _guess_format(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[1].lower()
    return _EXT_FORMAT.get(ext, "mp3")


def _transcribe_with_dashscope(audio_path: str) -> dict:
    """调用阿里云百炼 paraformer 做真实语音识别。失败时抛异常，由 transcribe 兜底。"""
    import dashscope
    from dashscope.audio.asr import Recognition

    dashscope.api_key = os.environ[_API_KEY_ENV].strip()
    recognition = Recognition(
        model=ASR_MODEL,
        format=_guess_format(audio_path),
        sample_rate=16000,
        callback=None,
    )
    result = recognition.call(file=audio_path)

    # 兼容 SDK 不同返回结构：拼接所有句子的 text
    sentences = []
    try:
        sentences = result.get_sentence() or []
    except Exception:
        sentences = getattr(result, "output", {}) or []
    text = "".join(s.get("text", "") for s in sentences if isinstance(s, dict)).strip()
    return {"text": text, "simulated": False, "model": ASR_MODEL, "error": None}


def transcribe(audio_path: str) -> dict:
    """语音转文字主入口。有 Key 调阿里，无 Key/失败走降级占位，保证永远有返回。"""
    if not audio_path or not os.path.exists(audio_path):
        return {"text": "", "simulated": True, "model": "none", "error": "音频文件不存在"}

    if has_api_key():
        try:
            out = _transcribe_with_dashscope(audio_path)
            if out["text"]:
                return out
            # 真实识别返回空 → 退回占位，避免前端拿到空文本
            return {"text": _FALLBACK_TEXT, "simulated": True, "model": ASR_MODEL,
                    "error": "识别结果为空，已用示例占位"}
        except Exception as e:
            print(f"[asr] 阿里语音识别失败，退回降级占位，原因: {e}")
            return {"text": _FALLBACK_TEXT, "simulated": True, "model": ASR_MODEL, "error": str(e)}

    # 未配置 Key：降级占位（可演示）
    print("[asr] 未配置 DASHSCOPE_API_KEY，返回降级占位转写（配置 Key 后为真实识别）")
    return {"text": _FALLBACK_TEXT, "simulated": True, "model": "fallback",
            "error": "未配置 DASHSCOPE_API_KEY"}


# ===================== LangGraph 节点封装（统一在图上管理） =====================

class AsrState(TypedDict, total=False):
    audio_path: str    # 输入：音频文件路径
    text: str          # 输出：转写文本
    simulated: bool    # 输出：是否降级占位
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
