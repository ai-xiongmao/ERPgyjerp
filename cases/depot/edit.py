"""仓库信息 - 编辑与复制（TC-DEP-024 ~ 026）。

编辑已有仓库、编辑时清空名称、编辑时取消。
"""

from cases.depot._const import NO_NAME_MSG
from framework.asserts import check, check_eq
from framework.registry import case


@case("TC-DEP-024", "编辑已有仓库信息", "编辑", "高")
def tc_dep_024(ctx):
    """编辑弹窗回显原值，改后同步更新，未改字段保持不变。"""
    depot = ctx.depot.open()
    name = ctx.new_depot(address="原地址", remark="原备注")

    depot.open_edit_modal(name)
    check_eq(depot.modal_title(), "编辑", "弹窗标题")
    state = depot.form_state() or {}
    check_eq(state.get("name"), name, "回显的名称")
    check_eq(state.get("address"), "原地址", "回显的地址")
    check_eq(state.get("remark"), "原备注", "回显的备注")

    depot.fill_form(address="新地址")
    depot.save_success()

    row = depot.read_row(name)
    check_eq(row["address"], "新地址", "修改后的地址列")
    check_eq(row["remark"], "原备注", "未修改的备注列应保持不变")


@case("TC-DEP-025", "编辑时清空仓库名称", "编辑", "中")
def tc_dep_025(ctx):
    """清空名称保存 → 提示并拦截，原数据不被修改。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.open_edit_modal(name)
    depot.fill_form(name="")
    depot.save_blocked(NO_NAME_MSG)
    check(any(NO_NAME_MSG in e for e in depot.inline_errors()), "应提示名称必填")
    check(depot.modal_visible(), "保存应被拦截")

    depot.cancel()
    check(depot.has_row(name), "原仓库应仍存在")


@case("TC-DEP-026", "编辑时取消", "编辑", "中")
def tc_dep_026(ctx):
    """修改后取消：弹窗关闭、数据不变。"""
    depot = ctx.depot.open()
    name = ctx.new_depot(address="原地址")

    depot.open_edit_modal(name)
    depot.fill_form(address="要丢弃的地址")
    depot.cancel()
    check(not depot.modal_visible(), "取消后弹窗应关闭")
    check_eq(depot.read_row(name)["address"], "原地址", "取消后地址不应变化")
