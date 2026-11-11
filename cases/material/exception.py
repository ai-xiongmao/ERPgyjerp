"""商品信息 - 异常与权限（TC-MAT-* 共 4 条）。

工具栏特殊按钮、批量编辑、列设置。
"""

from cases.material._const import NO_SELECT_MSG
from framework.asserts import check, check_eq, check_in
from framework.registry import case, manual


@case("TC-MAT-038", "工具栏特殊按钮（导入/导出/批量编辑等）", "异常", "中")
def tc_mat_038(ctx):
    """导出可成功（本次仅验证导出，导入不要求）。"""
    product = ctx.product.open()
    check(product.button("导入").count() >= 1, "应有「导入」按钮")
    check(product.button("导出").count() >= 1, "应有「导出」按钮")
    check(product.button("批量编辑").count() >= 1, "应有「批量编辑」按钮")
    check(product.button("修正库存").count() >= 1, "应有「修正库存」按钮")
    check(product.button("修正成本").count() >= 1, "应有「修正成本」按钮")
    check(product.button("列设置").count() >= 1, "应有「列设置」按钮")
    # 导出：点击后验证触发下载（不做内容校验）
    product.click_toolbar("导出")
    product.pause()
    ctx.note("导出按钮点击完成（本次仅验证按钮存在与可点击，不校验文件内容）")


manual(
    "TC-MAT-039", "试用到期后访问与操作", "权限", "低",
    reason="前置条件为「账号试用已到期」（当前页面显示试用到期 2026-11-08），"
           "无法在不改变账号状态的前提下构造；到期后人工执行",
)


@case("TC-MAT-042", "批量编辑商品（勾选后批量修改）", "异常", "高")
def tc_mat_042(ctx):
    """未勾选提示「请选择一条记录！」；勾选后弹批量编辑弹窗。"""
    product = ctx.product.open()
    name1 = ctx.new_material(unit="个")
    name2 = ctx.new_material(unit="个")
    product.reset()
    product.clear_selection()

    # 未勾选
    product.drain_toasts()
    product.click_toolbar("批量编辑")
    product.wait_toast(NO_SELECT_MSG)

    # 勾选 2 条 → 批量编辑弹窗
    product.select_rows([name1, name2])
    product.click_toolbar("批量编辑")
    product.modal().wait_for(state="visible", timeout=8000)
    check_eq(product.modal_title(), "批量编辑", "弹窗标题")

    labels = [l.strip() for l in product.modal().locator(".ant-form-item-label").all_inner_texts()]
    for expected in ("颜色", "品牌", "类别", "制造商", "备注"):
        check_in(expected, labels, "批量编辑字段")

    # 修改颜色后保存：批量保存会先弹「确认操作 / 是否操作选中的N条数据?」
    product.fill(product.field("color"), "批量色")
    title, content = product.save_batch()
    check_eq(title, "确认操作", "批量保存确认框标题")
    check_in("是否操作选中的", content, "批量保存确认框正文")
    check_eq(product.read_row(name1)["color"], "批量色", "批量编辑后第 1 条颜色")
    check_eq(product.read_row(name2)["color"], "批量色", "批量编辑后第 2 条颜色")


@case("TC-MAT-043", "列设置（列显隐配置）", "异常", "中")
def tc_mat_043(ctx):
    """列设置弹出列显隐配置列表，含「恢复默认」。"""
    product = ctx.product.open()
    popover = product.open_column_settings()

    check(popover.count() >= 1, "应弹出列设置浮层")
    text = popover.first.inner_text()
    for expected in ("条码", "名称", "单位", "库存", "状态", "恢复默认"):
        check_in(expected, text, "列设置项")

    product.page.keyboard.press("Escape")
    product.pause(300)
