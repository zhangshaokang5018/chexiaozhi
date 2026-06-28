# A 角色 AI 自动测试报告

测试对象：car-server A 链路（对话调度 /api/chat + 四个诊断 Agent + 知识库/上下文/维修存根/ASR）
测试分支：codex/ab-development-docs（A-T1~A-T10 已完成）
测试时间：2026-06-27
测试人/AI：开发 A（AI 辅助）
测试方式：pytest + Flask `app.test_client()` 全链路 + Agent 直接 import 单测，**不依赖 MySQL、不依赖联网**

## 测试范围

- `agents/scheduler.py` 意图路由优先级（image > DTC 正则 > 维保关键词 > 症状关键词 > 兜底）
- `agents/dtc.py`、`symptom.py`、`maintain.py`、`part.py` 的 `handle(text, context)` 统一契约（命中 + 未命中）
- `routes/chat.py`：`/api/chat` 全链路、输出归一化（`miss→pending`、`good→kv+good:true`）、scheduler/异常兜底、`user_id` + receipt 沉淀（A-T1/A-T2/A-T5）
- `routes/kb.py`：知识库分页、`/api/kb/dtc/{code}` 详情、非法 kind 404（A-T10）
- `routes/context.py` + `services/context.py`：VIN 脱敏、GET/POST 上下文回环
- `routes/receipt.py` + `services/receipt.py`：诊断沉淀生成核销单
- `routes/asr.py` + `services/asr.py`：无 Key 降级转写
- `routes/health.py`：`/api/ping`

> 说明：断言基于**接口契约**（字段存在性、命中/未命中语义、归一化不变量），不写死可变的知识库价格数值；未命中用例用 `monkeypatch` 关闭 RAG，确保不依赖本地向量库、结果确定。

## 测试命令

```bash
cd car-server
.venv/Scripts/python -m pip install -r requirements-dev.txt   # 安装 pytest（独立于 requirements.txt）
.venv/Scripts/python -m pytest                                # 运行全部用例
```

测试代码位于 `car-server/tests/`：`conftest.py`、`test_scheduler.py`、`test_agents.py`、
`test_chat_route.py`、`test_services_and_routes.py`。

## 测试结果汇总

**32 passed**（首次运行即全绿，未发现需修复的代码缺陷）。耗时约 80s，主要为
sentence-transformers 嵌入模型加载（RAG 实际可用路径）。

| 用例编号 | 功能 | 结果 | 备注 |
| --- | --- | --- | --- |
| SCH-1 | image 模式最高优先级 | ✅ 通过 | 文本含 P0300 仍路由 part（04 断点 6） |
| SCH-2 | DTC 正则路由 | ✅ 通过 | P0300/b0402/C1234 → dtc |
| SCH-3 | 维保/症状关键词 + 兜底 | ✅ 通过 | 合理→maintain；咕噜响→symptom；无匹配→scheduler(0.55) |
| SCH-4 | DTC 优先于维保关键词 | ✅ 通过 | “P0420 维修多少钱” → dtc |
| A-007/008 | dtc 命中契约 | ✅ 通过 | P0300 → hit、price_range 非空、confidence 0.92、带 receipt_item |
| A-009/I-009 | symptom 高风险 danger | ✅ 通过 | “机油灯亮” → level=高，出现 danger 强提醒 |
| A-013 类 | dtc/symptom/maintain 未命中不编造 | ✅ 通过 | 关闭 RAG 后均 hit=false、无 receipt_item、price_range=[] |
| I-004 | maintain 报价审核命中 | ✅ 通过 | “800 换机油机滤” → hit、price_range=[400,700]、含报价评估 |
| A-005/I-005 | part 图片模拟 | ✅ 通过 | image_label=报价单 → 结构化核对项 + “需核对实物”，价格留空 |
| A-002/A-008 | /api/chat 外形 + 归一化不变量 | ✅ 通过 | 6 类输入响应字段齐全；steps.status∈{done,doing,pending,todo}；无 good 块 |
| A-2 单测 | `_normalize_agent_result` | ✅ 通过 | miss→pending（保留 detail）；good→kv 且 good=true |
| 兜底 | /api/chat 永远能跑 | ✅ 通过 | 无意义输入 → scheduler、hit=false、200 且 reply 非空 |
| A-T5/I-006 | user_id + receipt 沉淀 | ✅ 通过 | 报价诊断后 /api/receipt 的 items 非空、total>0 |
| I-008 | 合规免责声明 | ✅ 通过 | legal_note 含“仅供参考” |
| I-001 | /api/ping | ✅ 通过 | ok=true、name=chexiaozhi-server |
| B-006 类 | VIN 脱敏 | ✅ 通过 | get_context 脱敏、get_raw_context 不脱敏，头尾保留 |
| A-T10 | kb 分页 | ✅ 通过 | page_size=4 → total≥5、count=min(4,total)、字段齐全 |
| A-T10 | kb 详情 by code / 404 | ✅ 通过 | /api/kb/dtc/P0300 命中；非法 kind 与未知 code 均 404 |
| ASR | 无 Key 降级 | ✅ 通过 | ok=true、text 非空；缺文件 → 400 |

## 失败详情

无。32 条用例首跑全绿，A 的后端实现与 `docs/development/03-接口契约.md` 契约一致。

## 修复说明

本轮无需修改 A 的源码（`agents/*`、`routes/*`、`services/*` 未改动）。仅新增测试相关文件：
- `car-server/tests/`（conftest + 4 个测试模块）
- `car-server/requirements-dev.txt`（pytest，独立于主依赖）
- `car-server/pytest.ini`

## 未覆盖项（需人工核对，不在本轮自动化范围）

前端小程序页面（A-001~A-013 的 UI 渲染：欢迎语/上下文卡片/气泡/快捷问题/loading/error/
空输入禁发等）依赖**微信开发者工具**运行，无法无头自动化。建议用开发者工具打开
`car-miniapp` 按 `docs/testing/A-agent-chat-test-plan.md` 清单手动回归一次。

## 结论

是否允许进入联调：**是**

A 自有主业务链路（调度 + 四个诊断 Agent + 归一化 + 上下文/存根/知识库/ASR）逻辑完整、
字段符合 Schema、命中/未命中/兜底语义正确，32 条后端用例全部通过。前端 UI 用例待在
微信开发者工具中人工核对后即可进入与 B 的 `/api/chat` 全链路联调。
