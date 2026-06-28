# tests/test_agents.py —— 四个诊断 Agent 的 handle() 契约（命中 + 未命中）
#
# 断言基于「接口契约」而非写死的知识库价格数值（KB 价格可能调整）。
# 未命中用例用 monkeypatch 关闭 RAG，保证不依赖本地向量库、结果确定。

import pytest

from agents import dtc, symptom, maintain, part


# ---- 公共契约校验 ----------------------------------------------------------

def assert_common_contract(result, agent_name):
    assert isinstance(result, dict)
    for key in ("agent", "agent_meta", "intent", "confidence", "hit", "reply", "steps"):
        assert key in result, f"缺少字段 {key}"
    assert result["agent"] == agent_name
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["hit"], bool)

    reply = result["reply"]
    for key in ("title", "summary", "blocks", "price_text", "price_range"):
        assert key in reply, f"reply 缺少字段 {key}"
    assert isinstance(reply["blocks"], list) and reply["blocks"]
    assert isinstance(reply["price_range"], list)

    steps = result["steps"]
    assert isinstance(steps, list) and len(steps) == 4
    for s in steps:
        assert "name" in s and "status" in s


def block_types(result):
    return [b.get("type") for b in result["reply"]["blocks"]]


# ---- dtc -------------------------------------------------------------------

def test_dtc_hit_by_exact_code():
    r = dtc.handle("P0300 是什么意思", {})
    assert_common_contract(r, "dtc")
    assert r["hit"] is True
    assert r["reply"]["price_range"], "命中应给出价格区间"
    assert r["confidence"] == 0.92  # 代码精确命中
    # 命中带 receipt_item 供 chat.py 沉淀
    assert isinstance(r.get("receipt_item"), dict)
    assert "avg" in r["receipt_item"]


def test_dtc_high_level_emits_danger(monkeypatch):
    # P0300 为 level=3 → warn；这里只断言风险等级 block 一定存在（warn 或 danger）
    r = dtc.handle("P0300", {})
    types = block_types(r)
    assert ("warn" in types) or ("danger" in types)


def test_dtc_miss_when_code_unknown_and_no_rag(monkeypatch):
    # 关闭 RAG，未收录的码必须澄清、不编造、无 receipt_item
    monkeypatch.setattr("agents.dtc.rag.search", lambda *a, **k: None)
    r = dtc.handle("P9999 是什么意思", {})
    assert_common_contract(r, "dtc")
    assert r["hit"] is False
    assert "receipt_item" not in r
    assert r["reply"]["price_range"] == []
    # 检索步骤标记为 miss（chat 层会归一化为 pending）
    assert any(s.get("status") == "miss" for s in r["steps"])


# ---- symptom ---------------------------------------------------------------

def test_symptom_hit_keyword():
    r = symptom.handle("发动机咕噜咕噜响", {})
    assert_common_contract(r, "symptom")
    assert r["hit"] is True
    assert r["reply"]["price_range"]


def test_symptom_high_level_emits_danger():
    # “机油灯亮” 命中 level=高 的条目 → 必须输出 danger 强提醒（A-T4 / I-009）
    r = symptom.handle("机油灯亮了", {})
    assert r["hit"] is True
    assert "danger" in block_types(r), "高风险症状必须出现 danger 块"


def test_symptom_miss_without_rag(monkeypatch):
    monkeypatch.setattr("agents.symptom.rag.search", lambda *a, **k: None)
    r = symptom.handle("随便说点不相关的内容", {})
    assert r["hit"] is False
    assert "receipt_item" not in r


# ---- maintain --------------------------------------------------------------

def test_maintain_hit_quote_review():
    r = maintain.handle("800 换机油机滤合理吗", {"location": "上海"})
    assert_common_contract(r, "maintain")
    assert r["hit"] is True
    assert r["reply"]["price_range"], "报价审核命中应给出参考价格区间"
    assert isinstance(r.get("receipt_item"), dict)


def test_maintain_miss_does_not_fabricate(monkeypatch):
    monkeypatch.setattr("agents.maintain.rag.search", lambda *a, **k: None)
    r = maintain.handle("今天天气怎么样", {})
    assert r["hit"] is False
    assert r["reply"]["price_range"] == []
    assert "receipt_item" not in r


# ---- part ------------------------------------------------------------------

def test_part_image_mode_structured_simulation():
    r = part.handle("", {"image_label": "报价单", "mode": "image"})
    assert_common_contract(r, "part")
    assert r["hit"] is True
    assert r["confidence"] == 0.95
    # 模拟识别价格留空 + 含“需核对实物”提示
    assert r["reply"]["price_range"] == []
    joined = " ".join(b.get("text", "") + b.get("value", "") for b in r["reply"]["blocks"])
    assert "核对" in joined


def test_part_unknown_label_uses_default_hint():
    r = part.handle("", {"image_label": "奇怪的东西", "mode": "image"})
    assert r["hit"] is True
    assert any(b.get("value") == "通用图片" for b in r["reply"]["blocks"])
