# B 角色测试计划：知识库、报价审核与维修记录闭环

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
| B-013 | RAG 命中 | 已知故障码/症状 | 返回高相关知识块 | pytest |
| B-014 | RAG 未命中 | 无关问题 | 返回澄清建议，不编造 | pytest |
| B-015 | LangGraph 流转 | 正常输入 | 节点按调度、检索、生成顺序完成 | pytest |

## AI 自动测试命令

待实现后补充，例如：

```bash
pytest tests/test_b_kb_receipt.py
```

## 通过标准

- B-001 到 B-015 全部通过。
- 所有接口返回符合开发文档 Schema。
- RAG 命中和未命中均有覆盖。
- 不依赖 A 的小程序页面即可完成测试。

