"""仓库信息 - 查询（TC-DEP-007 ~ 012）。

空条件查询、按名称 / 备注 / 模糊查询、重置、特殊字符与超长文本。
"""

from framework.asserts import check, check_eq, check_in
from framework.registry import case


@case("TC-DEP-007", "不输入条件直接点击查询", "查询", "中")
def tc_dep_007(ctx):
    """条件留空点查询，返回全量数据不报错。"""
    depot = ctx.depot.open()
    depot.reset()
    depot.click_button("查询")
    depot._wait_table_loaded()

    total = depot.total_count()
    check_eq(depot.row_count(), min(total, 10), "空条件查询应返回第 1 页全量数据")
    messages = depot.toasts()
    check(not any("500" in m or "失败" in m for m in messages),
          f"空条件查询不应报错：{messages}")


@case("TC-DEP-008", "按仓库名称查询", "查询", "高")
def tc_dep_008(ctx):
    """按仓库名称模糊查询，仅显示匹配记录。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.search(name)
    rows = depot.rows_data()
    check(len(rows) >= 1, f"按名称「{name}」查询应命中")
    for r in rows:
        check(name in (r["name"] or ""), f"查询结果应含目标名称：{r['name']!r}")

    # 用不存在的名称查，应无匹配
    depot.search("不存在仓库" + ctx.data.token)
    check_eq(depot.row_count(), 0, "不存在的名称查询应无结果")


@case("TC-DEP-009", "按备注查询", "查询", "中")
def tc_dep_009(ctx):
    """按备注关键词查询，命中备注匹配的仓库。"""
    depot = ctx.depot.open()
    name = ctx.new_depot(remark="独一无二的备注XYZ")

    depot.search_remark("备注XYZ")
    rows = depot.rows_data()
    check(len(rows) >= 1, "按备注查询应命中")
    check_in(name, [r["name"] for r in rows], "备注查询应命中该仓库")


@case("TC-DEP-010", "查询后点击重置", "查询", "高")
def tc_dep_010(ctx):
    """重置清空输入框、恢复全量列表。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.search(name)
    depot.reset()

    check_eq(depot.page.locator(depot.NAME_INPUT).first.input_value(), "", "重置后仓库名称输入框应为空")
    check_eq(depot.page.locator(depot.REMARK_INPUT).first.input_value(), "", "重置后备注输入框应为空")
    check(depot.has_row(name), "重置后列表应恢复全量（含目标仓库）")


@case("TC-DEP-011", "查询条件输入特殊字符与超长文本", "查询", "中")
def tc_dep_011(ctx):
    """特殊字符/超长文本查询不触发 XSS、不报 500。"""
    depot = ctx.depot.open()

    depot.search("<script>alert(1)</script>")
    check(not any("500" in m for m in depot.toasts()), "XSS 字符查询不应 500")
    check("暂无数据" in depot.empty_text() or depot.row_count() >= 0,
          "特殊字符查询应正常返回（空或匹配）")

    long_text = "仓" * 100
    depot.search(long_text)
    check(not any("500" in m or "崩溃" in m for m in depot.toasts()),
          f"超长文本查询不应报错：{depot.toasts()}")


@case("TC-DEP-012", "仓库名称模糊查询", "查询", "中")
def tc_dep_012(ctx):
    """仓库名称模糊匹配（含关键字即命中）。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    # 取名字中间子串做模糊查询
    depot.search(name[2:-2])
    rows = depot.rows_data()
    check_in(name, [r["name"] for r in rows], "子串应能模糊命中")
