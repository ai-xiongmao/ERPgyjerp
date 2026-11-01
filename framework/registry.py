"""用例注册表：把每个自动化函数绑定到测试用例编号（TC-UNIT-xxx）。

设计意图：
1. 用例编号是唯一主键——报告、控制台输出、写回 Excel「执行结果」列都靠它对齐；
2. 编号顺序即执行顺序（TC-UNIT-001 → 044），便于和用例表逐条对照；
3. 无法自动化的用例也登记进来（blocked=原因），保证「44 条用例都有交代」，
   而不是悄悄漏掉。
"""

from dataclasses import dataclass

# 执行结果口径与用例表一致
PASS = "通过"
FAIL = "失败"
BLOCKED = "阻塞"
ERROR = "异常"


@dataclass(frozen=True)
class Case:
    cid: str                 # 用例编号，如 TC-UNIT-012
    title: str               # 用例标题
    tag: str                 # 用例标签（页面入口 / 查询 / 新增 …）
    priority: str            # 优先级
    func: object = None      # 用例函数；None 表示人工执行
    blocked: str = ""        # 阻塞原因；非空则不执行

    @property
    def runnable(self):
        return self.func is not None and not self.blocked


_REGISTRY = {}


def case(cid, title, tag="", priority="", blocked=""):
    """登记一条可执行用例。用法：

        @case("TC-UNIT-013", "填写基本单位+副单位+比例保存", "新增", "高")
        def tc_013(ctx):
            ...
    """

    def deco(func):
        _REGISTRY[cid] = Case(cid, title, tag, priority, func, blocked)
        return func

    return deco


def manual(cid, title, tag="", priority="", reason=""):
    """登记一条不执行的用例（需人工验证 / 前置条件不具备）。"""
    _REGISTRY[cid] = Case(cid, title, tag, priority, None, reason)


def all_cases():
    return sorted(_REGISTRY.values(), key=lambda c: c.cid)


def find(cid):
    return _REGISTRY.get(cid)


def select(only=None, tags=None, start=None):
    """按编号 / 标签 / 起始编号筛选用例。"""
    cases = all_cases()
    if only:
        wanted = [c.strip().upper() for c in only if c.strip()]
        cases = [c for c in cases if c.cid.upper() in wanted]
    if tags:
        wanted_tags = [t.strip() for t in tags if t.strip()]
        cases = [c for c in cases if c.tag in wanted_tags]
    if start:
        cases = [c for c in cases if c.cid >= start]
    return cases
