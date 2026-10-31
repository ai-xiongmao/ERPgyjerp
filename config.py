"""全局配置：目标系统入口与桌面 MyTest 浏览器的连接参数。

MyTest 是 Chromium 内核浏览器，启动时已带 --remote-debugging-port=9231
（见桌面快捷方式 MyTest.exe.lnk），因此可以直接用 CDP 接入，
复用其中已经登录好的会话，无需重新走账号/验证码登录。
"""

# 管伊佳 ERP 线上地址
BASE_URL = "https://cloud.gyjerp.com"

# 商品管理 - 多单位页面路径
UNIT_PATH = "/system/unit"

# 登录页路径（会话过期时前端会跳到这里）
LOGIN_PATH = "/user/login"

# 桌面 MyTest 浏览器的 CDP 调试端点
CDP_ENDPOINT = "http://127.0.0.1:9231"

# 页面里识别目标业务系统的 URL 关键字
APP_URL_KEYWORD = "gyjerp"

# Playwright 默认元素等待超时（毫秒）
DEFAULT_TIMEOUT = 15000

# 每个 UI 动作之间的间隔（毫秒）。放慢节奏，避免和页面异步渲染、
# 服务端校验抢跑；可用环境变量 ERP_ACTION_DELAY_MS 覆盖，设 0 关闭。
import os as _os

ACTION_DELAY_MS = int(_os.environ.get("ERP_ACTION_DELAY_MS", "1000"))
