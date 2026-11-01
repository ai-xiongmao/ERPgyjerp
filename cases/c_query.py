"""查询：TC-UNIT-006 ~ 011。"""

from framework.asserts import check, check_contains, check_eq
from framework.registry import case


@case("TC-UNIT-006", "不输入条件直接点击查询", "查询", "中")
def tc_unit_006(ctx):
    """条件留空点查询，应返回全量数据且不报错。"""
    unit = ctx.open_unit()
    unit.reset_search_only()
    unit.click_button("查询")
    unit._wait_table_loaded()

    total = unit.total_count()
    check_eq(unit.row_count(), min(total, 10), "空条件查询应返回第 1 页全量数据")
    messages = unit.toasts()
    check(not any("500" in m or "失败" in m for m in messages), f"空条件查询不应报错：{messages}")


@case("TC-UNIT-007", "按已存在的单位名称精确查询", "查询", "高")
def tc_unit_007(ctx):
    """查询已存在的单位名称，只应命中包含该名称的记录。"""
    basic = ctx.new_unit([("箱", 10)])
    unit = ctx.unit
    unit.search(basic)

    rows = unit.rows_data()
    check(len(rows) >= 1, f"查询「{basic}」应至少命中 1 条，实际 {len(rows)}")
    for row in rows:
        check_contains(row["name"], basic, "命中记录的单位名称")

    hits = [row for row in rows if row["basic"] == basic]
    check_eq(len(hits), 1, f"命中「{basic}」的记录数")
    check_eq(rows[0]["other"], f"箱=10{basic}", "命中记录的副单位列")


@case("TC-UNIT-008", "按不存在的单位名称查询", "查询", "中")
def tc_unit_008(ctx):
    """查询不存在的名称，应显示暂无数据。"""
    unit = ctx.open_unit()
    keyword = "测试单位X" + ctx.data.token
    unit.search(keyword)

    check_eq(unit.row_count(), 0, "不存在的名称不应有数据行")
    check_contains(unit.empty_text(), "暂无数据", "空状态提示")
    messages = unit.toasts()
    check(not any("500" in m for m in messages), f"不应出现 500：{messages}")


@case("TC-UNIT-009", "关键字模糊查询", "查询", "中")
def tc_unit_009(ctx):
    """模糊匹配（已确认）：关键字命中的都列出，未命中的不出现。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])

    # 关键字出现在单位名称中间：10<基本单位>
    middle = f"10{basic}"
    unit.search(middle)
    rows = unit.rows_data()
    check_eq(len(rows), 1, f"模糊查询「{middle}」命中数")
    check_contains(rows[0]["name"], middle, "命中记录单位名称应含关键字")
    ctx.note(f"关键字出现在名称中间也能命中：{rows[0]['name']}")

    # 运行前缀命中本次造的多条数据，且不包含该关键字的记录不应出现
    unit.reset()          # 造数据前清掉查询条件，否则新记录被过滤、无法断言
    ctx.new_unit([("盒", 6)])
    unit.search(ctx.data.token)
    rows = unit.rows_data()
    check(len(rows) >= 2, f"「{ctx.data.token}」应命中多条，实际 {len(rows)}")
    for row in rows:
        check_contains(row["name"], ctx.data.token, "模糊查询结果应全部包含关键字")


@case("TC-UNIT-010", "查询后点击重置", "查询", "高")
def tc_unit_010(ctx):
    """重置后条件清空、恢复全量、回到第 1 页。"""
    unit = ctx.open_unit()
    ctx.new_unit([("箱", 10)])
    unit.search(ctx.data.token)
    check(unit.row_count() >= 1, "先按条件查询出结果")

    unit.reset()
    check_eq(unit.page.input_value(unit.SEARCH_INPUT), "", "重置后输入框")
    total = unit.total_count()
    check_eq(unit.row_count(), min(total, 10), "重置后应恢复全量列表")
    check_eq(unit.pagination_info()["current"], 1, "重置后页码")


@case("TC-UNIT-011", "查询条件输入特殊字符与超长文本", "查询", "中")
def tc_unit_011(ctx):
    """脚本标签不执行、超长文本不崩。"""
    unit = ctx.open_unit()
    page = unit.page
    dialogs = []

    def _on_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _on_dialog)
    try:
        unit.search("<script>alert(1)</script>")
        check_eq(dialogs, [], "不应弹出脚本对话框（XSS）")
        check_eq(unit.row_count(), 0, "特殊字符应无匹配")
        check_contains(unit.empty_text(), "暂无数据", "空状态提示")

        long_text = "测" * 100
        unit.fill(unit.SEARCH_INPUT, long_text)
        typed = unit.page.input_value(unit.SEARCH_INPUT)
        if len(typed) < len(long_text):
            ctx.note(f"输入框有长度限制：100 字符被截断为 {len(typed)} 字符")
        unit.click_button("查询")
        unit._wait_table_loaded()

        check_eq(dialogs, [], "超长文本不应弹出对话框")
        check_eq(unit.row_count(), 0, "超长关键字应无匹配")
        messages = unit.toasts()
        check(not any("500" in m for m in messages), f"不应出现 500：{messages}")
        check(unit.button("查询").count() >= 1, "页面应仍可操作")
    finally:
        page.remove_listener("dialog", _on_dialog)
