# B 角色 AI 自动测试报告

测试对象：car-server B 链路（知识库 / 报价审核 maintain Agent / 上下文 / 维修记录）
测试分支：main（含 maintain 智能体 LangGraph 升级）
测试时间：2026-06-27
测试人/AI：开发 B（AI 辅助）

## 测试范围

- maintain 报价审核 Agent（**已从普通函数升级为 LangGraph StateGraph**，契约 `handle(text, context)` 不变）
- 三个本地 RAG 知识库（dtc / cost / symptom）数据与读取
- services/context.py（VIN 脱敏、默认上下文）
- 接口字段与总文档 6.1 / 第 8 节 Schema 一致性

> 说明：`/api/chat`、`/api/context`、`/api/receipt` 的 HTTP 全链路依赖 A 的 `routes/chat.py` 调度（当前为占位 stub），本轮以**直接 import 单测**方式验证 B 自有逻辑，符合 B 文档「不依赖小程序页面」的独立通过标准。

## 测试命令

```bash
cd car-server

# 1) maintain LangGraph 版三类输入
.venv/Scripts/python -c "from agents import maintain; print(maintain.handle('4S店报价800元换机油机滤合理吗', {'location':'上海'}))"
.venv/Scripts/python -c "from agents import maintain; print(maintain.handle('换机油机滤大概多少钱', {}))"
.venv/Scripts/python -c "from agents import maintain; print(maintain.handle('今天天气怎么样', {}))"

# 2) 三个本地 RAG 知识库索引
.venv/Scripts/python -c "import chromadb;from chromadb.config import Settings;c=chromadb.PersistentClient(path='.chroma',settings=Settings(anonymized_telemetry=False));[print(col.name, c.get_collection(col.name).count()) for col in c.list_collections()]"

# 3) context 服务 + VIN 脱敏
.venv/Scripts/python -c "from services.context import mask_vin,get_context; print(mask_vin('LFMAP22CXXX123456')); print(get_context('test_user_001'))"
```

## 测试结果汇总

| 用例编号 | 功能 | 结果 | 备注 |
| --- | --- | --- | --- |
| B-004 | maintain 报价偏高判定 | ✅ 通过 | 800 元换机油机滤 → `hit=true`，`price_range=[400,700]`，含「超出市场价上限」warn |
| B-004b | maintain 区间内/未给报价 | ✅ 通过 | 仅询价 → `hit=true`，返回价格区间与避坑三件套，无误判 warn |
| B-014 | maintain 未命中不编造 | ✅ 通过 | 「今天天气怎么样」→ `hit=false`，返回澄清提示，无编造结论（B4-1 已在 Agent 内覆盖） |
| B-010 | 故障码库 kb_dtc | ✅ 通过 | 5 条，本地 RAG 索引 kb_dtc=5 |
| B-011 | 维修成本库 kb_cost | ✅ 通过 | 5 条，本地 RAG 索引 kb_cost=5 |
| B-012 | 症状库 kb_symptom | ✅ 通过 | 5 条，本地 RAG 索引 kb_symptom=5 |
| B-006 | VIN 脱敏 | ✅ 通过 | `LFMAP22CXXX123456` → `LFMA*********3456`，头尾保留、中间脱敏 |
| B-006b | 默认上下文 | ✅ 通过 | `test_user_001` 默认返回卡罗拉车型，VIN 默认脱敏 |
| — | LangGraph 编排生效 | ✅ 通过 | `maintain._get_graph()` 成功编译，`handle` 走图执行；图不可用时退回顺序执行（已留兜底） |
| — | 返回字段 Schema 一致 | ✅ 通过 | `reply` 含 `title/summary/blocks/price_text/price_range`，`agent=maintain`，与总文档 6.1 一致 |

## 失败详情

无。

## 修复建议

- 阶段 4 健壮性打磨尚未全部完成：B4-2 高风险强提醒（症状 `level=高` 返回 danger 块）、B4-3 全链路演示字段校验，建议在 A 的 `routes/chat.py` 调度接入后补做 HTTP 全链路冒烟。
- maintain 已用 LangGraph 编排，后续 dtc/symptom 等多步流程可复用同一 StateGraph 模式。

## 结论

是否允许进入联调：**是**

B 自有链路（知识库 + 报价审核 + 上下文/脱敏）逻辑完整、字段符合 Schema，maintain 已升级为 LangGraph 且行为与原版一致。待 A 的调度接入后即可进行 `/api/chat` 全链路联调。
