"""商品信息 - 删除（TC-MAT-034 ~ 037）。

未勾选时点删除、单条删除、取消删除。
"""

from cases.material._const import NO_SELECT_MSG
from framework.asserts import check, check_contains, check_eq
from framework.registry import case, manual


@case("TC-MAT-034", "未勾选记录点击删除", "删除", "中")
def tc_mat_034(ctx):
    """未勾选点删除：提示「请选择一条记录！」，不弹确认框。"""
    product = ctx.product.open()
    ctx.new_material(unit="个")
    product.reset()
    product.clear_selection()
    product.drain_toasts()

    product.click_toolbar("删除")
    product.wait_toast(NO_SELECT_MSG)
    check_eq(product.confirm_dialog().count(), 0, "不应弹出删除确认框")


@case("TC-MAT-035", "删除单条商品", "删除", "高")
def tc_mat_035(ctx):
    """勾选 → 删除 → 确认「确认删除/是否删除选中数据?」→ 删除成功无 toast。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    total = product.total_count()

    product.clear_selection()
    product.select_row(name)
    product.drain_toasts()
    product.click_toolbar("删除")
    dialog = product.confirm_dialog()
    dialog.wait_for(state="visible", timeout=8000)
    title, content = product.confirm_texts()
    check_contains(title, "确认删除", "确认框标题")
    check_contains(content, "是否删除选中数据", "确认框正文")
    product.click_confirm("确定")

    product.wait_row(name, present=False)
    check_eq(product.total_count(), total - 1, "删除后总数")
    check_eq(product.toasts(), [], "删除成功后不应有 toast 提示")


@case("TC-MAT-036", "取消删除", "删除", "中")
def tc_mat_036(ctx):
    """删除确认框点取消：记录保留、总数不变。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    total = product.total_count()

    product.clear_selection()
    product.select_row(name)
    product.click_toolbar("删除")
    product.cancel_confirm()

    check(product.has_row(name), "取消后记录应保留")
    check_eq(product.total_count(), total, "取消后总数不应变化")


manual(
    "TC-MAT-037", "删除被业务引用的商品", "删除", "中",
    reason="需要一条「已被采购/销售等业务单据引用」的商品，构造前置条件会改动真实业务数据，"
           "自动化不做此破坏性验证；请人工用已引用的商品执行",
)
