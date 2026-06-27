# app.py
# 车小智服务端入口。
#
# 【重要 · 协作约定】本文件尽量不再改动：现有主业务蓝图已注册，
# B 后续新增 routes/user.py 时会自动注册 user_bp。详见
# docs/development/06-并行开发边界与合并规则.md。

from flask import Flask
from flask_cors import CORS
from importlib.util import find_spec

from routes.health import health_bp      # 公共：/api/ping、/
from routes.chat import chat_bp           # A 负责：/api/chat
from routes.asr import asr_bp             # A 负责：/api/asr
from routes.context import context_bp     # A 负责：/api/context
from routes.receipt import receipt_bp     # A 负责：/api/receipt
from routes.kb import kb_bp               # A 负责：/api/kb/<kind>

if find_spec("routes.user"):
    try:
        from routes.user import user_bp        # B 新增：/api/user/*
    except Exception as exc:  # noqa: BLE001
        # B 的 routes/user.py 存在但导入失败（语法错误 / 缺少 user_bp 等）时，
        # 降级为「不注册 user 蓝图」，保证 A 的主业务接口仍能启动，不被一起带崩。
        # 约定：routes/user.py 必须导出名为 user_bp 的 Blueprint（见 06 §2.1）。
        print(f"[app] 跳过 user 蓝图注册：导入 routes.user 失败：{exc}")
        user_bp = None
else:
    user_bp = None


def create_app() -> Flask:
    app = Flask(__name__)
    # 开发阶段允许跨域，方便浏览器 / 工具直接调试接口
    CORS(app)

    blueprints = [health_bp, chat_bp, asr_bp, context_bp, receipt_bp, kb_bp]
    if user_bp is not None:
        blueprints.append(user_bp)

    for bp in blueprints:
        app.register_blueprint(bp)

    return app


app = create_app()


if __name__ == "__main__":
    # host=0.0.0.0 便于真机/同局域网设备访问；端口默认 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
