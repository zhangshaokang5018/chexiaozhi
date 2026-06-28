"""Minimal real DashScope smoke tests using the DB-backed key.

The script checks:
  1. Text model with one short prompt.
  2. Vision model with a tiny generated image.
  3. ASR model with a very short generated WAV to verify transport/permission.

It never prints the API key.
"""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import asr, llm, model_keys, vision  # noqa: E402


def _make_test_png(path: Path) -> None:
    width, height = 240, 120
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            border = x in (20, 21, 218, 219) or y in (30, 31, 88, 89)
            stripe = 45 <= y <= 75 and (x // 8) % 2 == 0 and 50 <= x <= 190
            if border or stripe:
                row.extend((20, 20, 20))
            else:
                row.extend((245, 245, 245))
        rows.append(b"\x00" + bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _make_test_wav(path: Path) -> None:
    sample_rate = 16000
    duration_sec = 0.6
    frames = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(frames):
            value = 0 if i % 2 == 0 else 800
            wav.writeframes(struct.pack("<h", value))


def check_text() -> tuple[bool, str]:
    reply = llm.generate_text(
        [
            {"role": "system", "content": "你只用一句中文回答。"},
            {"role": "user", "content": "汽车机油主要起什么作用？"},
        ],
        model=os.environ.get("DASHSCOPE_TEXT_MODEL", llm.TEXT_MODEL),
        temperature=0.1,
    )
    return bool(reply), reply[:80]


def check_vision(tmp_dir: Path) -> tuple[bool, str]:
    image_path = tmp_dir / "dashscope_vision_test.png"
    _make_test_png(image_path)
    result = vision.analyze_vehicle_image(str(image_path), "零件", "请用一句话识别这张测试图", {})
    ok = bool(result.get("hit"))
    summary = (result.get("reply") or {}).get("summary") or result.get("error") or ""
    return ok, str(summary)[:120]


def check_asr(tmp_dir: Path) -> tuple[bool, str]:
    audio_path = tmp_dir / "dashscope_asr_test.wav"
    _make_test_wav(audio_path)
    result = asr.transcribe(str(audio_path))
    if result.get("text"):
        return True, str(result["text"])[:80]
    if result.get("error") == "识别结果为空，请换一段清晰语音重试":
        return True, "ASR model reachable; generated test audio has no recognizable speech."
    return False, str(result.get("error") or "ASR returned no text")[:160]


def _run_check(name: str, fn) -> bool:
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, str(exc)
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {status} - {detail}")
    return ok


def main() -> int:
    if not model_keys.get_api_key():
        print("FAIL - no enabled dashscope key found in MySQL model_api_keys.")
        return 2

    with tempfile.TemporaryDirectory(prefix="cxz_dashscope_check_") as tmp:
        tmp_dir = Path(tmp)
        results = [
            _run_check("text", check_text),
            _run_check("vision", lambda: check_vision(tmp_dir)),
            _run_check("asr", lambda: check_asr(tmp_dir)),
        ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
