"""删除：TC-UNIT-030 ~ 033、044。"""

from framework.asserts import check, check_contains, check_eq
from framework.registry import case, manual
from pages.base_page import POPOVER


@case("TC-UNIT-030", "删除单条记录", "删除", "高")
def tc_unit_030(ctx):
    """行内删除走 Popconfirm「确定删除吗?」；工具栏删除走「确认删除」弹窗。"""
    unit = ctx.open_unit()

    # 路径一：行内「删除」→ Popconfirm
    inline_target = ctx.new_unit([("箱", 10)])
    total = unit.total_count()
    unit.drain_toasts()
    popover = unit.open_delete_popconfirm(inline_target)
    text = popover.inner_text()
    check_contains(text, "确定删除吗", "Popconfirm 文案")
    buttons = [b.strip() for b in popover.locator("button").all_inner_texts()]
    check_eq(len(buttons), 2, f"Popconfirm 应只有取消/确定两个按钮：{buttons}")

    unit.click_popconfirm_ok(popover)
    unit.wait_row(inline_target, present=False)
    check_eq(unit.total_count(), total - 1, "行内删除后总数")
    check_eq(unit.toasts(), [], "删除成功后不应有 toast 提示（实测无提示）")

    # 路径二：勾选 + 工具栏「删除」→ 确认弹窗
    toolbar_target = ctx.new_unit([("箱", 10)])
    total = unit.total_count()
    unit.clear_selection()
    unit.select_row(toolbar_target)
    title, content = unit.batch_action("删除")
    check_contains(title, "确认删除", "工具栏删除确认框标题")
    check_contains(content, "是否删除选中数据", "工具栏删除确认框正文")
    check(not unit.has_row(toolbar_target), "工具栏删除后该行应消失")
    check_eq(unit.total_count(), total - 1, "工具栏删除后总数")


@case("TC-UNIT-031", "取消删除", "删除", "中")
def tc_unit_031(ctx):
    """Popconfirm 点取消：浮层关闭、记录保留、总数不变。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])
    total = unit.total_count()

    popover = unit.open_delete_popconfirm(basic)
    unit.click_popconfirm_cancel(popover)

    check_eq(unit.page.locator(POPOVER).count(), 0, "取消后确认浮层应关闭")
    check(unit.has_row(basic), "取消后记录应保留")
    check_eq(unit.total_count(), total, "取消后总数不应变化")


@case("TC-UNIT-032", "未勾选记录点击删除", "删除", "高")
def tc_unit_032(ctx):
    """未勾选点工具栏删除：提示「请选择一条记录！」，不弹确认框。"""
    unit = ctx.open_unit()
    ctx.new_unit([("箱", 10)])
    unit.reset()
    unit.clear_selection()
    unit.drain_toasts()

    unit.click_toolbar("删除")
    unit.wait_toast("请选择一条记录！")

    check_eq(unit.page.locator(POPOVER).count(), 0, "不应弹出删除确认浮层")
    check_eq(unit.confirm_dialog().count(), 0, "不应弹出确认弹窗")


manual(
    "TC-UNIT-033", "删除被商品使用的单位", "删除", "中",
    reason="需要一条「已被商品引用」的单位。删除确认一旦被服务端放行就会真实删除业务数据，"
           "自动化不做此破坏性验证；请人工用「批量单位11」（已被 2 条商品引用）执行",
)
