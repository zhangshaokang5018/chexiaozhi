# 车小智服务端（car-server）

车小智小程序服务端。当前为**最小基座（阶段 0）**，仅提供 `/api/ping`，用于验证小程序与服务端最小联通。

## 技术栈

- Python 3.11
- Flask 3.x
- flask-cors（开发期允许跨域）

## 目录结构

```text
car-server/
  app.py            # Flask 入口，目前只有 /api/ping
  requirements.txt  # 依赖
  README.md
```

> 注：文档中规划的 `agents/`、`knowledge/`、`services/` 等目录属于后续阶段，基座阶段尚未创建。

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

### GET `/api/ping`

用途：验证小程序与服务端联通。返回固定 JSON（见上）。

### GET `/`

根路径，返回服务信息与可用接口列表，方便浏览器直接确认服务已启动。

## 常见问题

- **端口被占用**：修改 `app.py` 末尾 `app.run(..., port=5000)` 的端口，并同步修改小程序 `utils/request.ts` 的 `BASE_URL`。
- **小程序请求失败**：确认微信开发者工具已勾选「不校验合法域名」，且服务端已启动。
