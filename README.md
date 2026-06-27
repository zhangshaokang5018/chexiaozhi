# chexiaozhi（车小智）

基于多 Agent 协同的汽车售后商机挖掘与车况决策助手——小程序 MVP。

开发文档（统一入口）：[`docs/development/README.md`](docs/development/README.md)

## 当前进度：能跑通单点，主链路待打通；并行分工 A 主业务 / B 用户体系

- ✅ 基座联通：Flask 可启动、`GET /api/ping`、小程序聊天页 + `utils/request.ts`。
- ✅ 知识库链路端到端打通（`/api/kb/*` + RAG + 降级）。
- ⚠️ 对话主入口 `/api/chat` 仅做意图分类、返回占位，**尚未调用智能体**（核心断点）。
- 🆕 新增用户体系（登录 / 资料 / 隐私 / 我的页数据）作为独立开发线。

分工与计划详见开发文档：A 负责现有主业务闭环，B 负责新增用户体系，二者按文件边界并行开发。

## 仓库结构

```text
chexiaozhi/
  car-miniapp/        # 微信小程序（TypeScript + Less）
    miniprogram/
      app.json
      pages/chat/     # 聊天主界面（基座阶段展示连接状态）
      utils/request.ts
  car-server/         # Flask 服务端（见 car-server/README.md）
  docs/               # 产品 / 开发 / 测试文档
```

## 快速启动

### 1. 启动服务端

详见 [`car-server/README.md`](car-server/README.md)：

```bat
cd car-server
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

验证：浏览器或 curl 访问 `http://localhost:5000/api/ping`，应返回 `{"ok": true, ...}`。

### 2. 启动小程序

1. 用**微信开发者工具**打开 `car-miniapp` 目录（AppID 见 `project.config.json`，无 AppID 可选「测试号」）。
2. 在「详情 → 本地设置」勾选**「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**（因为本地服务端是 `http://localhost`）。
3. 编译后进入聊天页，顶部应显示 **✅ 服务已连接**，并展示服务端返回的 `name` / `version`。
4. 若显示连接失败，点击「重新检测连接」，并确认服务端已启动。

> 真机预览：把 `car-miniapp/miniprogram/utils/request.ts` 里的 `BASE_URL` 中的 `localhost` 换成电脑的局域网 IP（启动服务端时日志里会打印，例如 `http://10.105.0.133:5000`），并确保手机与电脑在同一网络。

## 验收标准（阶段 0）

- 本地启动后，小程序能展示服务端返回的 `ok=true`。
- 小程序页面显示「服务已连接」。
- 服务端日志能看到 `GET /api/ping` 请求。

基座跑通后，再按 [`docs/development/05-任务清单与开发计划.md`](docs/development/05-任务清单与开发计划.md) 进入主业务接通（A）与用户体系（B）两条开发线。
