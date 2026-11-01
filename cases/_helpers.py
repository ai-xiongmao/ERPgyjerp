"""用例公共小工具：单位名称拼接、提示文案校验等。"""

import re


def expected_other(basic, unit, ratio):
    """副单位列的展示格式：`箱=10个`（副单位=比例基本单位）。"""
    return f"{unit}={ratio}{basic}"


def expected_name(basic, unit, ratio):
    """单位名称列的展示格式：`个/(箱=10个)`。"""
    return f"{basic}/({expected_other(basic, unit, ratio)})"


NAME_PATTERN = re.compile(r"^.+/.+=.+$")


def message_has(messages, needle):
    return any(needle in (message or "") for message in messages)


def cell_blank(value):
    """“未填写的副单位显示为空”——排除 null/undefined 这类前端泄漏。"""
    return value in ("", None)
