"""编辑：TC-UNIT-024、025。"""

from framework.asserts import check, check_eq
from framework.registry import case

NO_BASIC_MSG = "请输入基本单位!"


@case("TC-UNIT-024", "修改已有单位信息", "编辑", "高")
def tc_unit_024(ctx):
    """行内只有编辑/删除；编辑弹窗回显原值，改后同步更新，取消不保存。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])

    links = [text.strip() for text in unit.row_locator(basic).locator("a").all_inner_texts()]
    check_eq(links, ["编辑", "删除"], "操作列按钮构成")

    unit.open_edit_modal(basic)
    check_eq(unit.modal_title(), "编辑", "弹窗标题")

    state = unit.form_state()
    check_eq(state["basic"], basic, "回显的基本单位")
    check_eq(state["other"], "箱", "回显的副单位")
    check_eq(state["ratio"], "10", "回显的比例")

    unit.fill_form(basic, [("箱", 12)])
    unit.save_success()
    check_eq(unit.read_row(basic)["other"], f"箱=12{basic}", "修改后的副单位列")
    check_eq(unit.read_row(basic)["name"], f"{basic}/(箱=12{basic})", "修改后的单位名称")

    # 取消不保存
    unit.open_edit_modal(basic)
    unit.fill_form(basic, [("箱", 99)])
    unit.cancel_modal()
    check_eq(unit.read_row(basic)["other"], f"箱=12{basic}", "取消后副单位不应变化")


@case("TC-UNIT-025", "编辑时清空基本单位", "编辑", "中")
def tc_unit_025(ctx):
    """清空基本单位保存 → 提示并拦截，原数据不被修改。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])

    unit.open_edit_modal(basic)
    unit.fill_form("", [("箱", 10)])
    result = unit.save_blocked(NO_BASIC_MSG)
    check(result["inline"] or result["toast"], "应提示基本单位必填")
    check(unit.modal_visible(), "保存应被拦截，弹窗保持打开")

    unit.cancel_modal()
    row = unit.read_row(basic)
    check_eq(row["basic"], basic, "原记录的基本单位")
    check_eq(row["other"], f"箱=10{basic}", "原记录的副单位")
