# tests/test_services_and_routes.py —— A 的其余接口/服务
# 覆盖：/api/ping、context+VIN 脱敏、/api/context、/api/kb 分页与详情、/api/asr 降级

import io

from services import context as ctx_service


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


def test_kb_unknown_kind_404(client):
    resp = client.get("/api/kb/notexist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_kb_detail_not_found_404(client):
    resp = client.get("/api/kb/dtc/P0000")
    assert resp.status_code == 404


# ---- ASR 降级（无 Key 仍能跑） ---------------------------------------------

def test_asr_degraded_returns_text(client):
    data = {"file": (io.BytesIO(b"fake-audio-bytes"), "voice.mp3")}
    resp = client.post("/api/asr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert isinstance(body["text"], str) and body["text"]  # 文本非空（降级占位或真实识别）


def test_asr_missing_file_400(client):
    resp = client.post("/api/asr", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
