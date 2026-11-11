"""仓库信息 - 列表展示（TC-DEP-* 共 4 条）。

空状态、字段展示、全选与取消全选、「是否默认」列展示。
"""

from framework.asserts import check, check_contains, check_eq
from framework.registry import case


@case("TC-DEP-004", "无数据时显示空状态", "列表展示", "中")
def tc_dep_004(ctx):
    """用「查不到的关键字」造出空列表，验证空状态与工具栏可用。"""
    depot = ctx.depot.open()
    keyword = "查无此仓库" + ctx.data.token

    depot.search(keyword)
    check_eq(depot.row_count(), 0, "无匹配时数据行数")
    check_contains(depot.empty_text(), "暂无数据", "空状态提示")

    for text in ("新增", "删除", "启用", "禁用"):
        check(depot.button(text).count() >= 1, f"空状态下「{text}」按钮应仍展示")

    messages = depot.toasts()
    check(not any("500" in m or "错误" in m for m in messages),
          f"空列表不应报错，实际提示：{messages}")


@case("TC-DEP-005", "有数据时列表字段展示正确", "列表展示", "高")
def tc_dep_005(ctx):
    """造一条完整仓库，核对各字段展示；未填字段为空。"""
    depot = ctx.depot.open()
    name = ctx.new_depot(address="深圳市南山区", warehousing="1.5",
                         truckage="20", sort="1", remark="测试备注")

    row = depot.read_row(name)
    check_eq(row["name"], name, "仓库名称列")
    check_eq(row["address"], "深圳市南山区", "仓库地址列")
    check_eq(row["warehousing"], "1.5", "仓储费列")
    check_eq(row["truckage"], "20", "搬运费列")
    check_eq(row["sort"], "1", "排序列")
    check_eq(row["remark"], "测试备注", "备注列")
    check_eq(row["status"], "启用", "状态列（新增默认启用）")
    # 是否默认：第一条成功保存的仓库自动成为默认（后续新增为「否」）
    check(row["isDefault"] in ("是", "否"), f"是否默认列取值异常：{row['isDefault']!r}")


@case("TC-DEP-006", "勾选框全选与取消全选", "列表展示", "中")
def tc_dep_006(ctx):
    """点表头勾选框全选当前页，再点一次取消。"""
    depot = ctx.depot.open()
    if depot.row_count() < 2:
        ctx.new_depot()
        ctx.new_depot()
        depot.reset()

    depot.clear_selection()
    total_rows = depot.row_count()
    check(total_rows >= 2, f"当前页至少需要 2 行，实际 {total_rows}")

    depot.select_all()
    check_eq(depot.selected_count(), total_rows, "全选后的勾选数")
    check_eq(depot.header_state(), "checked", "表头勾选框状态")

    depot.select_all(checked=False)
    check_eq(depot.selected_count(), 0, "再次点击后勾选数")
    check_eq(depot.header_state(), "none", "再次点击后表头勾选框状态")


@case("TC-DEP-035", "是否默认字段展示", "列表展示", "中")
def tc_dep_035(ctx):
    """默认仓库显示「是」，非默认显示「否」；列表为空时第一条自动成为默认。"""
    depot = ctx.depot.open()
    was_empty = depot.row_count() == 0

    first = ctx.new_depot()
    if was_empty:
        # 列表原本为空：第一条成功保存自动成为默认
        check_eq(depot.defaults().get(first), "是", "列表为空时第一条保存自动成为默认")

    second = ctx.new_depot()
    depot.reset()
    # 显式把 first 设为默认，验证 second 为「否」
    depot.set_default(first)
    defaults = depot.defaults()
    check_eq(defaults.get(first), "是", "默认仓库显示「是」")
    check_eq(defaults.get(second), "否", "非默认仓库显示「否」")
