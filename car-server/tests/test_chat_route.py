# tests/test_chat_route.py —— /api/chat 端到端 + 输出归一化（A-T1/A-T2/A-T5）

import routes.chat as chat_route
from routes.chat import _normalize_agent_result


# ---- 归一化函数（A-T2）：确定性单测 -----------------------------------------

def test_normalize_maps_miss_status_to_pending():
    raw = {"steps": [{"name": "检索", "status": "miss", "detail": "未命中"}]}
    out = _normalize_agent_result(raw)
    assert out["steps"][0]["status"] == "pending"
    assert out["steps"][0]["detail"] == "未命中"  # 保留说明


def test_normalize_maps_good_block_to_kv_good():
    raw = {"reply": {"blocks": [{"type": "good", "text": "报价在合理区间"}]}}
    out = _normalize_agent_result(raw)
    b = out["reply"]["blocks"][0]
    assert b["type"] == "kv"
    assert b["good"] is True
    assert b["value"] == "报价在合理区间"


# ---- HTTP 全链路 -----------------------------------------------------------

def _valid_step_statuses(steps):
    return all(s["status"] in {"done", "doing", "pending", "todo"} for s in steps)


def _no_good_block(reply):
    return all(b.get("type") != "good" for b in reply["blocks"])


def test_chat_response_shape_and_normalization_invariant(client):
    # 覆盖四类意图 + 兜底，断言归一化不变量对所有响应都成立
    inputs = [
        {"text": "P0300 是什么意思"},
        {"text": "发动机咕噜咕噜响"},
        {"text": "800 换机油机滤合理吗"},
        {"text": "拍报价单", "mode": "image", "image_label": "报价单"},
        {"text": "今天天气怎么样"},
        {"text": "P9999 没收录的码"},
    ]
    for payload in inputs:
        resp = client.post("/api/chat", json=payload)
        assert resp.status_code == 200, payload
        data = resp.get_json()
        for key in ("route", "agent", "agent_meta", "hit", "reply", "steps",
                    "sources", "consultation_id", "elapsed_ms", "legal_note"):
            assert key in data, (key, payload)
        assert data["consultation_id"].startswith("c_")
        assert isinstance(data["sources"], list), payload
        assert _valid_step_statuses(data["steps"]), payload
        assert _no_good_block(data["reply"]), payload


def test_chat_dtc_returns_saveable_source(client):
    resp = client.post("/api/chat", json={"text": "P0300 是什么意思", "user_id": "u_source"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["consultation_id"].startswith("c_")
    assert data["sources"] == [
        {"kind": "dtc", "item_id": "P0300", "title": "发动机缺火（随机/多缸）"}
    ]


def test_chat_fallback_always_runs(client):
    # 无意义输入 → scheduler 兜底，hit=false，但仍 200 且 reply 非空（永远能跑）
    resp = client.post("/api/chat", json={"text": "嗯哼哈"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["agent"] == "scheduler"
    assert data["hit"] is False
    assert data["reply"]["blocks"]


def test_chat_agent_exception_fallback_is_not_a_hit(client, monkeypatch):
    def boom(_text, _context):
        raise RuntimeError("agent exploded")

    monkeypatch.setitem(chat_route.AGENT_HANDLERS, "dtc", boom)
    resp = client.post("/api/chat", json={"text": "P0300 是什么意思"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["agent"] == "dtc"
    assert data["hit"] is False
    assert data["reply"]["title"] == "暂时无法完成分析"


def test_chat_quote_sinks_receipt(client):
    # A-T5 / I-006：报价诊断后，receipt 能查到沉淀项，total>0
    uid = "u_chat_receipt"
    chat = client.post("/api/chat", json={"text": "800 换机油机滤合理吗", "user_id": uid})
    assert chat.status_code == 200
    assert chat.get_json()["hit"] is True

    receipt = client.post("/api/receipt", json={"user_id": uid})
    assert receipt.status_code == 200
    rdata = receipt.get_json()
    assert rdata["receipt_id"].startswith("r_")
    assert rdata["items"], "诊断后应有沉淀维修项"
    assert rdata["total"] > 0


def test_chat_legal_note_present(client):
    # I-008：任意 AI 回复都带合规免责声明
    resp = client.post("/api/chat", json={"text": "P0300"})
    assert "仅供参考" in resp.get_json()["legal_note"]
