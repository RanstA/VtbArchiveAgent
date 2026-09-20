import os
import sys
from pathlib import Path


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if (
    str(BACKEND_ROOT)
    not in sys.path
):
    sys.path.insert(
        0,
        str(BACKEND_ROOT),
    )


# API tests 会 import app.main，
# 从而初始化 Settings。
#
# 测试环境不应该依赖开发者机器
# 是否恰好存在 .env。
os.environ.setdefault(
    "ARCHIVE_DATA_ROOT",
    str(BACKEND_ROOT),
)