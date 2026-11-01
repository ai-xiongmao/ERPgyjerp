"""状态与批量操作：TC-UNIT-026 ~ 029、039。"""

from framework.asserts import check, check_contains, check_eq
from framework.registry import case

NO_SELECT_MSG = "请选择一条记录！"


@case("TC-UNIT-026", "禁用一条启用状态的记录", "状态", "高")
def tc_unit_026(ctx):
    """勾选启用记录 → 禁用 → 确认 → 状态变禁用。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])
    check_eq(unit.read_row(basic)["status"], "启用", "新增后初始状态")

    title, content = unit.set_status(basic, "禁用")
    check_contains(title, "确认操作", "确认框标题")
    check_contains(content, "是否操作选中数据", "确认框正文")
    check_eq(unit.read_row(basic)["status"], "禁用", "禁用后的状态列")


@case("TC-UNIT-027", "启用一条禁用状态的记录", "状态", "高")
def tc_unit_027(ctx):
    """先把记录禁用，再启用回来。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])

    unit.set_status(basic, "禁用")
    check_eq(unit.read_row(basic)["status"], "禁用", "禁用后状态")

    title, content = unit.set_status(basic, "启用")
    check_contains(title, "确认操作", "启用确认框标题")
    check_eq(unit.read_row(basic)["status"], "启用", "启用后状态")


@case("TC-UNIT-028", "未勾选记录点击启用/禁用", "状态", "高")
def tc_unit_028(ctx):
    """未勾选时点启用/禁用：提示「请选择一条记录！」，不弹确认框、状态不变。"""
    unit = ctx.open_unit()
    ctx.new_unit([("箱", 10)])
    unit.reset()
    unit.clear_selection()

    before = unit.statuses()
    unit.drain_toasts()
    unit.click_toolbar("启用")
    unit.wait_toast(NO_SELECT_MSG)
    check_eq(unit.confirm_dialog().count(), 0, "未勾选时不应弹确认框")

    unit.drain_toasts()
    unit.click_toolbar("禁用")
    unit.wait_toast(NO_SELECT_MSG)
    check_eq(unit.statuses(), before, "未勾选时列表状态不应变化")


@case("TC-UNIT-029", "勾选单条记录执行启用/禁用/删除", "状态", "中")
def tc_unit_029(ctx):
    """单条：确认框标题/正文正确，操作生效且勾选自动清空。"""
    unit = ctx.open_unit()
    first = ctx.new_unit([("箱", 10)])
    second = ctx.new_unit([("箱", 10)])
    total = unit.total_count()

    unit.clear_selection()
    unit.select_row(first)
    title, content = unit.batch_action("禁用")
    check_contains(title, "确认操作", "禁用确认框标题")
    check_contains(content, "是否操作选中数据", "禁用确认框正文")
    check_eq(unit.read_row(first)["status"], "禁用", "被操作记录的状态")
    check_eq(unit.read_row(second)["status"], "启用", "未勾选记录的状态应不变")
    check_eq(unit.selected_count(), 0, "确认后勾选应自动清空")

    unit.select_row(first)
    title, content = unit.batch_action("删除")
    check_contains(title, "确认删除", "删除确认框标题")
    check_contains(content, "是否删除选中数据", "删除确认框正文")
    check(not unit.has_row(first), "单条删除后该行应消失")
    check_eq(unit.total_count(), total - 1, "删除后总数应减 1")


@case("TC-UNIT-039", "勾选 2 条及以上执行批量操作", "状态", "高")
def tc_unit_039(ctx):
    """两条同时禁用/启用/删除，每次操作后勾选自动清空。"""
    unit = ctx.open_unit()
    names = [ctx.new_unit([("箱", 10)]) for _ in range(3)]
    total = unit.total_count()

    unit.clear_selection()
    unit.select_rows(names[:2])
    check_eq(unit.selected_count(), 2, "批量勾选数")

    title, content = unit.batch_action("禁用")
    check_contains(title, "确认操作", "批量禁用确认框标题")
    check_eq(unit.read_row(names[0])["status"], "禁用", "第 1 条状态")
    check_eq(unit.read_row(names[1])["status"], "禁用", "第 2 条状态")
    check_eq(unit.read_row(names[2])["status"], "启用", "第 3 条状态应不变")
    check_eq(unit.selected_count(), 0, "批量禁用后勾选应清空")

    unit.select_rows(names[:2])
    unit.batch_action("启用")
    check_eq(unit.read_row(names[0])["status"], "启用", "批量启用后第 1 条状态")
    check_eq(unit.read_row(names[1])["status"], "启用", "批量启用后第 2 条状态")
    check_eq(unit.selected_count(), 0, "批量启用后勾选应清空")

    unit.select_rows(names[:2])
    title, content = unit.batch_action("删除")
    check_contains(title, "确认删除", "批量删除确认框标题")
    check_contains(content, "是否删除选中数据", "批量删除确认框正文")
    check(not unit.has_row(names[0]), "批量删除后第 1 条应消失")
    check(not unit.has_row(names[1]), "批量删除后第 2 条应消失")
    check_eq(unit.total_count(), total - 2, "批量删除后总数应减 2")
    check_eq(unit.selected_count(), 0, "批量删除后勾选应清空")
