"""商品信息 - 列表展示（TC-MAT-004 ~ 006）。

空状态、字段展示、全选与取消全选。
"""

from framework.asserts import check, check_contains, check_eq
from framework.registry import case


@case("TC-MAT-004", "无数据时显示空状态", "列表展示", "中")
def tc_mat_004(ctx):
    """用「查不到的关键字」造出空列表，验证空状态与工具栏可用。"""
    product = ctx.product.open()
    keyword = "查无此商品" + ctx.data.token

    product.search(keyword)
    check_eq(product.row_count(), 0, "无匹配时数据行数")
    check_contains(product.empty_text(), "暂无数据", "空状态提示")

    for text in ("新增", "删除", "启用", "禁用", "导入", "导出"):
        check(product.button(text).count() >= 1, f"空状态下「{text}」按钮应仍展示")

    messages = product.toasts()
    check(not any("500" in m or "错误" in m for m in messages),
          f"空列表不应报错，实际提示：{messages}")


@case("TC-MAT-005", "有数据时列表字段展示正确", "列表展示", "高")
def tc_mat_005(ctx):
    """造一条商品，核对条码/名称/单位/状态列；未填字段为空。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    row = product.read_row(name)
    check(row["barcode"].isdigit(), f"条码应由系统生成且为数字，实际 {row['barcode']!r}")
    check_eq(row["name"], name, "名称列")
    check_eq(row["unit"], "个", "单位列")
    check_eq(row["status"], "启用", "状态列（新增默认启用）")
    for field in ("spec", "model", "color", "category", "purchase", "retail", "sale", "lowest"):
        check(row[field] in ("", None), f"未填写的「{field}」应为空，实际 {row[field]!r}")


@case("TC-MAT-006", "勾选框全选与取消全选", "列表展示", "中")
def tc_mat_006(ctx):
    """点表头勾选框全选当前页，再点一次取消。"""
    product = ctx.product.open()
    if product.row_count() < 2:
        ctx.new_material(unit="个")
        ctx.new_material(unit="个")
        product.reset()

    product.clear_selection()
    total_rows = product.row_count()
    check(total_rows >= 2, f"当前页至少需要 2 行，实际 {total_rows}")

    product.select_all()
    check_eq(product.selected_count(), total_rows, "全选后的勾选数")
    check_eq(product.header_state(), "checked", "表头勾选框状态")

    product.select_all(checked=False)
    check_eq(product.selected_count(), 0, "再次点击后勾选数")
    check_eq(product.header_state(), "none", "再次点击后表头勾选框状态")
