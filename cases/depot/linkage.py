"""仓库信息 - 跨模块联动（TC-DEP-* 共 2 条）。

行内「设为默认」、默认仓库唯一性。
"""

from framework.asserts import check_contains, check_eq
from framework.registry import case


@case("TC-DEP-034", "行内「设为默认」操作", "商品联动", "高")
def tc_dep_034(ctx):
    """点非默认仓库的「设为默认」→ Popover 确认 → 该仓库变「是」、原默认变「否」。"""
    depot = ctx.depot.open()
    # 造两条，显式把第一条设为默认，第二条即非默认
    first = ctx.new_depot()
    second = ctx.new_depot()
    depot.reset()
    depot.set_default(first)

    check_eq(depot.defaults().get(first), "是", "设为默认后第一条应为默认")
    check_eq(depot.defaults().get(second), "否", "第二条应为非默认")

    popover = depot.open_set_default_popconfirm(second)
    text = popover.inner_text()
    check_contains(text, "确定设为默认吗", "设为默认 Popover 文案")

    depot.click_popconfirm_ok(popover)
    check_eq(depot.defaults().get(second), "是", "设为默认后该仓库应为「是」")
    check_eq(depot.defaults().get(first), "否", "原默认仓库应自动变「否」")


@case("TC-DEP-036", "默认仓库唯一性", "商品联动", "中")
def tc_dep_036(ctx):
    """默认仓库唯一：切换默认时原默认自动取消，同一时间仅一个默认。"""
    depot = ctx.depot.open()
    first = ctx.new_depot()
    second = ctx.new_depot()
    third = ctx.new_depot()
    depot.reset()

    depot.set_default(first)
    check_eq(depot.default_name(), first, "设为默认后应为第一条")

    depot.set_default(second)
    check_eq(depot.default_name(), second, "再设为默认后应为第二条")

    depot.set_default(third)
    check_eq(depot.default_name(), third, "再设为默认后应为第三条")

    # 同一时间仅一个默认
    defaults = depot.defaults()
    is_default_count = sum(1 for d in defaults.values() if d == "是")
    check_eq(is_default_count, 1, "同一时间应仅一个默认仓库")
