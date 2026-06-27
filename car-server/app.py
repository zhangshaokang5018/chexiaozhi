# app.py
# 车小智服务端 - 最小基座
# 阶段 0：只提供 /api/ping，验证小程序与服务端最小联通。
# 后续阶段再扩展 /api/chat、/api/context、/api/receipt、/api/kb/<kind> 等接口。

from flask import Flask, jsonify
from flask_cors import CORS

APP_NAME = "chexiaozhi-server"
APP_VERSION = "0.1.0"

app = Flask(__name__)
# 开发阶段允许跨域，方便浏览器 / 工具直接调试接口
CORS(app)


@app.get("/api/ping")
def ping():
    """验证小程序与服务端联通。返回固定 JSON。"""
    return jsonify(
        {
            "ok": True,
            "name": APP_NAME,
            "version": APP_VERSION,
        }
    )


@app.get("/")
def index():
    """根路径，便于浏览器直接确认服务已启动。"""
    return jsonify(
        {
            "ok": True,
            "name": APP_NAME,
            "version": APP_VERSION,
            "endpoints": ["/api/ping"],
        }
    )


if __name__ == "__main__":
    # host=0.0.0.0 便于真机/同局域网设备访问；端口默认 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
