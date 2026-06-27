# B 角色开发与自测指南：知识库、报价审核与维修记录闭环

> 这份文档是 B 角色**边开发边对照、边打勾**的主文档。
> 它回答三个问题：**我该做什么、按什么顺序做？做到什么程度算做完？怎么自己验证它好了？**
>
> 配套文档：
> - 总开发文档：`docs/development/车小智小程序开发文档.md`（接口 Schema 以它为准）
> - 用例速查表：`docs/testing/B-kb-receipt-test-plan.md`
> - 后端启动：`docs/development/后端服务启动说明.md`

---

## 0. 先读这一节（最重要）

### 0.1 你负责的链路

一句话：**让诊断结果能引用知识库、给出价格区间，并沉淀成维修记录。**

你负责"数据 + 报价审核 + 闭环沉淀"。你要碰的文件/目录：

```text
car-server/
  app.py                  # 🔒 已冻结，蓝图已注册，不要改
  routes/context.py       # /api/context 路由（你的文件）
  routes/receipt.py       # /api/receipt 路由（你的文件）
  routes/kb.py            # /api/kb/<kind> 路由（你的文件，已有基础实现）
  agents/maintain.py      # 报价审核/保养建议 Agent（你写）
  services/
    context.py            # 用户车辆上下文 + VIN 脱敏（你写）
    receipt.py            # 维修记录存根生成（你写）
  knowledge/
    kb_dtc.json           # 故障码知识库（你独家维护，起步数据已就绪）
    kb_cost.json          # 维修成本知识库
    kb_symptom.json       # 症状知识库
```

> 协作约定见 `docs/development/工程协作约定.md`：只改自己归属的文件、`app.py` 不要碰、`knowledge/` 由你独家写。

### 0.2 你和 A 的接口契约（必须遵守）

| 事项 | 谁负责 | 说明 |
| --- | --- | --- |
| 知识库 JSON 的**字段 Schema** | 双方冻结，B 是数据权威 | 见总文档第 8 节。开发期只允许"兼容性新增字段"，**不许删除或改名** |
| `scheduler/symptom/dtc/part` Agent | A 写 | 你不实现，但你的知识库要能被它们查到 |
| `maintain` Agent | 你写 | A 的调度会把"报价/保养"意图分发给你 |
| `/api/context`、`/api/receipt`、`/api/kb/<kind>` | 你写 | A 的前端弹窗会调它们 |

**独立开发铁律**：你**不依赖小程序页面**，全程用 `curl` 或 pytest 测接口。固定测试用户：`test_user_001`，每次测试前重置它的上下文。

### 0.3 接口范围（以总文档第 6 节为准，别多做）

MVP 只做这些接口，**不要**自行新增 `/api/feedback`、`/api/receipts` 列表、知识库分页等（那些是后续阶段，现在做会和 A 对不上）：

- `GET  /api/ping`（已完成）
- `POST /api/chat`（调度由 A 接，`maintain` 分支由你实现）
- `GET  /api/context?user_id=`
- `POST /api/context`
- `POST /api/receipt`
- `GET  /api/kb/<kind>`（kind = dtc / cost / symptom）

### 0.4 怎么确认"我做到哪了"——进度看板

每完成一个任务，把 `[ ]` 改成 `[x]`。

| 阶段 | 任务 | 状态 |
| --- | --- | --- |
| 2 | B2-1 故障码知识库 kb_dtc.json | [ ] |
| 2 | B2-2 症状知识库 kb_symptom.json | [ ] |
| 2 | B2-3 维修成本知识库 kb_cost.json | [ ] |
| 2 | B2-4 GET /api/kb/<kind> 接口 | [ ] |
| 2 | B2-5 报价审核 Agent（maintain） | [ ] |
| 3 | B3-1 services/context.py + VIN 脱敏 | [ ] |
| 3 | B3-2 GET/POST /api/context | [ ] |
| 3 | B3-3 services/receipt.py + POST /api/receipt | [ ] |
| 4 | B4-1 知识库未命中回退（不编造） | [ ] |
| 4 | B4-2 高风险强提醒 | [ ] |
| 4 | B4-3 演示数据与字段一致性校验 | [ ] |

> 说明：阶段 1 的 `/api/ping` 已在基座完成；`/api/chat` 路由骨架由 A 负责，你在阶段 2 补 `maintain` 分支。

### 0.5 每个任务长什么样

- **目标 / 改哪些文件 / 完成定义 DoD / 怎么自测（可复制 curl + 预期输出）/ 对应用例**
- 自测前先确保后端已启动（见 `后端服务启动说明.md`）。

---

## 阶段 2：知识库与报价审核

### B2-1 故障码知识库 kb_dtc.json

- **目标**：建立故障码知识库，字段严格按总文档 8.1。
- **改哪些文件**：`car-server/knowledge/kb_dtc.json`
- **完成定义 DoD**：
  - [ ] 是合法 JSON 数组，至少 5 条，**必含 P0300**
  - [ ] 每条含：`code/desc/cause/level/logic/price_part_low/price_part_high/price_labor_low/price_labor_high`
  - [ ] `level` 为 1~3 的数字；价格为数字
- **怎么自测**：
  ```bash
  cd car-server
  .venv/Scripts/python -c "import json;d=json.load(open('knowledge/kb_dtc.json',encoding='utf-8'));print('条数',len(d));print('含P0300', any(x['code']=='P0300' for x in d))"
  ```
  **预期**：打印条数 ≥5 且 `含P0300 True`，无 JSON 报错。
- **对应用例**：B-010

### B2-2 症状知识库 kb_symptom.json

- **目标**：建立症状知识库，字段按总文档 8.3。
- **改哪些文件**：`knowledge/kb_symptom.json`
- **完成定义 DoD**：
  - [ ] 合法 JSON 数组，至少 5 条，**必含含"咕噜咕噜"关键词的一条**
  - [ ] 每条含：`keywords(数组)/fault/level/tip/part_low/part_high/labor_low/labor_high`
  - [ ] 至少有 1 条 `level="高"` 的高风险症状（如机油报警）
- **怎么自测**：
  ```bash
  .venv/Scripts/python -c "import json;d=json.load(open('knowledge/kb_symptom.json',encoding='utf-8'));print('条数',len(d));print('有高风险', any(x['level']=='高' for x in d))"
  ```
  **预期**：条数 ≥5，`有高风险 True`。
- **对应用例**：B-012、B-019

### B2-3 维修成本知识库 kb_cost.json

- **目标**：建立成本基准库，字段按总文档 8.2。
- **改哪些文件**：`knowledge/kb_cost.json`
- **完成定义 DoD**：
  - [ ] 合法 JSON 数组，至少 5 条，**必含"更换机油机滤"**
  - [ ] 每条含：`cat/item/part_low/part_high/labor_low/labor_high/tip`
- **怎么自测**：
  ```bash
  .venv/Scripts/python -c "import json;d=json.load(open('knowledge/kb_cost.json',encoding='utf-8'));print('条数',len(d));print('含机油机滤', any('机油机滤' in x['item'] for x in d))"
  ```
  **预期**：条数 ≥5，`含机油机滤 True`。
- **对应用例**：B-011

### B2-4 GET /api/kb/<kind> 接口

- **目标**：提供知识库查询接口，`kind` 取 `dtc/cost/symptom`。
- **改哪些文件**：`car-server/routes/kb.py`（已有读取文件的基础实现，可按需扩展）
- **完成定义 DoD**：
  - [ ] `/api/kb/dtc`、`/api/kb/cost`、`/api/kb/symptom` 都返回 `{count, items}` 且 `count>0`
  - [ ] 非法 `kind` 返回 404 或 `{count:0, items:[]}`，不报 500
  - [ ] 返回字段和知识库 JSON 一致
- **怎么自测**：
  ```bash
  for k in dtc cost symptom; do echo "== $k =="; curl -s http://localhost:5000/api/kb/$k | head -c 200; echo; done
  ```
  **预期**：三个都返回 JSON，`count>0`。
- **对应用例**：B-010、B-011、B-012

### B2-5 报价审核 Agent（maintain）

- **目标**：`maintain.py` 匹配维修项目、查成本基准；若用户给了报价，判断是否偏离合理区间；输出报价审核 + 价格区间 + 避坑三件套。
- **改哪些文件**：`car-server/agents/maintain.py`（A 的 `routes/chat.py` 在 `maintain` 分支会调用它，你只写这个 Agent，不改 chat.py）
- **完成定义 DoD**：
  - [ ] 能从文本提取报价金额（如"800 元"）和项目（"机油机滤"）
  - [ ] 查 `kb_cost` 得到合理区间，组装 6.1 的 `reply`（`title/summary/blocks/price_text/price_range`）
  - [ ] 报价高于区间上限时，`blocks` 含 `warn`："超出市场价上限，建议多比价"
  - [ ] 含避坑三件套（至少 3 条建议性信息）
  - [ ] 命中不到项目时 `hit=false`，给澄清，不编造
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"4S店报价800元换机油机滤合理吗","mode":"text","image_label":""}'
  ```
  **预期**：`agent=maintain`，`reply.price_range` 类似 `[400,700]`，含一条"报价偏高"的 `warn`。
- **对应用例**：B-004

### ✅ 阶段 2 验收

- [ ] 三个知识库都能通过 `/api/kb/<kind>` 查到，`count>0`
- [ ] `maintain` 能判断 800 元换机油偏高
- [ ] 返回 JSON 字段与总文档 6.1 / 第 8 节 Schema 一致

---

## 阶段 3：上下文与维修记录闭环（后端）

### B3-1 services/context.py + VIN 脱敏

- **目标**：用内存（或简单文件）按 `user_id` 存车辆上下文；提供 VIN 脱敏方法。
- **改哪些文件**：`car-server/services/context.py`
- **完成定义 DoD**：
  - [ ] `get_context(user_id)` / `update_context(user_id, data)` 可用
  - [ ] `mask_vin(vin)` 把中间位变 `*`（如 `LFMAP22CXXX123456` → `LFMA*********3456`）
  - [ ] 默认 `test_user_001` 有一份初始上下文（卡罗拉那条）
- **怎么自测**：
  ```bash
  cd car-server
  .venv/Scripts/python -c "from services.context import mask_vin; print(mask_vin('LFMAP22CXXX123456'))"
  ```
  **预期**：打印脱敏后的 VIN（中间是 `*`，保留头尾）。
- **对应用例**：B-006

### B3-2 GET/POST /api/context

- **目标**：读取与更新车辆上下文。
- **改哪些文件**：`car-server/routes/context.py`（调用你写的 `services/context.py`）
- **完成定义 DoD**：
  - [ ] `GET /api/context?user_id=test_user_001` 返回 `car_model/vin/mileage/location/receipts`
  - [ ] 返回的 `vin` 默认脱敏
  - [ ] `POST /api/context` 能更新字段，再次 GET 能读到新值
- **怎么自测**：
  ```bash
  # 读
  curl -s "http://localhost:5000/api/context?user_id=test_user_001"
  # 改
  curl -s -X POST http://localhost:5000/api/context -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","mileage":"40,000 km"}'
  # 再读，确认 mileage 变了
  curl -s "http://localhost:5000/api/context?user_id=test_user_001"
  ```
  **预期**：第一次返回卡罗拉默认值且 VIN 脱敏；改完后里程变成 `40,000 km`。
- **对应用例**：B-006、B-007

### B3-3 services/receipt.py + POST /api/receipt

- **目标**：根据用户最近一次诊断生成维修记录存根；无诊断记录时返回空。
- **改哪些文件**：`car-server/services/receipt.py`、`car-server/routes/receipt.py`（`app.py` 不要改）
- **完成定义 DoD**：
  - [ ] `POST /api/receipt` 返回 `shop/shop_code/car_model/vin/location/created_at/items/total`
  - [ ] 用户**有过诊断**时 `items` 非空、`total>0`
  - [ ] 用户**无诊断**时 `items=[]`、`total=0`
  - [ ] 标注为模拟（不接真实门店）；`created_at` 用真实时间字符串
- **怎么自测**：
  ```bash
  # 无诊断（先确保重置了该用户）→ 空
  curl -s -X POST http://localhost:5000/api/receipt -H "content-type: application/json" \
    -d '{"user_id":"test_user_001"}'
  # 先做一次诊断
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"800元换机油机滤合理吗","mode":"text","image_label":""}' >/dev/null
  # 再生成 → 有数据
  curl -s -X POST http://localhost:5000/api/receipt -H "content-type: application/json" \
    -d '{"user_id":"test_user_001"}'
  ```
  **预期**：第一次 `items=[]`、`total=0`；诊断后 `items` 有数据、`total>0`。
- **对应用例**：B-008、B-009

### ✅ 阶段 3 验收

- [ ] `/api/context` 能读能改，VIN 默认脱敏
- [ ] `/api/receipt` 无记录返回空、有记录返回存根
- [ ] 所有返回字段符合总文档 6.2~6.4 Schema

---

## 阶段 4：健壮性与演示打磨

### B4-1 知识库未命中回退（不编造）

- **目标**：问一个知识库里没有的问题时，返回澄清建议而不是瞎编。
- **完成定义 DoD**：
  - [ ] 未命中时 `hit=false`，`reply` 是澄清/补充信息提示
  - [ ] 不出现编造的故障点/价格
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"今天天气怎么样","mode":"text","image_label":""}'
  ```
  **预期**：`hit=false`，回复是"需要补充信息/这不是车况问题"之类，无编造结论。
- **对应用例**：B-014

### B4-2 高风险强提醒

- **目标**：高风险症状（机油报警、水温过高等）必须给停车/线下检查的强提醒。
- **完成定义 DoD**：
  - [ ] 命中 `level=高` 的症状时，`reply` 含明显的强提醒块（建议立即停车/救援）
  - [ ] 响应里能体现风险等级（如 `blocks` 有 `danger`）
- **怎么自测**：
  ```bash
  curl -s -X POST http://localhost:5000/api/chat -H "content-type: application/json" \
    -d '{"user_id":"test_user_001","text":"机油报警灯亮了","mode":"text","image_label":""}'
  ```
  **预期**：返回含"立即停车/尽快线下检查"的强提醒。
- **对应用例**：B-019

### B4-3 演示数据与字段一致性校验

- **目标**：保证所有接口返回字段稳定、与 Schema 一致，演示不翻车。
- **完成定义 DoD**：
  - [ ] 4 类 chat 输入（症状/故障码/报价/图片）返回结构一致，关键字段不缺
  - [ ] 知识库、context、receipt 字段名与总文档完全一致
  - [ ] 跑一遍演示脚本顺序（总文档第 12 节）接口不报错
- **怎么自测**：把第 12 节演示顺序对应的 curl 串起来跑一遍，逐个看返回字段齐全。
- **对应用例**：I-002~I-006

### ✅ 阶段 4 验收

- [ ] 未命中不编造
- [ ] 高风险有强提醒
- [ ] 演示脚本涉及的接口全部返回正常、字段齐全

---

## 附：B 的独立通过标准（进联调前自检）

- [ ] 不依赖小程序页面，全部接口用 curl/pytest 能跑通
- [ ] 进度看板全部打勾
- [ ] 所有接口返回符合总文档 Schema
- [ ] 知识库命中与未命中都覆盖到
- [ ] 已在 `docs/testing/ai-test-report-template.md` 复制一份并填好测试报告，结论为"允许进入联调"

---

## 附：一段顺手的"接口冒烟"自检（全部跑一遍）

后端启动后，复制整段到 Git Bash 跑，快速看哪个接口挂了：

```bash
BASE=http://localhost:5000
echo "1) ping";    curl -s $BASE/api/ping | head -c 120; echo
echo "2) kb dtc";  curl -s $BASE/api/kb/dtc | head -c 120; echo
echo "3) 症状";    curl -s -X POST $BASE/api/chat -H "content-type: application/json" -d '{"user_id":"test_user_001","text":"咕噜咕噜响","mode":"text","image_label":""}' | head -c 160; echo
echo "4) 故障码";  curl -s -X POST $BASE/api/chat -H "content-type: application/json" -d '{"user_id":"test_user_001","text":"P0300","mode":"text","image_label":""}' | head -c 160; echo
echo "5) 报价";    curl -s -X POST $BASE/api/chat -H "content-type: application/json" -d '{"user_id":"test_user_001","text":"800元换机油机滤合理吗","mode":"text","image_label":""}' | head -c 160; echo
echo "6) context"; curl -s "$BASE/api/context?user_id=test_user_001" | head -c 160; echo
echo "7) receipt"; curl -s -X POST $BASE/api/receipt -H "content-type: application/json" -d '{"user_id":"test_user_001"}' | head -c 160; echo
```

每行都能看到 JSON、没有报错或空响应，就说明接口层是通的。
