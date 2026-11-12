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

# 服务端能力声明，随 /api/health 一起返回。
# 为什么要它：页面 HTML 是每次请求实时读盘的，Python 路由却是进程启动时就定死的。
# 改完代码不重启服务，就会出现「新按钮 + 旧路由」——点下去只能得到 404。
# 页面拿这份清单自检，对不上就把按钮标成「需重启服务」，而不是让人对着报错猜。
SERVER_VERSION = "1.1.0"
SERVER_FEATURES = ("shutdown",)

CASE_TTL = 300          # 用例清单缓存（秒）
HEALTH_TTL = 5          # 环境探测周期（秒）
MAX_LOG_LINES = 6000    # 单个任务保留的日志上限，防止长跑把内存吃掉
LOGIN_PATH_HINT = "login"
