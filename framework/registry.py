"""用例注册表：把每个自动化函数绑定到测试用例编号（TC-UNIT-xxx）。

设计意图：
1. 用例编号是唯一主键——报告、控制台输出、写回 Excel「执行结果」列都靠它对齐；
2. 编号顺序即执行顺序（TC-UNIT-001 → 044），便于和用例表逐条对照；
3. 无法自动化的用例也登记进来（blocked=原因），保证「44 条用例都有交代」，
   而不是悄悄漏掉；
4. 一个编号可以有**两套实现**：UI（func）与接口（api），跑哪套由 --layer 决定。
   接口实现用 `@api_case(...)` 挂在已登记的编号上，标题/标签/优先级直接复用，
   避免两边各写一份导致口径漂移。
"""

from dataclasses import dataclass, replace

# 执行结果口径与用例表一致
PASS = "通过"
FAIL = "失败"
BLOCKED = "阻塞"
ERROR = "异常"
NOT_COVERED = "未覆盖"   # 该层没有实现（例如页面入口类没有接口版），不计失败

LAYERS = ("ui", "api")


@dataclass(frozen=True)
class Case:
    cid: str                 # 用例编号，如 TC-UNIT-012
    title: str               # 用例标题
    tag: str                 # 用例标签（页面入口 / 查询 / 新增 …）
    priority: str            # 优先级
    func: object = None      # UI 实现；None 表示该层没写
    blocked: str = ""        # 阻塞原因；非空则不执行
    api: object = None       # 接口实现；None 表示该层没写
    api_unblocked: bool = False   # 接口层可用测试数据自证，不受 blocked 限制

    def func_for(self, layer="ui"):
        return self.api if layer == "api" else self.func

    def blocked_for(self, layer="ui"):
        """按层取阻塞原因：接口层被显式解锁时返回空。"""
        if layer == "api" and self.api_unblocked:
            return ""
        return self.blocked

    def runnable_on(self, layer="ui"):
        return self.func_for(layer) is not None and not self.blocked_for(layer)

    @property
    def runnable(self):
        """兼容旧写法：默认按 UI 层判断是否可执行。"""
        return self.runnable_on("ui")

    @property
    def layers(self):
        got = []
        if self.func is not None:
            got.append("ui")
        if self.api is not None:
            got.append("api")
        return got


_REGISTRY = {}


def case(cid, title, tag="", priority="", blocked=""):
    """登记一条可执行用例（UI 层）。用法：

        @case("TC-UNIT-013", "填写基本单位+副单位+比例保存", "新增", "高")
        def tc_013(ctx):
            ...
    """

    def deco(func):
        existing = _REGISTRY.get(cid)
        if existing is not None and existing.api is not None:
            # 该编号已经挂过接口实现：保留 api，只更新 UI 侧的元信息与函数
            _REGISTRY[cid] = replace(existing, title=title, tag=tag,
                                     priority=priority, func=func, blocked=blocked)
        else:
            _REGISTRY[cid] = Case(cid, title, tag, priority, func, blocked)
        return func

    return deco


def api_case(cid, title="", tag="", priority="", unblock=False):
    """给已登记的编号挂一个接口实现（同编号双轨）。

    标题/标签/优先级沿用 UI 层登记的，保证两边口径一致；
    若该编号还没登记（纯接口新增的用例），才用这里传的元信息建一条。

    unblock=True：UI 层因「破坏真实业务数据」而阻塞，但接口层可以用测试前缀
    自造数据完成验证（例如「删除被商品引用的单位」），此时**只解除接口层的阻塞**，
    UI 层仍如实登记为阻塞——blocked 原因不能因为接口层能跑就被抹掉。
    """

    def deco(func):
        existing = _REGISTRY.get(cid)
        if existing is None:
            _REGISTRY[cid] = Case(cid, title, tag, priority, None, "", func,
                                  api_unblocked=unblock)
        else:
            _REGISTRY[cid] = replace(existing, api=func, api_unblocked=unblock)
        return func

    return deco


def manual(cid, title, tag="", priority="", reason=""):
    """登记一条不执行的用例（需人工验证 / 前置条件不具备）。"""
    _REGISTRY[cid] = Case(cid, title, tag, priority, None, reason)


def all_cases():
    return sorted(_REGISTRY.values(), key=lambda c: c.cid)


def prefix_of(cid):
    """取模块前缀：TC-UNIT-012 → UNIT。"""
    parts = cid.split("-")
    return parts[1].upper() if len(parts) >= 2 else ""


def find(cid):
    return _REGISTRY.get(cid)


def coverage(layer="ui"):
    """返回 (该层有实现的条数, 总条数)。"""
    total = len(_REGISTRY)
    return sum(1 for c in _REGISTRY.values() if c.runnable_on(layer)), total


def select(only=None, tags=None, start=None, prefixes=None, layer=None):
    """按编号 / 标签 / 模块前缀 / 起始编号筛选用例。

    layer 传入时，只保留该层有实现的用例（未覆盖的不进执行计划）。
    """
    cases = all_cases()
    if layer:
        cases = [c for c in cases if c.runnable_on(layer) or c.blocked_for(layer)]
    if only:
        wanted = [c.strip().upper() for c in only if c.strip()]
        cases = [c for c in cases if c.cid.upper() in wanted]
    if tags:
        wanted_tags = [t.strip() for t in tags if t.strip()]
        cases = [c for c in cases if c.tag in wanted_tags]
    if prefixes:
        wanted_prefixes = [p.strip().upper() for p in prefixes if p.strip()]
        cases = [c for c in cases if prefix_of(c.cid) in wanted_prefixes]
    if start:
        cases = [c for c in cases if c.cid >= start]
    return cases
