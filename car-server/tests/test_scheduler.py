# tests/test_scheduler.py —— 调度 Agent 路由优先级（对应 04 断点 6 的关键约定）
#
# 验证 scheduler.route 的优先级：image > DTC 正则 > 维保关键词 > 症状关键词 > 兜底。

from agents.scheduler import route


def test_image_mode_has_top_priority_even_with_dtc_text():
    # mode=image 即使文本里带 P0300，也应优先路由到 part（04 断点 6）
    r = route("P0300 怎么回事", mode="image", image_label="报价单")
    assert r["agent"] == "part"
    assert r["confidence"] == 0.95


def test_dtc_code_routes_to_dtc():
    for code in ("P0300", "b0402", "C1234"):
        r = route(f"车子报了 {code} 故障码", mode="text")
        assert r["agent"] == "dtc", code


def test_maintain_keyword_routes_to_maintain():
    r = route("800 换机油机滤合理吗", mode="text")
    assert r["agent"] == "maintain"


def test_symptom_keyword_routes_to_symptom():
    r = route("发动机咕噜咕噜响", mode="text")
    assert r["agent"] == "symptom"


def test_unmatched_falls_back_to_scheduler():
    r = route("今天天气怎么样", mode="text")
    assert r["agent"] == "scheduler"
    assert r["confidence"] == 0.55


def test_dtc_priority_over_maintain_keyword():
    # 同时含故障码与“多少钱”，DTC 正则优先于维保关键词
    r = route("P0420 维修多少钱", mode="text")
    assert r["agent"] == "dtc"
