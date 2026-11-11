"""配置出口：外部一律 `from config import BASE_URL`，不关心取值来自哪个文件。

现在只有 settings.py 一层；将来要区分 dev / staging 时，在这里按 ERP_ENV
选择 `config.env.<name>` 覆盖后重新导出即可，调用方零改动。
"""

from config.settings import (
    ACTION_DELAY_MS,
    API_PREFIX,
    APP_URL_KEYWORD,
    BASE_URL,
    CDP_ENDPOINT,
    DEFAULT_TIMEOUT,
    LOGIN_PATH,
    UNIT_PATH,
)

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
