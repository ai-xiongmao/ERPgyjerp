"""断言工具：失败信息要求「说清实际值 vs 期望值」，方便直接贴进缺陷单。

不引入 pytest，原因是本项目要复用桌面 MyTest 浏览器的登录态，
用自带的连接上下文比 pytest fixture 更直观，断言只要「抛异常带信息」即可。
"""


class CaseFailed(AssertionError):
    """用例断言失败（与预期结果不一致）。"""


class CaseBlocked(Exception):
    """用例跑不下去：页面本身没问题，但缺前置数据/条件（例如类别下拉为空）。

    与「失败」区分开——失败是产品不符合预期，阻塞是这条用例在这个环境里无法验证，
    报告里记「阻塞」、Allure 里记 skipped，原因写清楚，绝不静默算通过。
    """


def blocked(reason):
    raise CaseBlocked(reason)


def check(cond, msg):
    if not cond:
        raise CaseFailed(msg)


def check_eq(actual, expected, label):
    if actual != expected:
        raise CaseFailed(f"{label}：实际 {actual!r}，期望 {expected!r}")


def check_ne(actual, unexpected, label):
    if actual == unexpected:
        raise CaseFailed(f"{label}：实际 {actual!r}，不应为 {unexpected!r}")


def check_in(member, container, label):
    if member not in container:
        raise CaseFailed(f"{label}：{member!r} 不在 {list(container)!r} 中")


def check_contains(text, needle, label):
    if needle not in (text or ""):
        raise CaseFailed(f"{label}：{text!r} 中未包含 {needle!r}")


def check_regex(text, pattern, label):
    import re

    if not re.search(pattern, text or ""):
        raise CaseFailed(f"{label}：{text!r} 不匹配 {pattern}")


def check_empty(items, label):
    if items:
        raise CaseFailed(f"{label}：应为空，实际 {list(items)!r}")


def check_true(cond, msg):
    check(bool(cond), msg)
