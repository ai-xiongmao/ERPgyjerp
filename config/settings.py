"""全局配置的实际取值。

这里只放「常量与默认值」，按环境切换的加载逻辑后续加在 `config/env/<name>.py`，
由 `config/__init__.py` 统一出口——用例与页面对象永远只 `from config import X`。

三个可被环境变量覆盖的项（CI / 预发环境用得上，本地不设即用默认值）：
    ERP_BASE_URL        目标系统地址
    ERP_CDP_ENDPOINT    桌面 MyTest 浏览器的 CDP 调试端点
    ERP_TIMEOUT         单个 Playwright 动作的默认等待超时（毫秒）
"""

import os

# 管伊佳 ERP 线上地址
BASE_URL = os.environ.get("ERP_BASE_URL", "https://cloud.gyjerp.com")

# 商品管理 - 多单位页面路径
UNIT_PATH = "/system/unit"

# 登录页路径（会话过期时前端会跳到这里）
LOGIN_PATH = "/user/login"

# 桌面 MyTest 浏览器的 CDP 调试端点。
# MyTest 是 Chromium 内核浏览器，启动时已带 --remote-debugging-port=9231
# （见桌面快捷方式 MyTest.exe.lnk），因此可以直接用 CDP 接入，
# 复用其中已经登录好的会话，无需重新走账号/验证码登录。
CDP_ENDPOINT = os.environ.get("ERP_CDP_ENDPOINT", "http://127.0.0.1:9231")

# 页面里识别目标业务系统的 URL 关键字
APP_URL_KEYWORD = "gyjerp"

# 后端接口统一前缀（jshERP 的 Spring Boot 服务挂在 /jshERP-boot 下）
API_PREFIX = "/jshERP-boot"

# Playwright 默认元素等待超时（毫秒）
DEFAULT_TIMEOUT = int(os.environ.get("ERP_TIMEOUT", "15000"))

# 每个 UI 动作之间的间隔（毫秒）。放慢节奏，避免和页面异步渲染、
# 服务端校验抢跑；可用环境变量 ERP_ACTION_DELAY_MS 覆盖，设 0 关闭。
ACTION_DELAY_MS = int(os.environ.get("ERP_ACTION_DELAY_MS", "1000"))

__all__ = [
    "BASE_URL",
    "UNIT_PATH",
    "LOGIN_PATH",
    "CDP_ENDPOINT",
    "APP_URL_KEYWORD",
    "API_PREFIX",
    "DEFAULT_TIMEOUT",
    "ACTION_DELAY_MS",
]
