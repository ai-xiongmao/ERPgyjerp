"""仓库信息 - 启用 / 禁用（TC-DEP-027 ~ 029）。

单条启用 / 禁用、未勾选时的提示。
"""

from cases.depot._const import NO_SELECT_MSG
from framework.asserts import check_contains, check_eq
from framework.registry import case


@case("TC-DEP-027", "禁用一条启用状态的仓库", "状态", "高")
def tc_dep_027(ctx):
    """勾选启用仓库 → 禁用 → 确认 → 状态变禁用。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    check_eq(depot.read_row(name)["status"], "启用", "新增后初始状态")

    title, content = depot.set_status(name, "禁用")
    check_contains(title, "确认操作", "确认框标题")
    check_contains(content, "是否操作选中数据", "确认框正文")
    check_eq(depot.read_row(name)["status"], "禁用", "禁用后的状态列")


@case("TC-DEP-028", "启用一条禁用状态的仓库", "状态", "高")
def tc_dep_028(ctx):
    """先禁用，再启用回来。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.set_status(name, "禁用")
    check_eq(depot.read_row(name)["status"], "禁用", "禁用后状态")

    title, content = depot.set_status(name, "启用")
    check_contains(title, "确认操作", "启用确认框标题")
    check_eq(depot.read_row(name)["status"], "启用", "启用后状态")


@case("TC-DEP-029", "未勾选记录点击启用/禁用", "状态", "高")
def tc_dep_029(ctx):
    """未勾选点启用/禁用：提示「请选择一条记录！」，不弹确认框。"""
    depot = ctx.depot.open()
    ctx.new_depot()
    depot.reset()
    depot.clear_selection()
    depot.drain_toasts()

    depot.click_toolbar("启用")
    depot.wait_toast(NO_SELECT_MSG)
    check_eq(depot.confirm_dialog().count(), 0, "未勾选时不应弹确认框")

    depot.drain_toasts()
    depot.click_toolbar("禁用")
    depot.wait_toast(NO_SELECT_MSG)
