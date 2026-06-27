# app.py
# 车小智服务端入口。
#
# 【重要 · 协作约定】本文件已"冻结"：所有路由都通过蓝图(Blueprint)注册，A/B 双方
# 各自的路由文件已提前建好并在此注册。开发功能时请只改 routes/ 下属于你的文件，
# 不要再改本文件，从而避免合并冲突。详见 docs/development/工程协作约定.md。

from flask import Flask
from flask_cors import CORS

from routes.health import health_bp      # 公共：/api/ping、/
from routes.chat import chat_bp           # A 负责：/api/chat
from routes.context import context_bp     # B 负责：/api/context
from routes.receipt import receipt_bp     # B 负责：/api/receipt
from routes.kb import kb_bp               # B 负责：/api/kb/<kind>


def create_app() -> Flask:
    app = Flask(__name__)
    # 开发阶段允许跨域，方便浏览器 / 工具直接调试接口
    CORS(app)

    for bp in (health_bp, chat_bp, context_bp, receipt_bp, kb_bp):
        app.register_blueprint(bp)

    return app


app = create_app()


if __name__ == "__main__":
    # host=0.0.0.0 便于真机/同局域网设备访问；端口默认 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
