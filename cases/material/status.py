"""商品信息 - 启用 / 禁用（TC-MAT-031 ~ 033）。

单条启用 / 禁用、未勾选时的提示。
"""

from cases.material._const import NO_SELECT_MSG
from framework.asserts import check_contains, check_eq
from framework.registry import case


@case("TC-MAT-031", "禁用一条启用状态的商品", "状态", "高")
def tc_mat_031(ctx):
    """勾选启用商品 → 禁用 → 确认 → 状态变禁用。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    check_eq(product.read_row(name)["status"], "启用", "新增后初始状态")

    title, content = product.set_status(name, "禁用")
    check_contains(title, "确认操作", "确认框标题")
    check_contains(content, "是否操作选中数据", "确认框正文")
    check_eq(product.read_row(name)["status"], "禁用", "禁用后的状态列")


@case("TC-MAT-032", "启用一条禁用状态的商品", "状态", "高")
def tc_mat_032(ctx):
    """先禁用，再启用回来。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    product.set_status(name, "禁用")
    check_eq(product.read_row(name)["status"], "禁用", "禁用后状态")

    title, content = product.set_status(name, "启用")
    check_contains(title, "确认操作", "启用确认框标题")
    check_eq(product.read_row(name)["status"], "启用", "启用后状态")


@case("TC-MAT-033", "未勾选记录点击启用/禁用", "状态", "中")
def tc_mat_033(ctx):
    """未勾选点启用/禁用：提示「请选择一条记录！」，不弹确认框。"""
    product = ctx.product.open()
    ctx.new_material(unit="个")
    product.reset()
    product.clear_selection()
    product.drain_toasts()

    product.click_toolbar("启用")
    product.wait_toast(NO_SELECT_MSG)
    check_eq(product.confirm_dialog().count(), 0, "未勾选时不应弹确认框")

    product.drain_toasts()
    product.click_toolbar("禁用")
    product.wait_toast(NO_SELECT_MSG)
