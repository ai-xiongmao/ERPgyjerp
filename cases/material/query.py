"""商品信息 - 查询（TC-MAT-007 ~ 013）。

空条件查询、关键词（条码/名称/助记码）、规格、类别下拉、
高级查询字段、重置、特殊字符与超长文本。
"""

from framework.asserts import blocked, check, check_eq, check_in
from framework.registry import case


@case("TC-MAT-007", "不输入条件直接点击查询", "查询", "中")
def tc_mat_007(ctx):
    """条件留空点查询，返回全量数据不报错。"""
    product = ctx.product.open()
    product.reset()
    product.click_button("查询")
    product._wait_table_loaded()

    total = product.total_count()
    check_eq(product.row_count(), min(total, 10), "空条件查询应返回第 1 页全量数据")
    messages = product.toasts()
    check(not any("500" in m or "失败" in m for m in messages),
          f"空条件查询不应报错：{messages}")


@case("TC-MAT-008", "按关键词查询（条码/名称/助记码）", "查询", "高")
def tc_mat_008(ctx):
    """关键词模糊匹配条码/名称/助记码任一字段。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    row = product.read_row(name)
    barcode = row["barcode"]

    # 按名称查
    product.search(name)
    check_eq(product.count_row(name), 1, f"按名称「{name}」查询命中数")

    # 按条码查
    product.search(barcode)
    rows = product.rows_data()
    check(len(rows) >= 1, f"按条码「{barcode}」查询应命中")
    check_in(name, [r["name"] for r in rows], "按条码查询应命中该商品")

    # 模糊匹配：名称中间子串
    product.search(name[2:-2])
    rows = product.rows_data()
    check_in(name, [r["name"] for r in rows], "关键词子串应能模糊命中")


@case("TC-MAT-009", "按规格查询", "查询", "中")
def tc_mat_009(ctx):
    """规格命中匹配商品，其他不显示。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")
    # 编辑补规格
    product.open_edit_modal(name)
    product.fill(product.field("standard"), "测试规格XYZ")
    product.save_success()

    product.search_spec("测试规格XYZ")
    rows = product.rows_data()
    check(len(rows) >= 1, "按规格查询应命中")
    for r in rows:
        check("测试规格XYZ" in (r["spec"] or ""), f"规格查询结果应含目标规格：{r['spec']!r}")


@case("TC-MAT-010", "按类别下拉查询", "查询", "中")
def tc_mat_010(ctx):
    """类别下拉选择后查询命中该类别的商品。"""
    product = ctx.product.open()
    # 类别下拉在当前数据下可能无选项；至少验证下拉可点开且不报错
    check(product.category_select().count() >= 1, "应有「请选择类别」下拉")
    options = product.category_options()
    ctx.note(f"类别下拉选项：{options[:10]}")
    # 类别表当前为空（0 条），「按类别查询命中」这一层验证不了。
    # 记「阻塞（前置不具备）」而不是「失败」——产品本身没毛病，是环境缺数据。
    if not options:
        blocked("商品类别为空（商品管理→商品类别 0 条），无法验证「按类别查询命中」；"
                "需先在商品类别里建数据再跑本条")

    picked = product.pick_category()
    ctx.note(f"按类别「{picked}」查询完成，当前页 {product.row_count()} 行")
    check(product.has_table(), "按类别查询后表格应正常渲染")


@case("TC-MAT-011", "展开后高级查询字段", "查询", "中")
def tc_mat_011(ctx):
    """展开后多出型号/颜色/品牌/制造商/扩展等字段，收起恢复。"""
    product = ctx.product.open()
    product.expand_query()

    inputs = product.page.evaluate("""() => {
        const card = document.querySelector('.ant-card:has(.ant-table)');
        return Array.from(card.querySelectorAll('input')).map(i => i.placeholder || '').filter(Boolean);
    }""")
    for expected in ("请输入型号查询", "请输入颜色查询", "请输入品牌查询",
                     "请输入制造商查询", "请输入扩展1查询", "请输入仓位货架查询",
                     "请输入基础重量查询", "请输入保质期查询", "请输入备注查询"):
        check_in(expected, inputs, f"展开后应有「{expected}」字段")

    # 收起
    product.collapse_query()
    ctx.note("展开/收起交互正常")


@case("TC-MAT-012", "查询后点击重置", "查询", "中")
def tc_mat_012(ctx):
    """重置后关键词/规格清空，列表恢复全量。"""
    product = ctx.product.open()
    ctx.new_material(unit="个")
    product.search(ctx.data.token)
    check(product.row_count() >= 1, "先按条件查询出结果")

    product.reset()
    check_eq(product.page.input_value(product.KEYWORD_INPUT), "", "重置后关键词输入框")
    check_eq(product.page.input_value(product.SPEC_INPUT), "", "重置后规格输入框")
    total = product.total_count()
    check_eq(product.row_count(), min(total, 10), "重置后应恢复全量列表")


@case("TC-MAT-013", "查询条件输入特殊字符与超长文本", "查询", "低")
def tc_mat_013(ctx):
    """脚本标签不执行、超长文本不崩。"""
    product = ctx.product.open()
    page = product.page
    dialogs = []

    def _on_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _on_dialog)
    try:
        product.search("<script>alert(1)</script>")
        check_eq(dialogs, [], "不应弹出脚本对话框（XSS）")
        check_eq(product.row_count(), 0, "特殊字符应无匹配")

        long_text = "测" * 100
        product.fill(product.KEYWORD_INPUT, long_text)
        product.click_button("查询")
        product._wait_table_loaded()
        check_eq(dialogs, [], "超长文本不应弹出对话框")
        messages = product.toasts()
        check(not any("500" in m for m in messages), f"不应出现 500：{messages}")
        check(product.button("查询").count() >= 1, "页面应仍可操作")
    finally:
        page.remove_listener("dialog", _on_dialog)
