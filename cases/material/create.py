"""商品信息 - 新增（TC-MAT-* 共 14 条）。

弹窗结构与必填标识、空表单 / 单字段缺失校验、单单位与多单位、
条码表与库存 / 图片 Tab、连续新增、取消新增、手动改条码。
"""

import time

from cases.material._const import NO_NAME_MSG
from framework.asserts import check, check_contains, check_eq, check_in
from framework.registry import case

NO_UNIT_MSG = "请输入单位!"


@case("TC-MAT-014", "新增弹窗结构与必填标识", "新增", "高")
def tc_mat_014(ctx):
    """三个 Tab；名称、单位带 * 号。"""
    product = ctx.product.open()
    product.open_create_modal()

    check_eq(product.modal_title(), "新增", "弹窗标题")
    tabs = [t.strip() for t in product.modal().locator(".ant-tabs-tab").all_inner_texts()]
    check_eq(tabs, ["基本信息", "库存数量", "图片信息"], "三个 Tab")

    required = product.modal().locator(
        ".ant-form-item-label:has(.ant-form-item-required)").all_inner_texts()
    check_in("名称", [t.strip() for t in required], "名称应带 * 号")
    check_in("单位", [t.strip() for t in required], "单位应带 * 号")

    buttons = [b.replace(" ", "") for b in product.modal().locator("button").all_inner_texts()]
    check(any("取消" in b for b in buttons), f"应有「取消」按钮，实际：{buttons}")
    check(any("保存" in b for b in buttons), f"应有「保存」按钮，实际：{buttons}")

    product.cancel()


@case("TC-MAT-015", "空表单保存必填校验", "新增", "高")
def tc_mat_015(ctx):
    """空表单保存：名称/单位下方红字，弹窗不关，不产生数据。"""
    product = ctx.product.open()
    total_before = product.total_count()

    product.open_create_modal()
    product.save_blocked(NO_NAME_MSG)
    errors = product.inline_errors()
    check(any(NO_NAME_MSG in e for e in errors), f"名称下方应提示「{NO_NAME_MSG}」，实际：{errors}")
    check(any(NO_UNIT_MSG in e for e in errors), f"单位下方应提示「{NO_UNIT_MSG}」，实际：{errors}")
    check(product.modal_visible(), "校验失败时弹窗应保持打开")

    product.cancel()
    check_eq(product.total_count(), total_before, "不应产生任何数据")


@case("TC-MAT-016", "只填名称不填单位保存", "新增", "高")
def tc_mat_016(ctx):
    """只填名称：单位下方提示「请输入单位!」。"""
    product = ctx.product.open()
    total_before = product.total_count()

    product.open_create_modal()
    product.fill_name("测试商品")
    product.save_blocked(NO_UNIT_MSG)
    errors = product.inline_errors()
    check(any(NO_UNIT_MSG in e for e in errors), f"单位下方应提示「{NO_UNIT_MSG}」，实际：{errors}")
    check(product.modal_visible(), "保存应被拦截")

    product.cancel()
    check_eq(product.total_count(), total_before, "不应产生数据")


@case("TC-MAT-017", "只填单位不填名称保存", "新增", "高")
def tc_mat_017(ctx):
    """只填单位：名称下方提示「请输入名称!」。"""
    product = ctx.product.open()
    total_before = product.total_count()

    product.open_create_modal()
    product.fill_unit("个")
    product.save_blocked(NO_NAME_MSG)
    errors = product.inline_errors()
    check(any(NO_NAME_MSG in e for e in errors), f"名称下方应提示「{NO_NAME_MSG}」，实际：{errors}")
    check(product.modal_visible(), "保存应被拦截")

    product.cancel()
    check_eq(product.total_count(), total_before, "不应产生数据")


@case("TC-MAT-018", "填写必填项后保存（单单位）", "新增", "高")
def tc_mat_018(ctx):
    """名称+单位保存：弹窗关闭、列表新增、状态启用、条码自动生成。"""
    product = ctx.product.open()
    name = ctx.new_material(unit="个")

    row = product.read_row(name)
    check_eq(row["name"], name, "列表新增的名称")
    check_eq(row["unit"], "个", "列表新增的单位")
    check_eq(row["status"], "启用", "状态默认启用")
    check(row["barcode"].isdigit() and row["barcode"], "条码应由系统自动生成")


@case("TC-MAT-019", "填写完整字段保存", "新增", "中")
def tc_mat_019(ctx):
    """填写规格/型号/颜色/品牌/助记码等完整字段保存，列表一致。"""
    product = ctx.product.open()
    name = ctx.data.material_name()
    ctx.data.track_material(name)

    product.open_create_modal()
    product.fill_basic(name, "个")
    product.fill(product.field("standard"), "规格A")
    product.fill(product.field("model"), "型号B")
    product.fill(product.field("color"), "红色")
    product.fill(product.field("brand"), "品牌C")
    # 助记码由系统按名称自动生成拼音（readonly），不手动填
    product.save_success()
    product.wait_row(name, present=True)

    row = product.read_row(name)
    check_eq(row["spec"], "规格A", "规格列")
    check_eq(row["model"], "型号B", "型号列")
    check_eq(row["color"], "红色", "颜色列")


@case("TC-MAT-020", "单位字段勾选「多单位」切换为下拉", "新增", "高")
def tc_mat_020(ctx):
    """勾选多单位 → 单位输入框变「选择多单位」下拉；取消勾选恢复。"""
    product = ctx.product.open()
    product.open_create_modal()

    check(product.field("unit").count() == 1, "初始应有自由输入的单位框")
    product.enable_multi_unit()
    check(product.field("unit").count() == 0, "勾选多单位后 #unit 输入框应消失")
    check_eq(product.multi_unit_select().count(), 1, "应出现「选择多单位」下拉")

    product.disable_multi_unit()
    check(product.field("unit").count() == 1, "取消勾选后应恢复自由输入")
    product.cancel()


@case("TC-MAT-021", "多单位下拉与多单位页数据联动", "新增", "高")
def tc_mat_021(ctx):
    """勾选多单位，下拉列出单位页面录入的记录，格式「基本单位/(副单位=比例基本单位)」。"""
    basic = ctx.new_unit([("箱", 10)])
    expected = f"{basic}/(箱=10{basic})"

    product = ctx.product.open()
    product.open_create_modal()
    product.enable_multi_unit()

    options = product.multi_unit_options()
    check(options, "多单位下拉不应为空")
    check_contains("\n".join(options), expected,
                   f"下拉未包含单位页面新录入的「{expected}」，前几项：{options[:5]}")
    product.cancel()


@case("TC-MAT-022", "条码表格结构（多单位商品）", "新增", "中")
def tc_mat_022(ctx):
    """勾选多单位后，条码表格表头为条码/单位/采购价/零售价/销售价/最低售价。"""
    product = ctx.product.open()
    product.open_create_modal()

    # 条码表格在基本信息 Tab 底部，是自定义 div 表格（.input-table .thead .td）
    headers = product.modal().evaluate("""(m) => {
        const thead = m.querySelector('.input-table .thead');
        if (!thead) return [];
        return Array.from(thead.querySelectorAll('.td, [class*=td]'))
            .map(t => (t.innerText || '').trim()).filter(Boolean);
    }""")
    ctx.note(f"条码表格表头：{headers}")
    for expected in ("条码", "单位", "采购价", "零售价", "销售价", "最低售价"):
        check_in(expected, headers, "条码表格表头")

    check(product.insert_row_button().count() >= 1, "应有「插入行」按钮")
    product.cancel()


@case("TC-MAT-023", "库存数量 Tab 结构", "新增", "中")
def tc_mat_023(ctx):
    """库存数量 Tab：仓库/期初库存数量/最低安全库存数量/最高安全库存数量，初始暂无数据。"""
    product = ctx.product.open()
    product.open_create_modal()
    product.switch_tab("库存数量")

    pane_text = product.active_tab_text()
    for expected in ("仓库", "期初库存数量", "最低安全库存数量", "最高安全库存数量"):
        check_in(expected, pane_text, "库存数量 Tab 表头")
    check_in("暂无数据", pane_text, "初始应为暂无数据")

    check(product.insert_row_button().count() >= 1, "应有「插入行」按钮")
    product.cancel()


@case("TC-MAT-024", "图片信息 Tab 上传限制", "新增", "中")
def tc_mat_024(ctx):
    """图片信息 Tab：提示「图片最多4张，且单张大小不超过1M」。"""
    product = ctx.product.open()
    product.open_create_modal()
    product.switch_tab("图片信息")

    pane_text = product.active_tab_text()
    check_in("图片最多4张", pane_text, "应有图片数量限制提示")
    check_in("不超过1M", pane_text, "应有单张大小限制提示")
    product.cancel()


@case("TC-MAT-025", "取消新增", "新增", "中")
def tc_mat_025(ctx):
    """填写后取消：弹窗关闭、无数据、重开为空表单。"""
    product = ctx.product.open()
    name = ctx.data.material_name()

    product.open_create_modal()
    product.fill_basic(name, "个")
    product.cancel()
    check(not product.modal_visible(), "取消后弹窗应关闭")

    product.search(name)
    check_eq(product.row_count(), 0, "取消后不应新增数据")
    product.reset()

    product.open_create_modal()
    state = product.form_state()
    check_eq(state["name"], "", "重新打开时名称应为空")
    product.cancel()


@case("TC-MAT-026", "连续新增两条数据", "新增", "中")
def tc_mat_026(ctx):
    """第一条保存后，第二次打开空白表单，能正常保存第二条。"""
    product = ctx.product.open()
    first = ctx.new_material(unit="个")

    product.open_create_modal()
    state = product.form_state()
    check_eq(state["name"], "", "第二次打开时名称应无残留")

    second = ctx.data.material_name()
    ctx.data.track_material(second)
    product.fill_basic(second, "个")
    product.save_success()
    product.wait_row(second, present=True)

    check(product.has_row(first), f"第一条「{first}」应仍在列表")
    check(product.has_row(second), f"第二条「{second}」应出现在列表")


@case("TC-MAT-040", "手动编辑条码保存（条码可手动改）", "新增", "高")
def tc_mat_040(ctx):
    """条码自动生成后可手动改，保存后以手动值为准。"""
    product = ctx.product.open()
    name = ctx.data.material_name()
    ctx.data.track_material(name)

    product.open_create_modal()
    product.fill_basic(name, "个")
    auto_barcode = product.form_state()["barCode"]
    check(auto_barcode, "条码应自动生成")

    # 手动改条码
    manual_barcode = "990" + str(int(time.time()))[-6:]
    product.modal().evaluate(
        """(m, val) => {
        const b = m.querySelector('[id^=barCode_]');
        if (!b) return;
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(b, val);
        b.dispatchEvent(new Event('input', {bubbles:true}));
    }""",
        manual_barcode,
    )
    product.save_success()
    product.wait_row(name, present=True)

    check_eq(product.read_row(name)["barcode"], manual_barcode, "保存后条码应为手动值")
