# 车小智服务端（car-server）

车小智小程序的 Flask 服务端，当前已进入连调阶段：`/api/chat` 会调用 scheduler 与多个 Agent，知识库/RAG、ASR、车辆上下文、用户体系和记录持久化都已接入。

## 技术栈

- Python 3.11
- Flask 3.x
- flask-cors（开发期允许跨域）
- langgraph / chromadb / sentence-transformers（本地 RAG）
- dashscope（ASR、图片识别、文字大模型；Key 从 MySQL 读取）
- MySQL 8.x + PyMySQL（用户体系，见 `requirements-user.txt`）

## 目录结构

```text
car-server/
  app.py
  routes/
    health.py         # /api/ping、/
    chat.py           # /api/chat：调度 Agent 并返回结构化回复
    asr.py            # /api/asr：语音转文字，真实调用 DashScope
    context.py        # /api/context：优先 MySQL user_vehicle，失败降级内存
    receipt.py        # /api/receipt：当前会话维修存根
    kb.py             # /api/kb/<kind>、/api/kb/<kind>/<item_id>
    user.py           # /api/user/*：登录、资料、隐私、记录
  agents/             # scheduler / dtc / symptom / maintain / part
  services/           # rag / context / receipt / asr / llm / vision / model_keys / db / user
  knowledge/          # kb_dtc / kb_cost / kb_symptom.json
  sql/                # user_schema.sql
  .chroma/            # RAG 本地向量库（自动生成，git 忽略，可重建）
  requirements.txt
  requirements-user.txt
```

## 本地启动

### 1. 创建虚拟环境并安装依赖

```bat
cd car-server
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r requirements-user.txt
```

`requirements-user.txt` 只用于 `/api/user/*` 和 `/api/context` 的 MySQL 优先读取。没有 MySQL 时，服务仍应能启动，诊断主链路会降级到内存车辆上下文。

### 2. 启动服务

```bat
.venv\Scripts\python app.py
```

启动后默认监听：

- `http://127.0.0.1:5000`
- `http://localhost:5000`
- `http://<本机局域网IP>:5000`（真机预览时使用）

### 3. 验证接口

```bash
curl http://localhost:5000/api/ping
curl http://localhost:5000/
```

`/api/ping` 预期返回：

```json
{
  "ok": true,
  "name": "chexiaozhi-server",
  "version": "0.1.0"
}
```

## 用户体系数据库

`/api/user/*` 使用 MySQL 存放用户账号、资料、隐私、车辆、统计、咨询记录和维修记录。`/api/context` 也会优先读取 `user_vehicle`，让“我的页”维护的车辆资料和诊断上下文一致。

如果 MySQL 不可用：

- `/api/kb/*`、`/api/receipt` 仍可运行；`/api/chat` 中需要大模型的合成、图片识别、ASR 会返回明确错误。
- `/api/context` 降级到进程内默认车辆。
- `/api/user/*` 返回带 `recoverable=true` 的 503。

### 1. 建库、建表、初始化演示数据

```bash
cd car-server
mysql -u root -p < sql/user_schema.sql
```

脚本会创建 `chexiaozhi_user`，并初始化：

- `users`：演示账号 `user_10001`
- `user_privacy`：默认隐私设置
- `user_vehicle`：演示车辆资料
- `user_stats`：演示统计数据
- `user_consultations`：演示咨询记录
- `user_repairs`：演示维修记录
- `model_api_keys`：DashScope 等模型供应商 Key（脚本创建表，不写入真实 Key）

验证：

```bash
mysql -u root -p -e "USE chexiaozhi_user; SHOW TABLES;"
mysql -u root -p -e "USE chexiaozhi_user; SELECT car_model,vin,mileage,location FROM user_vehicle WHERE user_id='user_10001';"
```

### 2. 创建本地开发账号

默认 `.env.example` 使用：

```text
DB_USER=cxz_user
DB_PASSWORD=cxz_user_dev_2026
DB_NAME=chexiaozhi_user
```

执行授权：

```bash
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'cxz_user'@'localhost' IDENTIFIED BY 'cxz_user_dev_2026'; CREATE USER IF NOT EXISTS 'cxz_user'@'127.0.0.1' IDENTIFIED BY 'cxz_user_dev_2026'; GRANT SELECT, INSERT, UPDATE, DELETE ON chexiaozhi_user.* TO 'cxz_user'@'localhost'; GRANT SELECT, INSERT, UPDATE, DELETE ON chexiaozhi_user.* TO 'cxz_user'@'127.0.0.1'; FLUSH PRIVILEGES;"
```

复制配置：

```bat
copy .env.example .env
```

### 3. 写入 DashScope Key 到数据库

语音识别、图片识别、文字大模型都共用 `model_api_keys` 表里的 `dashscope` Key。不要把真实 Key 写入前端、后端源码或 `.env`。

交互式写入：

```bat
cd car-server
.venv\Scripts\python tools\set_model_key.py
```

或者在当前 shell 已临时设置 `DASHSCOPE_API_KEY` 时执行同一个脚本，脚本只会把 Key 写入 MySQL，不会打印 Key。

最小真实能力检查：

```bat
.venv\Scripts\python tools\check_dashscope_key.py
```

该脚本会用数据库里的 Key 分别检查文字模型、视觉模型和 ASR 模型。ASR 使用极短测试 WAV，若返回“接口可达但无可识别人声”，说明 Key/模型权限/传输已打通，但测试音频本身没有有效语音内容。

## 接口

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| GET | `/api/ping` | 固定健康检查 |
| GET | `/` | 服务信息 + 接口列表 |
| POST | `/api/chat` | scheduler → Agent → 知识库/RAG → DashScope 合成 → 结构化回复 |
| POST | `/api/chat/image` | 上传图片 → DashScope 视觉模型 → 结构化回复 |
| POST | `/api/asr` | 上传语音 → DashScope ASR → 文本 |
| GET/POST | `/api/context` | 优先 MySQL 车辆资料，失败降级内存 |
| POST | `/api/receipt` | 根据当前会话诊断项生成维修存根 |
| GET | `/api/kb/<kind>` | 知识库列表，kind=dtc/cost/symptom |
| GET | `/api/kb/<kind>/<item_id>` | 知识库详情 |
| POST | `/api/user/login` | 微信/游客登录 MVP |
| GET/PATCH | `/api/user/profile` | 用户资料 |
| GET/PATCH | `/api/user/privacy` | 隐私设置 |
| GET | `/api/user/stats` | 我的页统计 |
| GET/PATCH | `/api/user/vehicle` | 用户车辆资料 |
| GET/POST | `/api/user/consultations` | 咨询记录 |
| GET/POST | `/api/user/repairs` | 维修记录 |

## 常用验证

```bat
.venv\Scripts\python -m pytest
```

关键接口：

```bash
curl "http://localhost:5000/api/context?user_id=user_10001"
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"user_id\":\"user_10001\",\"text\":\"P0300 是什么意思\",\"mode\":\"text\",\"image_label\":\"\"}"
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"user_id\":\"user_10001\",\"text\":\"已选择报价单图片\",\"mode\":\"image\",\"image_label\":\"报价单\"}"
curl -X POST http://localhost:5000/api/receipt -H "Content-Type: application/json" -d "{\"user_id\":\"user_10001\"}"
```

## 常见问题

- 端口被占用：修改 `app.py` 末尾 `app.run(..., port=5000)`，并同步修改小程序 `utils/request.ts` 的 `BASE_URL`。
- 小程序请求失败：确认微信开发者工具已勾选「不校验合法域名」，且服务端已启动。
- MySQL 未启动：诊断主链路会继续运行；用户相关接口会返回可恢复错误。
