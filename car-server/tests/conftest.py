# tests/conftest.py —— A 后端自动化测试公共夹具
#
# - 把 car-server 根目录加入 sys.path，使 import app/agents/services/routes 不依赖运行 cwd。
# - client：Flask 测试客户端（无需真正起服务端，用 test_client 跑 HTTP 全链路）。
# - reset_ctx：每个用例前后清理 services.context 的进程内内存态，保证用例相互隔离。

import os
import sys

import pytest

# car-server 根目录（本文件位于 car-server/tests/）
_SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_ROOT not in sys.path:
    sys.path.insert(0, _SERVER_ROOT)

from app import create_app  # noqa: E402
from services import context as ctx_service  # noqa: E402

# 用例中可能用到的 user_id，跑前跑后都清掉，避免沉淀互相污染
TEST_USER_IDS = ["test_user_001", "u_chat_receipt", "u_ctx", "guest_demo"]


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_ctx():
    for uid in TEST_USER_IDS:
        ctx_service.reset_user(uid)
    yield
    for uid in TEST_USER_IDS:
        ctx_service.reset_user(uid)
