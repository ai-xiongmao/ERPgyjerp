"""商品信息 - 编辑与复制（TC-MAT-* 共 5 条）。

编辑已有商品、编辑时清空名称、编辑时取消、复制新增、复制后条码与库存规则。
"""

from cases.material._const import NO_NAME_MSG
from framework.asserts import check, check_eq
from framework.registry import case


@case("TC-MAT-027", "编辑已有商品信息", "编辑", "高")
def tc_mat_027(ctx):
    """编辑弹窗回显原值，改后同步更新。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    product.open_edit_modal(name)
    check_eq(product.modal_title(), "编辑", "弹窗标题")
    state = product.form_state()
    check_eq(state["name"], name, "回显的名称")
    check_eq(state["unit"], "个", "回显的单位")

    product.fill(product.field("standard"), "新规格123")
    product.save_success()
    check_eq(product.read_row(name)["spec"], "新规格123", "修改后的规格列")


@case("TC-MAT-028", "编辑时清空名称", "编辑", "中")
def tc_mat_028(ctx):
    """清空名称保存 → 提示并拦截，原数据不被修改。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    product.open_edit_modal(name)
    product.fill_name("")
    product.save_blocked(NO_NAME_MSG)
    check(any(NO_NAME_MSG in e for e in product.inline_errors()), "应提示名称必填")
    check(product.modal_visible(), "保存应被拦截")

    product.cancel()
    check(product.has_row(name), "原商品应仍存在")


@case("TC-MAT-029", "编辑时取消", "编辑", "中")
def tc_mat_029(ctx):
    """修改后取消：弹窗关闭、数据不变。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    product.open_edit_modal(name)
    product.fill(product.field("standard"), "要丢弃的规格")
    product.cancel()
    check(not product.modal_visible(), "取消后弹窗应关闭")
    check_eq(product.read_row(name)["spec"], "", "取消后规格不应变化")


@case("TC-MAT-030", "复制商品（复制新增）", "复制", "中")
def tc_mat_030(ctx):
    """复制弹窗标题「复制新增」，回显名称/单位，条码自动生成新值。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    src = product.read_row(name)

    product.open_copy_modal(name)
    check_eq(product.modal_title(), "复制新增", "弹窗标题")
    state = product.form_state()
    check_eq(state["name"], name, "复制的名称")
    check_eq(state["unit"], "个", "复制的单位")
    check(state["barCode"] and state["barCode"] != src["barcode"],
          f"复制后条码应自动生成新值，实际 {state['barCode']!r}（源 {src['barcode']!r}）")
    product.cancel()


@case("TC-MAT-041", "复制新增后条码自动生成、库存不复制", "复制", "中")
def tc_mat_041(ctx):
    """复制只复用名称+单位，条码自动生成新值，库存不复制。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    src = product.read_row(name)

    product.open_copy_modal(name)
    state = product.form_state()
    check_eq(state["name"], name, "复制复用的名称")
    check_eq(state["unit"], "个", "复制复用的单位")
    check(state["barCode"] != src["barcode"], "复制后条码应为新值")

    # 保存复制出的商品
    copy_name = ctx.data.material_name()
    ctx.data.track_material(copy_name)
    product.fill_name(copy_name)
    product.save_success()
    product.wait_row(copy_name, present=True)

    row = product.read_row(copy_name)
    check(row["barcode"] != src["barcode"], "新商品条码应不同于源")
    check_eq(row["stock"], "0", "复制商品库存应为空（不复制）")
