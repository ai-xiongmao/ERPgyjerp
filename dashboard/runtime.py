"""控制台的进程级参数。

注意 `PORT` 是**可变**的：`--port` 会在启动时改写它，而 health 探测与
同源校验都是晚于启动才读的。所以其它模块必须写 `runtime.PORT`（模块属性访问），
不能写 `from dashboard.runtime import PORT`——后者会把启动时的默认值复制一份进
自己的命名空间，改端口后界面显示 8760 但实际监听 8800。
"""

from __future__ import annotations

import os
import time

HOST = "127.0.0.1"
PORT = int(os.environ.get("ERP_DASH_PORT", "8760"))
STARTED_AT = time.time()

CASE_TTL = 300          # 用例清单缓存（秒）
HEALTH_TTL = 5          # 环境探测周期（秒）
MAX_LOG_LINES = 6000    # 单个任务保留的日志上限，防止长跑把内存吃掉
LOGIN_PATH_HINT = "login"
