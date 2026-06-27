# routes/asr.py —— 语音转文字接口 /api/asr
#
# 前端用 wx.uploadFile 以 multipart 上传录音文件（字段名 file），
# 后端保存到临时文件 → 调 services/asr.transcribe → 返回识别文本。
#
# 返回：{ok, text, simulated, model, error}
#   - text：识别出的文字（前端回填到输入框，用户确认后再发 /api/chat）
#   - simulated：True 表示降级占位（未配置 Key 或识别失败），前端可给提示
#
# 注意：本接口不直接出诊断结论，只负责“语音→文字”。文字仍走 /api/chat 的意图路由。

import os
import tempfile

from flask import Blueprint, jsonify, request

from services import asr

asr_bp = Blueprint("asr", __name__)

# 允许的音频后缀（与小程序录音常见格式对齐）
_ALLOWED_EXT = (".mp3", ".wav", ".pcm", ".aac", ".m4a")


@asr_bp.post("/api/asr")
def speech_to_text():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"ok": False, "text": "", "simulated": True,
                        "model": "none", "error": "未收到音频文件（字段名应为 file）"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        ext = ".mp3"  # 小程序默认录音可按 mp3 处理

    tmp_path = None
    try:
        # 保存到临时文件供识别使用
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        file.save(tmp_path)

        result = asr.transcribe(tmp_path)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "text": "", "simulated": True,
                        "model": "none", "error": f"服务端处理失败: {e}"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
