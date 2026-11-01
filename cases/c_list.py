"""列表展示：TC-UNIT-004、005、034、035、036。"""

import math

from framework.asserts import check, check_contains, check_eq, check_in
from framework.registry import case, manual
from cases._helpers import cell_blank, expected_name, expected_other


@case("TC-UNIT-004", "无数据时显示空状态", "列表展示", "中")
def tc_unit_004(ctx):
    """用「查不到的关键字」造出空列表，验证空状态与工具栏可用。"""
    unit = ctx.open_unit()
    keyword = "查无此单位" + ctx.data.token     # 保证不存在

    unit.search(keyword)
    check_eq(unit.row_count(), 0, "无匹配时数据行数")
    check_contains(unit.empty_text(), "暂无数据", "空状态提示")

    for text in ("新增", "删除", "启用", "禁用"):
        check(unit.button(text).count() >= 1, f"空状态下「{text}」按钮应仍展示")

    messages = unit.toasts()
    check(not any("500" in m or "错误" in m for m in messages), f"空列表不应报错，实际提示：{messages}")


@case("TC-UNIT-005", "有数据时列表字段展示正确", "列表展示", "高")
def tc_unit_005(ctx):
    """造一条单副单位、一条双副单位，核对各列展示（副单位3 由 TC-UNIT-014 覆盖）。"""
    unit = ctx.open_unit()
    basic_a = ctx.new_unit([("箱", 10)])
    basic_b = ctx.new_unit([("盒", 6), ("箱", 60)])

    row_a = unit.read_row(basic_a)
    check(row_a["seq"].isdigit(), f"# 列应为序号，实际 {row_a['seq']!r}")
    check_eq(row_a["basic"], basic_a, "基本单位列")
    check_eq(row_a["other"], expected_other(basic_a, "箱", 10), "副单位列")
    check_eq(row_a["name"], expected_name(basic_a, "箱", 10), "单位名称列")
    check(cell_blank(row_a["other2"]), f"未填写的副单位2 应为空，实际 {row_a['other2']!r}")
    check(cell_blank(row_a["other3"]), f"未填写的副单位3 应为空，实际 {row_a['other3']!r}")
    check_in(row_a["status"], ("启用", "禁用"), "状态列")
    check_eq(row_a["status"], "启用", "新增后默认状态")

    row_b = unit.read_row(basic_b)
    check_eq(row_b["other"], expected_other(basic_b, "盒", 6), "副单位列（双副单位）")
    check_eq(row_b["other2"], expected_other(basic_b, "箱", 60), "副单位2 列")
    check(cell_blank(row_b["other3"]), f"未填写的副单位3 应为空，实际 {row_b['other3']!r}")
    check(row_b["name"].startswith(f"{basic_b}/("), f"单位名称应以「{basic_b}/(」开头：{row_b['name']!r}")


@case("TC-UNIT-034", "勾选框全选与取消全选", "列表展示", "中")
def tc_unit_034(ctx):
    """点表头勾选框全选当前页，再点一次取消。"""
    unit = ctx.open_unit()
    if unit.row_count() < 2:
        ctx.new_unit([("箱", 10)])
        ctx.new_unit([("箱", 10)])
        unit.reset()

    unit.clear_selection()
    total_rows = unit.row_count()
    check(total_rows >= 2, f"当前页至少需要 2 行，实际 {total_rows}")

    unit.select_all()
    check_eq(unit.selected_count(), total_rows, "全选后的勾选数")
    check_eq(unit.header_state(), "checked", "表头勾选框状态")

    unit.select_all(checked=False)
    check_eq(unit.selected_count(), 0, "再次点击后勾选数")
    check_eq(unit.header_state(), "none", "再次点击后表头勾选框状态")


@case("TC-UNIT-035", "数据超过一页时显示分页器", "列表展示", "中")
def tc_unit_035(ctx):
    """验证分页阈值、每页条数、翻页与范围文案。"""
    unit = ctx.open_unit()

    total = unit.total_count()
    if total <= 10:
        ctx.note(f"当前仅 {total} 条数据，先补造到 11 条再验分页")
        while total <= 10:
            ctx.new_unit([("箱", 10)])
            total = unit.total_count()
        unit.reset()

    info = unit.pagination_info()
    check(info["exists"], "数据超过 10 条时应出现分页器")
    check_eq(info["pageSize"], 10, "每页默认条数")
    check_eq(info["current"], 1, "初始页码")
    check_contains(info["range"], f"共{total}条", "分页总数文案")
    check_eq(info["pages"], math.ceil(total / 10), "总页数")
    check_eq(info["range"].split(" ")[0], f"1-{min(10, total)}", "首屏范围文案")

    # 第 2 页
    unit.goto_page(2)
    info = unit.pagination_info()
    check_eq(info["current"], 2, "切页后页码")
    check_eq(info["range"].split(" ")[0], "11-20", "第 2 页范围文案")

    # 每页条数切换（先回第 1 页，否则切完可能停在末页只剩几行）
    unit.goto_page(1)
    unit.set_page_size(20)
    info = unit.pagination_info()
    check_eq(info["pageSize"], 20, "切换后每页条数")
    check_eq(unit.row_count(), min(20, total), "每页 20 条时的数据行数")
    check_eq(info["pages"], math.ceil(total / 20), "每页 20 条时的总页数")

    # 收尾：恢复默认每页 10 条、第 1 页
    unit.set_page_size(10)
    unit.goto_page(1)
    check_eq(unit.pagination_info()["current"], 1, "恢复后页码")


manual(
    "TC-UNIT-036", "页面顶部出现无关统计卡片", "异常", "中",
    reason="说明型用例：顶部统计卡片为首页模块的设计行为（点击过即显示），"
           "已确认不作为缺陷，无需自动断言，回归时人工目视确认不遮挡操作即可",
)
