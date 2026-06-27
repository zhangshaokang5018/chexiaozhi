# 车小智服务端（car-server）

车小智小程序服务端。基座已完成；当前采用 **Flask 蓝图(Blueprint)** 结构，A/B 各自的路由分文件管理，便于并行开发不冲突。

## 技术栈

- Python 3.11
- Flask 3.x
- flask-cors（开发期允许跨域）
- A 主业务：langgraph / chromadb / sentence-transformers（本地 RAG）、dashscope（ASR，可选）
- B 用户体系：**MySQL 8.x** + PyMySQL（见 `requirements-user.txt`）；A 不依赖

## 目录结构

```text
car-server/
  app.py              # 🔒 入口：创建 app + 注册所有蓝图（已冻结：user 蓝图自动注册且容错，勿改）
  routes/
    health.py         # 公共：/api/ping、/
    chat.py           # A：/api/chat（对话主入口）
    asr.py            # A：/api/asr（语音转文字）
    context.py        # A：/api/context（车辆上下文）
    receipt.py        # A：/api/receipt（维修存根）
    kb.py             # A：/api/kb/<kind>（知识库，已接 RAG）
    user.py           # B：/api/user/*（待新增，存在即自动注册）
  agents/             # A：scheduler / maintain（已实现）；dtc / symptom / part（待 A 新建）
  services/           # A：rag.py / context.py / receipt.py / asr.py
                      # B：user.py（用户业务）、db.py（MySQL 连接，待 B 新增）
  knowledge/          # A 维护：kb_dtc / kb_cost / kb_symptom.json
  sql/                # B：user_schema.sql（用户体系建库建表脚本）
  data/               # B：用户体系本地导出/缓存（已 gitignore，PII 不入 git）
  .chroma/            # RAG 本地向量库（自动生成，git 忽略，可重建）
  requirements.txt        # A 主业务依赖
  requirements-user.txt   # B 用户体系依赖（PyMySQL 等，与 A 分开避免冲突）
  README.md
```

> 谁能改哪些文件、如何避免合并冲突，见 `docs/development/06-并行开发边界与合并规则.md`。
> 分工：**A 负责现有主业务闭环，B 负责新增用户体系**（含 MySQL）。详见 `docs/development/README.md`。
> RAG 为完全本地方案（bge-small-zh + Chroma，无需 Key），建索引步骤见 `docs/development/02-系统架构与数据流.md` 第 6 节。

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

> **B（用户体系）额外一步**：在同一个 `.venv` 里再装用户体系依赖（A 无需此步）：
> ```bat
> .venv\Scripts\python -m pip install -r requirements-user.txt
> ```

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

## 用户体系数据库（仅 B 需要，A 可跳过）

B 的 `/api/user/*` 用 **MySQL** 存放用户账号 / 资料 / 隐私 / 车辆 / 统计。A 的主业务不使用数据库，**A 开发时无需安装 MySQL**。即使本机没有 MySQL，服务端也应能启动；若 B 的用户依赖和 `routes/user.py` 已存在且导入成功，则只有 `/api/user/*` 在查询数据库时返回可恢复错误。若 B 还没安装 `requirements-user.txt` 或 `routes/user.py` 导入失败，`app.py` 会跳过 user 蓝图注册，A 的主业务仍可用。

### 1. 安装并启动 MySQL

本机装好 MySQL 8.x（或 5.7+），确认能用 `mysql` 客户端登录，例如：

```bash
mysql -u root -p
```

### 2. 建库 + 建表 + 初始化演示数据（数据库创建步骤）

仓库已提供建库建表脚本 `car-server/sql/user_schema.sql`，它会：创建数据库 `chexiaozhi_user`（utf8mb4）→ 建 `users / user_privacy / user_vehicle / user_stats` 四张表 → 初始化一组联调演示数据：

- `users`：演示账号 `user_10001`
- `user_privacy`：默认隐私设置
- `user_vehicle`：演示车辆资料
- `user_stats`：演示统计数据

执行：

```bash
cd car-server
mysql -u root -p < sql/user_schema.sql
```

验证：

```bash
mysql -u root -p -e "USE chexiaozhi_user; SHOW TABLES;"
```

应看到 `users`、`user_privacy`、`user_vehicle`、`user_stats` 四张表。

验证演示数据：

```bash
mysql -u root -p -e "USE chexiaozhi_user; SELECT user_id,nickname,phone,profile_completed FROM users WHERE user_id='user_10001';"
mysql -u root -p -e "USE chexiaozhi_user; SELECT car_model,vin,mileage,location FROM user_vehicle WHERE user_id='user_10001';"
mysql -u root -p -e "USE chexiaozhi_user; SELECT consult_count,receipt_count,estimated_saved FROM user_stats WHERE user_id='user_10001';"
```

### 3. 创建本地开发库账号（账号密码写死到文档，便于联调）

root 只用于本机建库和授权，B 的用户接口统一使用下面这个低权限开发账号连接业务库：

```text
DB_USER=cxz_user
DB_PASSWORD=cxz_user_dev_2026
DB_NAME=chexiaozhi_user
```

执行授权：

```bash
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'cxz_user'@'localhost' IDENTIFIED BY 'cxz_user_dev_2026'; CREATE USER IF NOT EXISTS 'cxz_user'@'127.0.0.1' IDENTIFIED BY 'cxz_user_dev_2026'; GRANT SELECT, INSERT, UPDATE, DELETE ON chexiaozhi_user.* TO 'cxz_user'@'localhost'; GRANT SELECT, INSERT, UPDATE, DELETE ON chexiaozhi_user.* TO 'cxz_user'@'127.0.0.1'; FLUSH PRIVILEGES;"
```

验证开发账号能读到初始化数据：

```bash
mysql -h 127.0.0.1 -u cxz_user -pcxz_user_dev_2026 -e "USE chexiaozhi_user; SELECT user_id,nickname FROM users WHERE user_id='user_10001';"
```

> 业务演示用户是 `user_10001`。当前 MVP 是微信/游客登录模型，`users` 表不保存明文业务密码，也没有密码登录字段；`/api/user/login` 成功后由 B 返回 `session_token`。如果后续要做手机号+密码登录，需要先补 `password_hash` 字段并同步更新 `sql/user_schema.sql` 与接口契约。

> 也可由 B 实现可选的 `services/user_init.py`，用 `.venv\Scripts\python -m services.user_init` 在 Python 侧执行同一份 DDL，方便没有 `mysql` 命令行的环境一键建库。

### 4. 配置连接

复制 `.env.example` 为 `.env`，填写本机 MySQL 连接（这些键已在 `.env.example` 预留）：

```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=cxz_user
DB_PASSWORD=cxz_user_dev_2026
DB_NAME=chexiaozhi_user
```

B 在 `services/db.py` 用 PyMySQL + `python-dotenv` 读取以上配置建立连接（**连接须惰性建立，不在模块导入时连库**，详见隔离保证）。

### 与 A 的隔离保证（A 不受影响）

- **依赖隔离**：MySQL 相关依赖只在 `requirements-user.txt`，不进 `requirements.txt`；A 不装也能跑全部主业务。
- **配置隔离**：`DB_*` 仅 B 使用；A 的代码不读取这些变量。
- **启动隔离**：`app.py` 对 user 蓝图导入做了容错；且约定 B 的 `services/db.py` **惰性连库**。MySQL 未启动时，A 的 `/api/chat`、`/api/kb` 等照常工作；用户接口要么未注册（B 依赖/导入未就绪），要么在被调用时返回可恢复数据库错误（B 依赖已安装且蓝图已注册）。
- **数据隔离**：用户数据在独立库 `chexiaozhi_user`，与 A 的内存上下文 / Chroma / knowledge JSON 无交集。

## 接口

| 方法 | 路径 | 归属 | 状态 |
| --- | --- | --- | --- |
| GET | `/api/ping` | 公共 | ✅ 固定 JSON |
| GET | `/` | 公共 | ✅ 服务信息 + 接口列表 |
| POST | `/api/chat` | A | ⚠️ 已通但返回占位，待接智能体 |
| POST | `/api/asr` | A | ✅ 语音转文字（含降级） |
| GET/POST | `/api/context` | A | ✅ 接口已通 |
| POST | `/api/receipt` | A | ✅ 接口已通 |
| GET | `/api/kb/<kind>` | A | ✅ 已接 RAG（kind=dtc/cost/symptom） |
| POST | `/api/user/login` | B | 🆕 待新增（MySQL） |
| GET/PATCH | `/api/user/profile` | B | 🆕 待新增（MySQL） |
| GET/PATCH | `/api/user/privacy` | B | 🆕 待新增（MySQL） |
| GET | `/api/user/stats` | B | 🆕 待新增（MySQL） |
| GET/PATCH | `/api/user/vehicle` | B | 🆕 待新增（MySQL） |

> 接口字段以 `docs/development/03-接口契约.md` 为单一事实来源。

## 常见问题

- **端口被占用**：修改 `app.py` 末尾 `app.run(..., port=5000)` 的端口，并同步修改小程序 `utils/request.ts` 的 `BASE_URL`。
- **小程序请求失败**：确认微信开发者工具已勾选「不校验合法域名」，且服务端已启动。
