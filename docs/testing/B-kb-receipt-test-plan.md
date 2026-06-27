# B 角色测试计划：知识库、报价审核与维修记录闭环

> **本文是「用例速查表」。** 详细的开发步骤、完成定义(DoD)、每个接口怎么用 curl 自测，见
> `docs/development/B-开发与自测指南.md`（开发时以那份为主，本表用于回归核对）。
>
> **接口范围以总文档第 6 节为准。** 标【后续】的用例属于 MVP 之后的扩展（知识库搜索/分页/详情、
> 维修记录列表、反馈接口等，总文档未定义），本期不做、不计入通过标准。
> RAG / LangGraph 为技术选型方向，MVP 用关键词匹配即可达标，相关用例标【可选】。

## 功能范围

- RAG 知识库
- Agent 接口逻辑
- 报价审核
- 车辆上下文
- 维修记录存根
- 核销单数据

## 前置条件

- 服务端可本地启动。
- 使用固定测试用户：`test_user_001`。
- 每次测试前清空测试用户上下文。
- 不依赖小程序页面。

## B 做完后应该是什么样

- 服务端能本地启动，并且 `/api/ping` 返回健康状态。
- `/api/chat` 能识别症状、故障码、报价审核、图片模拟四类请求。
- `/api/context` 能读取和更新固定测试用户的车辆信息。
- `/api/receipt` 能返回无记录和有记录两种核销单结果。
- `/api/kb/dtc`、`/api/kb/cost`、`/api/kb/symptom` 能返回知识库数据。
- 知识库命中时返回相关知识块，未命中时给澄清建议，不编造结论。
- 返回 JSON 字段稳定，和开发文档 Schema 一致。

以下为 MVP 之后的扩展（本期不做）：

- `/api/kb/<kind>` 支持关键词搜索、筛选和分页。
- `/api/kb/<kind>/<id>` 能返回详情和一键咨询文本。
- `/api/receipts` 和 `/api/receipts/<id>` 能返回历史记录列表和详情。
- `/api/feedback` 能保存用户反馈。

## B 自测顺序

1. 启动服务端，不打开小程序。
2. 使用固定测试用户 `test_user_001` 清空或重置测试数据。
3. 用 curl 或 pytest 跑 B-001 到 B-012、B-019（核心用例）。
4. 把测试命令、返回摘要、失败原因写入测试报告。
5. 全部通过后，再和 A 的小程序页面做联调。

## 测试用例

| 编号 | 功能 | 输入 | 期望结果 | 自动测试方式 |
| --- | --- | --- | --- | --- |
| B-001 | 服务健康 | GET `/api/ping` | 返回 `ok=true` | pytest/curl |
| B-002 | 症状分析 | 咕噜咕噜响 | agent=symptom，返回故障点和费用 | pytest |
| B-003 | 故障码 | P0300 | agent=dtc，返回故障码解释 | pytest |
| B-004 | 报价审核 | 800 元换机油 | agent=maintain，判断报价偏高 | pytest |
| B-005 | 图片模拟 | mode=image | agent=part，返回识别结果 | pytest |
| B-006 | 获取上下文 | GET `/api/context` | 返回车型、VIN、里程、所在地 | pytest |
| B-007 | 更新上下文 | POST `/api/context` | 字段更新成功 | pytest |
| B-008 | 无记录核销单 | POST `/api/receipt` | items 为空，总价为 0 | pytest |
| B-009 | 有记录核销单 | 先 chat 再 receipt | items 有数据，总价大于 0 | pytest |
| B-010 | DTC 知识库 | GET `/api/kb/dtc` | count > 0 | pytest |
| B-011 | 成本知识库 | GET `/api/kb/cost` | count > 0 | pytest |
| B-012 | 症状知识库 | GET `/api/kb/symptom` | count > 0 | pytest |
| B-013 | 【可选】RAG 命中 | 已知故障码/症状 | 返回高相关知识块 | pytest |
| B-014 | 知识库未命中 | 无关问题 | 返回澄清建议，不编造 | pytest |
| B-015 | 【可选】LangGraph 流转 | 正常输入 | 节点按调度、检索、生成顺序完成 | pytest |
| B-016 | 【后续】知识库搜索 | GET `/api/kb/dtc?q=P0300` | total > 0，items 包含 P0300 | pytest |
| B-017 | 【后续】知识库筛选 | GET `/api/kb/symptom?level=高` | 只返回高风险症状 | pytest |
| B-018 | 【后续】知识库详情 | GET `/api/kb/dtc/P0300` | 返回 source 和 ask_text | pytest |
| B-019 | 高风险强提醒 | 机油红灯亮 | risk_level=高，包含停车/救援建议 | pytest |
| B-020 | 【后续】维修记录列表 | GET `/api/receipts` | 返回分页列表 | pytest |
| B-021 | 【后续】维修记录详情 | GET `/api/receipts/<id>` | 返回原始问题和继续追问文本 | pytest |
| B-022 | 【后续】用户反馈 | POST `/api/feedback` | ok=true，反馈可查询或落库 | pytest |

## AI 自动测试命令

待实现后补充，例如：

```bash
pytest tests/test_b_kb_receipt.py
```

## 通过标准

- 核心用例 B-001 到 B-012、B-014、B-019 全部通过（标【后续】不计入；标【可选】视实现方式而定）。
- 所有接口返回符合开发文档 Schema。
- 知识库命中和未命中均有覆盖。
- 不依赖 A 的小程序页面即可完成测试。

