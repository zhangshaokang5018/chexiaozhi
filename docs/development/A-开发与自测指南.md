# A 角色开发与自测指南：车况诊断与 Agent 对话链路

> 这份文档是 A 角色**边开发边对照、边打勾**的主文档。
> 它回答三个问题：**我该做什么、按什么顺序做？做到什么程度算做完？怎么自己验证它好了？**
>
> 配套文档：
> - 总开发文档：`docs/development/车小智小程序开发文档.md`（接口 Schema 以它为准）
> - 用例速查表：`docs/testing/A-agent-chat-test-plan.md`
> - 后端启动：`docs/development/后端服务启动说明.md`

---

## 0. 先读这一节（最重要）

### 0.1 你负责的链路

一句话：**让用户在小程序里问一个车况问题，看到一条结构化的诊断结果。**

你负责"输入 → 调度 → 诊断 → 展示"这条链路，**前端 + 这条链路用到的后端 Agent 都归你**（本项目按功能链路分工，不按前后端分）。

你要碰的文件/目录：

```text
car-miniapp/miniprogram/
  pages/chat/            # 聊天主界面（你的主战场）
  pages/chat/components/ # 消息气泡、Agent 卡片等（按需新建）
  utils/request.ts       # 请求封装（已建，按需扩展）
  mock/                  # 你的 mock 数据（新建，独立开发用）
car-server/
  app.py                 # 🔒 已冻结，蓝图已注册，不要改
  routes/chat.py         # /api/chat 路由（你的文件）
  agents/scheduler.py    # 调度 Agent（你写）
  agents/symptom.py      # 症状分析 Agent（你写）
  agents/dtc.py          # 故障码解读 Agent（你写）
  agents/part.py         # 零件识别 Agent（你写）
```

> 协作约定见 `docs/development/工程协作约定.md`：只改自己归属的文件、`app.py` 不要碰、`knowledge/` 只读。

### 0.2 你和 B 的接口契约（必须遵守）

| 事项 | 谁负责 | 你怎么用 |
| --- | --- | --- |
| 知识库 JSON（`kb_dtc/kb_cost/kb_symptom.json`） | B 独家持有 | **起步数据已就绪，你只读不改不提交**。你的 symptom/dtc Agent 直接读它即可自测。Schema 见总文档第 8 节。 |
| 报价审核 Agent（`maintain`） | B 写 | 你只在调度里把 `maintain` 意图分发出去，不实现它的逻辑 |
| `/api/context`、`/api/receipt` | B 写 | 前端弹窗（阶段 3）调它们；独立开发期用 mock |

**独立开发铁律**：你的页面在**服务端没启动时也要能用 mock 数据完整演示**。不能因为 B 没写完你就卡住。

### 0.3 怎么确认"我做到哪了"——进度看板

每完成一个任务，把下面表格对应行的 `[ ]` 改成 `[x]`。一眼就知道进度。

| 阶段 | 任务 | 状态 |
| --- | --- | --- |
| 1 | A1-1 聊天页消息流骨架 | [ ] |
| 1 | A1-2 用户输入与发送 | [ ] |
| 1 | A1-3 快捷问题区 | [ ] |
| 1 | A1-4 接入 /api/chat（含 mock 开关） | [ ] |
| 1 | A1-5 调度 Agent + steps 展示 | [ ] |
| 2 | A2-1 症状分析 Agent（后端） | [ ] |
| 2 | A2-2 故障码解读 Agent（后端） | [ ] |
| 2 | A2-3 零件识别 Agent（后端） | [ ] |
| 2 | A2-4 Agent 回复卡片渲染（blocks/price/legal） | [ ] |
| 3 | A3-1 车辆信息弹窗 | [ ] |
| 3 | A3-2 顶部上下文联动 | [ ] |
| 3 | A3-3 核销单弹窗展示 | [ ] |
| 4 | A4-1 默认演示数据 | [ ] |
| 4 | A4-2 loading / 网络错误 / 合规提示打磨 | [ ] |

### 0.4 每个任务长什么样

下面每个任务都按统一格式写，照着做即可：

- **目标**：这个任务要达成什么
- **改哪些文件**：动手范围
- **完成定义 DoD**：逐条可勾，**全勾才算完成**
- **怎么自测**：具体步骤 + **预期看到什么**（这是你"确认做好了"的依据）
- **对应用例**：测试计划里的编号

---

## 阶段 1：聊天与调度

阶段目标：用户能发消息，请求能按意图路由到正确的 Agent，并看到处理步骤。

### A1-1 聊天页消息流骨架

- **目标**：聊天页有一个能上下滚动的消息流，支持"用户气泡"和"Agent 气泡"两种样式。
- **改哪些文件**：`pages/chat/chat.wxml`、`chat.less`、`chat.ts`
- **完成定义 DoD**：
  - [ ] `chat.ts` 的 `data` 里有 `messages: Message[]` 数组
  - [ ] 消息类型至少支持 `user`(用户文字)、`agent`(AI回复)、`loading`(处理中) 三种
  - [ ] 用户气泡右对齐，Agent 气泡左对齐，样式可区分
  - [ ] 新消息追加后自动滚动到底部（`scroll-into-view`）
- **怎么自测**：
  1. 在 `chat.ts` 的 `data.messages` 里手写 2 条假数据（一条 user、一条 agent）。
  2. 开发者工具编译，进入聊天页。
  3. **预期看到**：两条气泡左右分开显示，样式不同；内容能正常换行不溢出。
- **对应用例**：A-001、A-003

### A1-2 用户输入与发送

- **目标**：底部输入栏能输入文字，点发送后把用户消息加入消息流，空输入不能发。
- **改哪些文件**：`chat.wxml`、`chat.ts`
- **完成定义 DoD**：
  - [ ] 输入框双向绑定 `data.inputText`
  - [ ] 点"发送"后：把文字作为 `user` 消息 push 进 `messages`，并清空输入框
  - [ ] `inputText` 去掉首尾空格后为空时，发送按钮不可点（或点了无反应）
- **怎么自测**：
  1. 输入"咕噜咕噜响"，点发送。**预期**：出现一条用户气泡，输入框清空。
  2. 不输入任何内容直接点发送。**预期**：没有新增空气泡。
  3. 只输入空格点发送。**预期**：同样不能发送。
- **对应用例**：A-003、A-013

### A1-3 快捷问题区

- **目标**：聊天页有一排可横向滑动的快捷问题，点一下等于替用户发出该问题。
- **改哪些文件**：`chat.wxml`、`chat.less`、`chat.ts`
- **完成定义 DoD**：
  - [ ] 有至少 4 个快捷问题：症状("咕噜咕噜响")、故障码("P0300 是什么意思")、报价("800 元换机油机滤合理吗")、图片("拍报价单")
  - [ ] 横向 `scroll-view` 可滑动，不换行挤压
  - [ ] 点击后复用 A1-2 的发送逻辑（图片类走 `mode=image`，见 A1-4）
- **怎么自测**：
  1. 进入页面，横向滑动快捷问题区。**预期**：能滑动，按钮不变形。
  2. 点"咕噜咕噜响"。**预期**：等同于手动输入并发送，出现用户气泡。
- **对应用例**：A-004、A-005

### A1-4 接入 /api/chat（含 mock 开关）

- **目标**：发送后调用 `/api/chat`，把返回渲染成 Agent 气泡；并提供 mock 开关，让页面脱离服务端也能演示。
- **改哪些文件**：`utils/request.ts`（加 `chat()`）、`pages/chat/chat.ts`、新建 `miniprogram/mock/mock_chat_success.json`、`mock_chat_loading.json`、`mock_chat_error.json`
- **请求/响应 Schema**：严格按总文档 6.1。请求 `{user_id, text, mode, image_label}`，响应含 `route/agent/agent_meta/hit/reply/steps/elapsed_ms/legal_note`。
- **完成定义 DoD**：
  - [ ] `request.ts` 新增 `chat(payload): Promise<ChatResp>`
  - [ ] `chat.ts` 里有 `USE_MOCK` 开关（`true` 时读 `mock/*.json`，不发网络请求）
  - [ ] 发送时先 push 一条 `loading` 消息，拿到结果后替换为 `agent` 消息
  - [ ] 三份 mock JSON 都符合 6.1 Schema，字段齐全
  - [ ] 文字走 `mode=text`，快捷"拍报价单"走 `mode=image` 且带 `image_label`
- **怎么自测**：
  1. 把 `USE_MOCK=true`，发任意消息。**预期**：先看到 loading 气泡，约 0.5s 后变成 Agent 回复气泡（来自 `mock_chat_success.json`）。
  2. 把 mock 指向 `mock_chat_error.json` 或模拟 reject。**预期**：出现"请求失败"提示，不白屏不卡死。
  3. `USE_MOCK=false` 且后端已启动，重复步骤 1。**预期**：拿到真实返回。
- **对应用例**：A-006、A-012

### A1-5 调度 Agent + steps 展示（后端 + 前端）

- **目标**：后端 `/api/chat` 能按规则把输入路由到 `symptom/dtc/maintain/part/scheduler`，并返回 steps；前端把 steps 渲染成处理步骤。
- **改哪些文件**：`car-server/routes/chat.py`、`car-server/agents/scheduler.py`、`pages/chat/*`（`app.py` 不要改）
- **路由规则**：严格按总文档 7.1：
  - `mode=image` → `part`
  - 含 `P/B/C + 4位数字` → `dtc`
  - 含 "报价/费用/价格/多少钱/合理/贵/保养" → `maintain`
  - 含 "响/抖/顿挫/报警/灯亮/水温/机油/刹车/转向" → `symptom`
  - 都不匹配 → `scheduler`
- **完成定义 DoD**：
  - [ ] `scheduler.py` 有 `route(text, mode, image_label) -> {agent, intent, confidence}`
  - [ ] `/api/chat` 调 `route()`，返回的 `route.agent` 符合上表
  - [ ] 响应里 `steps` 至少含：意图识别、分发、知识库检索、合成回复 4 步，每步有 `status`
  - [ ] 前端把 `agent_meta.name/desc`、`route.intent`、`steps` 渲染出来（Agent chip + 步骤标签）
- **怎么自测**（前端 + 后端各一套）：
  - 后端（启动服务后，用 curl，预期 `agent` 字段）：
    ```bash
    curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
      -d '{"user_id":"test_user_001","text":"P0300 是什么意思","mode":"text","image_label":""}'
    # 预期 route.agent = "dtc"

    curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
      -d '{"user_id":"test_user_001","text":"咕噜咕噜响","mode":"text","image_label":""}'
    # 预期 route.agent = "symptom"

    curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
      -d '{"user_id":"test_user_001","text":"800元换机油机滤合理吗","mode":"text","image_label":""}'
    # 预期 route.agent = "maintain"

    curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
      -d '{"user_id":"test_user_001","text":"拍报价单","mode":"image","image_label":"报价单"}'
    # 预期 route.agent = "part"
    ```
  - 前端：`USE_MOCK=false`，分别发上面 4 句。**预期**：每条 Agent 气泡顶部显示对应 Agent 名称，并列出 4 个处理步骤。
- **对应用例**：A-004、A-007、A-008

### ✅ 阶段 1 验收（全勾才算这阶段完成）

- [ ] 输入 "P0300" → 路由到 `dtc`
- [ ] 输入 "咕噜咕噜响" → 路由到 `symptom`
- [ ] 输入 "800 元换机油合理吗" → 路由到 `maintain`
- [ ] 点 "拍报价单" → 路由到 `part`
- [ ] 每条回复都能看到 Agent 名称 + 处理步骤
- [ ] `USE_MOCK=true` 时整条聊天流程可脱离服务端演示

---

## 阶段 2：诊断 Agent 与回复卡片

阶段目标：三类 Agent（症状/故障码/零件）能产出结构化结果，前端把它渲染成漂亮卡片。

> 注：本阶段三个 Agent 要读知识库。**起步数据 B 已放好（含 P0300、"咕噜咕噜"等），你直接读 `car-server/knowledge/*.json` 即可，不要修改或提交它们**。Schema 见总文档第 8 节。

### A2-1 症状分析 Agent（后端）

- **目标**：`symptom.py` 根据症状关键词匹配症状库，输出故障点、紧急程度、应急处理、避坑建议、费用区间。
- **改哪些文件**：`car-server/agents/symptom.py`（只读 `knowledge/kb_symptom.json`，不修改）
- **完成定义 DoD**：
  - [ ] 能按关键词匹配，取最高匹配项
  - [ ] 输出组装成 6.1 的 `reply`：`title/summary/blocks/price_text/price_range`
  - [ ] `blocks` 含至少 1 条 `warn`(避坑/应急) 和价格相关 kv
  - [ ] 命中不到时**不编造**，返回澄清提示（`hit=false`）
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"发动机咕噜咕噜响，加速更明显","mode":"text","image_label":""}'
  ```
  **预期**：`agent=symptom`，`reply.blocks` 里有故障点、紧急程度、费用，且有一条 `warn`。
- **对应用例**：A-009、A-010、A-011

### A2-2 故障码解读 Agent（后端）

- **目标**：`dtc.py` 提取 DTC 代码，查故障码库，输出描述、可能原因、修复难度、排查顺序、费用区间。
- **改哪些文件**：`car-server/agents/dtc.py`（只读 `knowledge/kb_dtc.json`，不修改）
- **完成定义 DoD**：
  - [ ] 能从文本里正则提取形如 `P0300` 的代码
  - [ ] 查到后输出 `desc/cause/level/logic` + 费用区间，组装成 `reply`
  - [ ] 高危等级(level≥3)的 `blocks` 含 `danger` 类型高亮
  - [ ] 查不到代码时 `hit=false`，给澄清
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"仪表盘亮黄灯，读码 P0300","mode":"text","image_label":""}'
  ```
  **预期**：`agent=dtc`，`reply` 含 P0300 描述、可能原因、排查顺序。
- **对应用例**：A-008、A-009

### A2-3 零件识别 Agent（后端）

- **目标**：`part.py` 用预设结果模拟图片识别，输出识别结果、零件库匹配、原厂/副厂建议、避坑建议。
- **改哪些文件**：`car-server/agents/part.py`
- **完成定义 DoD**：
  - [ ] 按 `image_label`（刹车片/机油报警/报价单）返回不同预设结果
  - [ ] 输出组装成 `reply`，含避坑 `warn`
  - [ ] MVP 阶段在结果里标注"识别为模拟"
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"识别刹车片","mode":"image","image_label":"刹车片"}'
  ```
  **预期**：`agent=part`，返回刹车片识别结果 + 避坑建议。
- **对应用例**：A-005

### A2-4 Agent 回复卡片渲染（前端）

- **目标**：把 `reply.blocks` 按类型渲染成卡片：`kv` 普通行、`warn` 黄色块、价格绿色、`danger` 红色；底部固定显示 `legal_note`。
- **改哪些文件**：`pages/chat/chat.wxml`、`chat.less`、（可选）`components/reply-card`
- **完成定义 DoD**：
  - [ ] `kv` 类型渲染为"标签：值"行
  - [ ] `warn` 类型用黄色警示块
  - [ ] `price_text` 用绿色高亮
  - [ ] `danger`/故障码危险等级用红色高亮
  - [ ] 每条 AI 回复底部都显示 `legal_note`（"仅供参考…"）
- **怎么自测**：
  1. 用 `mock_chat_success.json`（含 kv/warn/danger 三种 block + price + legal）驱动页面。
  2. **预期看到**：普通信息白底行、避坑黄块、价格绿字、危险红字、底部免责声明，**无重叠/溢出/不可读**。
- **对应用例**：A-009、A-010、A-011

### ✅ 阶段 2 验收

- [ ] 症状/故障码/零件三类输入都能返回结构化 `blocks`
- [ ] 每类返回都含价格区间
- [ ] 每类返回都含至少 1 条避坑/应急建议
- [ ] 每条回复底部都有免责声明

---

## 阶段 3：上下文与维修记录闭环（前端展示部分）

阶段目标：前端能展示/编辑车辆信息，并把诊断结果生成维修记录存根弹窗。

> 注：`/api/context`、`/api/receipt` 的实现是 B 的活。独立开发期你用 mock 数据；联调时接 B 的真实接口。

### A3-1 车辆信息弹窗

- **目标**：点顶部上下文条弹出车辆信息弹窗，展示车型/VIN/里程/所在地，VIN 默认脱敏，编辑态可见完整 VIN。
- **改哪些文件**：`pages/chat/chat.wxml`、`chat.ts`、（可选）`components/car-info-modal`
- **完成定义 DoD**：
  - [ ] 点顶部条能打开弹窗
  - [ ] 展示态 VIN 脱敏（如 `LFMA****3456`）
  - [ ] 进入编辑态显示完整 VIN，保存后更新顶部上下文
  - [ ] "清空对话与记录"需二次确认
- **怎么自测**：
  1. mock 一份 context，打开弹窗。**预期**：VIN 是脱敏的。
  2. 点编辑。**预期**：VIN 变完整；改里程保存后顶部数字同步变化。
  3. 点清空。**预期**：弹出二次确认。
- **对应用例**：A-002

### A3-2 顶部上下文联动

- **目标**：进页面拉取 context 渲染到顶部条；编辑保存后实时刷新。
- **改哪些文件**：`utils/request.ts`(加 `getContext/updateContext`)、`chat.ts`
- **完成定义 DoD**：
  - [ ] `onLoad` 拉 context（mock 或真实）渲染顶部
  - [ ] 保存走 `POST /api/context`（或 mock），成功后本地数据同步
- **怎么自测**：mock 模式下改完保存，**预期**顶部"车型·里程·所在地"立即更新。
- **对应用例**：A-002

### A3-3 核销单弹窗展示

- **目标**：诊断产生结果后，可点"维修记录"生成核销单弹窗；无诊断记录时显示空状态。
- **改哪些文件**：`pages/chat/*`、（可选）`components/receipt-modal`
- **完成定义 DoD**：
  - [ ] 有诊断结果后点"维修记录" → 弹出存根，含维修中心/工单号/车型/VIN/所在地/时间/项目/零件价/工时价/合计
  - [ ] 无诊断记录时显示"尚无诊断记录，请先咨询"
  - [ ] 弹窗标注"模拟核销单"
- **怎么自测**：
  1. 没诊断就点维修记录。**预期**：空状态提示。
  2. 先跑一次诊断，再点。**预期**：弹出完整存根（mock `/api/receipt` 数据）。
- **对应用例**：A-002

### ✅ 阶段 3 验收

- [ ] 改车辆信息后顶部上下文同步变化
- [ ] 诊断后能生成核销单存根
- [ ] 无记录时核销单是空状态
- [ ] VIN 默认脱敏

---

## 阶段 4：演示打磨（与 B 协作）

### A4-1 默认演示数据

- **目标**：首次进入有欢迎语 + 默认车辆上下文，演示不冷场。
- **完成定义 DoD**：
  - [ ] 首次进入显示欢迎消息 + 免责声明
  - [ ] 顶部有默认车辆上下文（卡罗拉那条）
- **怎么自测**：清缓存重进。**预期**：直接能看到欢迎语和上下文，无需任何操作。

### A4-2 loading / 网络错误 / 合规提示打磨

- **目标**：三种状态都顺滑，合规提示齐全。
- **完成定义 DoD**：
  - [ ] loading 有"AI 正在思考"动画/文案
  - [ ] 服务端关闭时发消息有明确错误提示，可重试
  - [ ] 高风险症状（如机油报警灯）有强提醒（建议停车/线下检查）
  - [ ] 所有 AI 回复都有免责声明
- **怎么自测**：
  1. 关掉后端发消息。**预期**：友好错误提示 + 重试入口，不白屏。
  2. 发"机油报警灯亮"。**预期**：出现强提醒块。
- **对应用例**：A-006、A-012、I-007、I-009

### ✅ 阶段 4 验收

- [ ] 能在 3 分钟内连续演示：症状 → 故障码 → 报价 → 维修记录
- [ ] 页面无明显错位
- [ ] 服务端异常时有提示
- [ ] 所有 AI 建议带免责声明，高风险有强提醒

---

## 附：A 的独立通过标准（进联调前自检）

- [ ] 不依赖真实服务端，用 3 份 mock（成功/loading/错误）能完整演示聊天流程
- [ ] 阶段 1~4 进度看板全部打勾
- [ ] 页面无重叠、溢出、不可读文字
- [ ] 已在 `docs/testing/ai-test-report-template.md` 复制一份并填好测试报告，结论为"允许进入联调"
