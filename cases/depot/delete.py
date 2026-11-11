"""仓库信息 - 删除（TC-DEP-030 ~ 033）。

单条删除、取消删除、未勾选时点删除。
"""

from cases.depot._const import NO_SELECT_MSG
from framework.asserts import check, check_contains, check_eq
from framework.registry import case, manual


@case("TC-DEP-030", "删除单条仓库", "删除", "高")
def tc_dep_030(ctx):
    """勾选 → 删除 → 确认「确认删除/是否删除选中数据?」→ 删除成功无 toast。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    total = depot.total_count()

    depot.clear_selection()
    depot.select_row(name)
    depot.drain_toasts()
    depot.click_toolbar("删除")
    dialog = depot.confirm_dialog()
    dialog.wait_for(state="visible", timeout=8000)
    title, content = depot.confirm_texts()
    check_contains(title, "确认删除", "确认框标题")
    check_contains(content, "是否删除选中数据", "确认框正文")
    depot.click_confirm("确定")

    depot.wait_row(name, present=False)
    check_eq(depot.total_count(), total - 1, "删除后总数")
    check_eq(depot.toasts(), [], "删除成功后不应有 toast 提示")


@case("TC-DEP-031", "取消删除", "删除", "中")
def tc_dep_031(ctx):
    """删除确认框点取消：记录保留、总数不变。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    total = depot.total_count()

    depot.clear_selection()
    depot.select_row(name)
    depot.click_toolbar("删除")
    depot.cancel_confirm()

    check(depot.has_row(name), "取消后记录应保留")
    check_eq(depot.total_count(), total, "取消后总数不应变化")


@case("TC-DEP-032", "未勾选记录点击删除", "删除", "高")
def tc_dep_032(ctx):
    """未勾选点删除：提示「请选择一条记录！」，不弹确认框。"""
    depot = ctx.depot.open()
    ctx.new_depot()
    depot.reset()
    depot.clear_selection()
    depot.drain_toasts()

    depot.click_toolbar("删除")
    depot.wait_toast(NO_SELECT_MSG)
    check_eq(depot.confirm_dialog().count(), 0, "不应弹出删除确认框")


manual(
    "TC-DEP-033", "删除被业务引用的仓库", "删除", "中",
    reason="业务已确认「被引用仓库可删除、保留现状」，用例预期按此调整；"
           "但构造前置条件需采购/销售单据引用，真删会破坏业务数据，自动化不做此破坏性验证，"
           "请人工用已被引用的仓库执行",
)
