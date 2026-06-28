# tests/test_services_and_routes.py —— 后端通用接口/服务
# 覆盖：/api/ping、context+VIN 脱敏、/api/context、/api/kb 分页与详情、/api/asr 契约

import io
from contextlib import contextmanager
from urllib.parse import quote

from services import context as ctx_service
from services import asr as asr_service


# ---- 健康检查（I-001） -----------------------------------------------------

def test_ping(client):
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["name"] == "chexiaozhi-server"


# ---- VIN 脱敏 + 默认上下文 -------------------------------------------------

def test_mask_vin_keeps_head_tail():
    masked = ctx_service.mask_vin("LFMAP22CXXX123456")
    assert masked.startswith("LFMA")
    assert masked.endswith("3456")
    assert "*" in masked
    assert len(masked) == len("LFMAP22CXXX123456")


def test_get_context_masks_vin_but_raw_does_not():
    uid = "u_ctx"
    ctx = ctx_service.get_context(uid)
    raw = ctx_service.get_raw_context(uid)
    assert "*" in ctx["vin"]
    assert "*" not in raw["vin"]


def test_context_get_post_roundtrip(client):
    uid = "u_ctx"
    # POST 更新 location → GET 能读到新值
    post = client.post("/api/context", json={"user_id": uid, "location": "深圳"})
    assert post.status_code == 200
    assert post.get_json()["ok"] is True

    get = client.get("/api/context", query_string={"user_id": uid})
    assert get.status_code == 200
    assert get.get_json()["location"] == "深圳"


def test_context_prefers_mysql_vehicle(monkeypatch, client):
    uid = "u_mysql_ctx"
    ctx_service.update_context(
        uid,
        {
            "car_model": "内存里的旧车",
            "vin": "MEMORYVIN1234567",
            "mileage": "1 km",
            "location": "内存城市",
        },
    )
    state = {
        "users": {uid: {"user_id": uid}},
        "user_vehicle": {
            uid: {
                "user_id": uid,
                "car_model": "2024款 比亚迪 宋PLUS DM-i",
                "vin": "LGXCG6DF9R1234567",
                "mileage": "12,000 km",
                "location": "上海",
            }
        },
    }

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=None):
            normalized = " ".join(sql.strip().split()).lower()
            params = params or ()
            self._one = None
            if normalized.startswith("select * from users where user_id="):
                self._one = state["users"].get(params[0])
                return 1 if self._one else 0
            if normalized.startswith("insert ignore into user_vehicle"):
                state["user_vehicle"].setdefault(
                    params[0],
                    {"user_id": params[0], "car_model": "", "vin": "", "mileage": "", "location": ""},
                )
                return 1
            if normalized.startswith("select * from user_vehicle where user_id="):
                self._one = state["user_vehicle"].get(params[0])
                return 1 if self._one else 0
            if normalized.startswith("update user_vehicle set"):
                values = list(params)
                user_id = values.pop()
                for assignment, value in zip(normalized.split(" set ", 1)[1].split(" where ", 1)[0].split(","), values):
                    key = assignment.split("=", 1)[0].strip()
                    state["user_vehicle"][user_id][key] = value
                return 1
            raise AssertionError(f"Unhandled SQL in fake context DB: {sql}")

        def fetchone(self):
            return self._one

    class Conn:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    @contextmanager
    def fake_connection():
        yield Conn()

    monkeypatch.setattr(ctx_service, "get_connection", fake_connection)

    get = client.get("/api/context", query_string={"user_id": uid})
    assert get.status_code == 200
    data = get.get_json()
    assert data["car_model"] == "2024款 比亚迪 宋PLUS DM-i"
    assert data["location"] == "上海"
    assert data["vin"].startswith("LGXC")
    assert data["vin"].endswith("4567")
    assert "*" in data["vin"]

    post = client.post("/api/context", json={"user_id": uid, "location": "杭州"})
    assert post.status_code == 200
    assert post.get_json()["context"]["location"] == "杭州"
    assert ctx_service.get_raw_context(uid)["vin"] == "LGXCG6DF9R1234567"


# ---- 知识库分页与详情（A-T10） --------------------------------------------

def test_kb_pagination(client):
    resp = client.get("/api/kb/dtc", query_string={"page": 1, "page_size": 4})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["page"] == 1
    assert data["page_size"] == 4
    assert data["count"] == min(4, data["total"])
    assert data["total"] >= 5  # kb_dtc 至少 5 条
    assert len(data["items"]) == data["count"]


def test_kb_detail_by_code(client):
    resp = client.get("/api/kb/dtc/P0300")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "P0300"
    assert data["kind"] == "dtc"


def test_kb_detail_allows_slash_in_item_id(client):
    item_id = "咕噜咕噜 / 呼噜声 / 异响"
    resp = client.get(f"/api/kb/symptom/{item_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == item_id
    assert data["kind"] == "symptom"

    encoded = quote(item_id, safe="")
    encoded_resp = client.get(f"/api/kb/symptom/{encoded}")
    assert encoded_resp.status_code == 200
    assert encoded_resp.get_json()["id"] == item_id


def test_kb_unknown_kind_404(client):
    resp = client.get("/api/kb/notexist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_kb_detail_not_found_404(client):
    resp = client.get("/api/kb/dtc/P0000")
    assert resp.status_code == 404


# ---- ASR 真实服务契约 -------------------------------------------------------

def test_asr_returns_transcribed_text_when_service_succeeds(monkeypatch, client):
    def fake_transcribe(_path):
        return {"text": "发动机怠速异响", "simulated": False, "model": "paraformer-realtime-v2", "error": None}

    monkeypatch.setattr("routes.asr.asr.transcribe", fake_transcribe)
    data = {"file": (io.BytesIO(b"fake-audio-bytes"), "voice.mp3")}
    resp = client.post("/api/asr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["text"] == "发动机怠速异响"
    assert body["simulated"] is False


def test_asr_error_is_not_fake_success(monkeypatch, client):
    def fake_transcribe(_path):
        return {"text": "", "simulated": False, "model": "paraformer-realtime-v2", "error": "数据库未配置 dashscope API Key"}

    monkeypatch.setattr("routes.asr.asr.transcribe", fake_transcribe)
    data = {"file": (io.BytesIO(b"fake-audio-bytes"), "voice.mp3")}
    resp = client.post("/api/asr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["ok"] is False
    assert body["text"] == ""
    assert body["error"] == "数据库未配置 dashscope API Key"


def test_asr_detects_audio_format_from_header(tmp_path):
    samples = {
        "wav": b"RIFF\x24\x00\x00\x00WAVEfmt ",
        "mp3": b"ID3\x04\x00\x00\x00\x00\x00\x21",
        "m4a": b"\x00\x00\x00\x18ftypM4A ",
        "amr": b"#!AMR\n",
    }
    for expected, content in samples.items():
        audio = tmp_path / f"voice-{expected}.tmp"
        audio.write_bytes(content)
        assert asr_service.detect_audio_format(str(audio)) == expected


def test_asr_extracts_text_from_dashscope_shapes():
    assert asr_service._extract_sentence_text([{"text": "发动机"}, {"text": "异响"}]) == "发动机异响"
    assert asr_service._extract_sentence_text({"sentences": [{"text": "刹车"}, {"text": "异响"}]}) == "刹车异响"
    assert asr_service._extract_sentence_text({"text": "水温高"}) == "水温高"


def test_asr_missing_file_400(client):
    resp = client.post("/api/asr", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
