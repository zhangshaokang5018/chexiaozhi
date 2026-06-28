# chexiaozhi（车小智）

基于多 Agent 协同的汽车售后商机挖掘与车况决策助手，小程序 MVP 已进入连调阶段。

开发文档统一入口：[`docs/development/README.md`](docs/development/README.md)

## 当前状态

- 小程序前端已接首页、聊天页、知识库、我的、咨询记录、维修存根等页面。
- 文字咨询走 `POST /api/chat`，由 scheduler 分发到故障码、症状、报价保养、图片识别等 Agent。
- 知识咨询结合本地 JSON 知识库与 RAG；RAG 或模型不可用时会自动降级到规则/关键词链路。
- 语音入口走“按住说话 → /api/asr → 回填文本”，未配置 ASR Key 时返回可演示的降级文本。
- 图片入口会真实调用相机/相册；当前后端按 `mode=image + image_label` 做结构化模拟识别，后续可替换为视觉大模型。
- 用户登录、资料、隐私、车辆、咨询记录、维修记录走 `/api/user/*` + MySQL。
- `/api/context` 已优先读取 MySQL `user_vehicle`，MySQL 不可用或用户不存在时降级到内存默认车辆。

## 仓库结构

```text
chexiaozhi/
  car-miniapp/        # 微信小程序（TypeScript + Less）
    miniprogram/
      pages/index/    # 首页：热门咨询、拍照入口、输入入口
      pages/chat/     # 对话页：文字、按住说话、图片咨询
      pages/kb/       # 知识库：搜索、筛选、一键咨询
      pages/profile/  # 我的页与用户资料入口
      utils/          # request / user-api / media
  car-server/         # Flask 服务端（见 car-server/README.md）
  docs/               # 产品 / 开发 / 测试文档
```

## 快速启动

### 1. 启动服务端

```bat
cd car-server
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r requirements-user.txt
.venv\Scripts\python app.py
```

验证：

```bash
curl http://localhost:5000/api/ping
curl http://localhost:5000/
```

`/` 会返回当前服务信息和已注册接口列表。

### 2. 配置 MySQL（用户体系）

用户体系使用本地 MySQL，建库建表脚本在 [`car-server/sql/user_schema.sql`](car-server/sql/user_schema.sql)。如果暂时没有 MySQL，诊断、知识库、ASR 降级、维修存根生成仍可运行；受影响的是登录、用户资料、历史记录持久化等 `/api/user/*` 能力。

```bat
cd car-server
mysql -u root -p < sql/user_schema.sql
copy .env.example .env
```

`.env` 默认使用：

```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=cxz_user
DB_PASSWORD=cxz_user_dev_2026
DB_NAME=chexiaozhi_user
```

更多账号授权步骤见 [`car-server/README.md`](car-server/README.md)。

### 3. 启动小程序

1. 用微信开发者工具打开 `car-miniapp` 目录。
2. 在「详情 → 本地设置」勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。
3. 编译后从首页进入聊天页，文字、图片、语音入口都应可触发对应链路。

真机预览时，把 [`car-miniapp/miniprogram/utils/request.ts`](car-miniapp/miniprogram/utils/request.ts) 的 `BASE_URL` 从 `localhost` 改成电脑局域网 IP，并确保手机与电脑在同一网络。

## 常用验证

```bat
cd car-miniapp
npm run typecheck

cd ..\car-server
.venv\Scripts\python -m pytest
```

关键接口：

```bash
curl http://localhost:5000/api/context?user_id=user_10001
curl -X POST http://localhost:5000/api/chat -H "Content-Type: application/json" -d "{\"user_id\":\"user_10001\",\"text\":\"P0300 是什么意思\",\"mode\":\"text\",\"image_label\":\"\"}"
curl -X POST http://localhost:5000/api/receipt -H "Content-Type: application/json" -d "{\"user_id\":\"user_10001\"}"
```
