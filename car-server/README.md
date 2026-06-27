# 车小智服务端（car-server）

车小智小程序服务端。基座已完成；当前采用 **Flask 蓝图(Blueprint)** 结构，A/B 各自的路由分文件管理，便于并行开发不冲突。

## 技术栈

- Python 3.11
- Flask 3.x
- flask-cors（开发期允许跨域）

## 目录结构

```text
car-server/
  app.py              # 🔒 入口：创建 app + 注册所有蓝图（已冻结，勿改）
  routes/
    health.py         # 公共：/api/ping、/
    chat.py           # A：/api/chat（占位，待 A 实现）
    context.py        # B：/api/context（占位，待 B 实现）
    receipt.py        # B：/api/receipt（占位，待 B 实现）
    kb.py             # B：/api/kb/<kind>（已读取 knowledge 的基础实现）
  agents/             # A：scheduler/symptom/dtc/part；B：maintain
  services/           # B：context.py / receipt.py / rag.py（本地 RAG 检索）
  knowledge/          # B 独家维护：kb_dtc / kb_cost / kb_symptom.json（起步数据已就绪）
  .chroma/            # RAG 本地向量库（自动生成，git 忽略，可重建）
  requirements.txt
  README.md
```

> 谁能改哪些文件、如何避免合并冲突，见 `docs/development/工程协作约定.md`。
> RAG 为完全本地方案（bge-small-zh + Chroma，无需 Key），建索引步骤见 `docs/development/后端服务启动说明.md` 第 3.5 节。

## 本地启动

### 1. 创建虚拟环境并安装依赖

Windows（PowerShell / CMD）：

```bat
cd car-server
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

Git Bash / macOS / Linux：

```bash
cd car-server
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
```

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
```

预期返回：

```json
{
  "ok": true,
  "name": "chexiaozhi-server",
  "version": "0.1.0"
}
```

## 接口

| 方法 | 路径 | 归属 | 状态 |
| --- | --- | --- | --- |
| GET | `/api/ping` | 公共 | ✅ 固定 JSON |
| GET | `/` | 公共 | ✅ 服务信息 + 接口列表 |
| POST | `/api/chat` | A | 🚧 占位，待实现 |
| GET/POST | `/api/context` | B | 🚧 占位，待实现 |
| POST | `/api/receipt` | B | 🚧 占位，待实现 |
| GET | `/api/kb/<kind>` | B | ✅ 基础实现（读 knowledge，kind=dtc/cost/symptom） |

> 占位接口会返回带 `"_stub": true` 的 JSON，仅用于先打通联通，字段以总文档第 6 节为准。

## 常见问题

- **端口被占用**：修改 `app.py` 末尾 `app.run(..., port=5000)` 的端口，并同步修改小程序 `utils/request.ts` 的 `BASE_URL`。
- **小程序请求失败**：确认微信开发者工具已勾选「不校验合法域名」，且服务端已启动。
