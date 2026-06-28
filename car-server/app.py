# app.py
# 车小智服务端入口。
#
from flask import Flask
from flask_cors import CORS
from importlib.util import find_spec

from routes.health import health_bp      # 公共：/api/ping、/
from routes.chat import chat_bp           # /api/chat
from routes.asr import asr_bp             # /api/asr
from routes.context import context_bp     # /api/context
from routes.receipt import receipt_bp     # /api/receipt
from routes.kb import kb_bp               # /api/kb/<kind>

if find_spec("routes.user"):
    try:
        from routes.user import user_bp        # /api/user/*
    except Exception as exc:  # noqa: BLE001
        # routes/user.py 存在但导入失败时，跳过用户蓝图，保证诊断主链路仍可启动。
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
