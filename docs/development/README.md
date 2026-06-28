# 车小智 · 开发文档入口

> 当前日期：2026-06-28。项目已从 A/B 并行开发阶段进入连调阶段；历史文档里关于“开发人员 A / 开发人员 B / 待新增 / 占位接口”的表述，只作为追溯材料，不再作为当前事实来源。

## 当前事实

- 前端首页、聊天页、知识库、我的页、咨询记录、维修存根页已经在同一个小程序工程里联调。
- 用户信息相关能力走 `/api/user/*`，数据落 MySQL：登录、资料、隐私、统计、车辆、咨询记录、维修记录。
- 知识咨询相关能力走 `/api/chat`：scheduler 先判断输入类型和意图，再分发到 `dtc / symptom / maintain / part` 等 Agent。
- Agent 回答结合本地 JSON 知识库和 RAG；RAG、ASR、MySQL 不可用时均应降级，不阻断诊断主链路。
- `/api/context` 已优先读取 MySQL `user_vehicle`，MySQL 不可用或用户不存在时降级到内存默认车辆。
- 图片入口必须真实调用相机/相册；当前后端仍按 `mode=image + image_label` 做结构化模拟识别，后续接视觉大模型时在同一链路扩展上传/识别。
- 语音入口使用“按住说话、松手转写”，转写结果回填输入框，由用户确认后发送。

## 当前主链路

```text
小程序
  ├─ 登录 / 我的 / 隐私 / 记录
  │    └─ /api/user/* → MySQL
  │
  ├─ 首页 / 聊天读取车辆上下文
  │    └─ /api/context → 优先 MySQL user_vehicle，失败降级默认上下文
  │
  ├─ 文字咨询
  │    └─ /api/chat(mode=text)
  │        → scheduler
  │        → dtc / symptom / maintain / scheduler
  │        → 知识库 / RAG
  │        → 结构化回复
  │        → 前端非阻塞保存 /api/user/consultations
  │
  ├─ 语音咨询
  │    └─ 按住录音 → /api/asr → 回填文字 → /api/chat(mode=text)
  │
  ├─ 图片咨询
  │    └─ wx.chooseMedia 相机/相册
  │        → /api/chat(mode=image, image_label)
  │        → part Agent 当前模拟结构化分析
  │        → 后续替换/扩展为视觉大模型
  │
  └─ 维修存根
       └─ /api/receipt 当前会话生成
          → 前端非阻塞保存 /api/user/repairs
          → 我的页从 MySQL 读历史维修记录
```

## 文档导航

| 文档 | 当前用途 |
|------|----------|
| [01-需求与产品规格.md](./01-需求与产品规格.md) | 产品原始需求与页面说明，若与代码/README 冲突，以当前代码和本入口为准。 |
| [02-系统架构与数据流.md](./02-系统架构与数据流.md) | 历史架构说明，部分 A/B 分工内容已过时。 |
| [03-接口契约.md](./03-接口契约.md) | 接口字段参考；已开始同步当前实现，仍需持续跟随代码更新。 |
| [04-当前进度与问题清单.md](./04-当前进度与问题清单.md) | 历史问题追溯；“/api/chat 占位”等旧断点已修复。 |
| [05-任务清单与开发计划.md](./05-任务清单与开发计划.md) | 历史任务拆分；连调阶段不再按 A/B 人员边界执行。 |
| [06-并行开发边界与合并规则.md](./06-并行开发边界与合并规则.md) | 历史并行开发规则；当前仅作归档参考。 |
| [07-2026-06-28页面与记录增量变更.md](./07-2026-06-28页面与记录增量变更.md) | 页面与记录持久化增量需求，已基本落入当前代码。 |

## 验证命令

```bat
cd car-miniapp
npm run typecheck

cd ..\car-server
.venv\Scripts\python -m pytest
```

## 后续接视觉/大模型的位置

- 视觉模型：从前端已选图片 `tempFilePath` 扩展上传接口，或让 `/api/chat(mode=image)` 支持 `image_url/image_base64`。
- 大模型意图分析：替换或增强 `agents/scheduler.py`，但保留当前规则路由作为稳定降级。
- Agent 答复生成：在各 Agent 命中知识库/RAG 后调用大模型润色，但必须保留“未命中不编造”的兜底。
