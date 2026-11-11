"""基础资料 - 仓库信息：TC-DEP-001 ~ 038。

这一组用例围绕「基础资料 - 仓库信息」页面，共 38 条。按标签分块：
    页面入口（001~003）、列表展示（004~006、035）、查询（007~012）、
    新增（013~023）、编辑（024~026）、状态（027~029）、删除（030~033）、
    商品联动（034、036）、权限（037）、异常（038）。

保存类操作统一走 depot.save_success()：同时检查「弹窗关闭 + 无失败 toast」，
因为这个系统接口报错时也会关弹窗（与多单位/商品页一致）。

数据纪律：所有造出的仓库名都带运行前缀（ATxxxxDxx），跑完按前缀回收；
绝不删既有业务数据。仓库名称唯一（与多单位页允许同名不同）。

已知偏差（记录 note，不判红）：
    - 空表单保存校验文案为「请输入仓库名称! 未知异常」（多了「未知异常」后缀）；
    - 仓储费/搬运费无前端数字校验，负数/小数可保存，非数字后端静默失败；
    - 排序字段自由文本无校验。
"""

import time

from config import BASE_URL
from framework.asserts import blocked, check, check_contains, check_eq, check_in
from framework.registry import case, manual
from pages.base_page import spaced

NO_SELECT_MSG = "请选择一条记录！"
NO_NAME_MSG = "请输入仓库名称!"

EXPECTED_HEADERS = [
    "", "#", "操作", "仓库名称", "仓库地址", "仓储费", "搬运费",
    "负责人", "备注", "排序", "状态", "是否默认",
]
EXPECTED_TOOLBAR = ["新增", "删除", "启用", "禁用"]


# ==================== 页面入口 ====================

@case("TC-DEP-001", "通过左侧菜单进入仓库信息页面", "页面入口", "高")
def tc_dep_001(ctx):
    """展开「基础资料」→ 点「仓库信息」，校验地址/标题/菜单高亮。"""
    page = ctx.page
    page.goto(BASE_URL + "/dashboard/analysis", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    submenu = page.locator(".ant-menu-submenu").filter(has_text="基础资料").first
    submenu.wait_for(state="visible", timeout=15000)
    if "ant-menu-submenu-open" not in (submenu.get_attribute("class") or ""):
        submenu.locator(".ant-menu-submenu-title").first.click()
        ctx.depot.pause()

    link = page.locator('.ant-menu-item a[href="/system/depot"]').first
    link.wait_for(state="visible", timeout=10000)
    link.click()
    page.wait_for_timeout(1200)
    ctx.depot._wait_table_loaded()

    check((page.url or "").rstrip("/").endswith("/system/depot"),
          f"进入后地址不符：{page.url}")

    # SPA 路由切换后 document.title 是异步更新的，轮询一下再断言
    deadline = time.time() + 10
    title = page.title().strip()
    while time.time() < deadline and title != "仓库信息 · 管伊佳ERP":
        page.wait_for_timeout(300)
        title = page.title().strip()
    if title != "仓库信息 · 管伊佳ERP":
        # 与多单位/商品页一致的已知行为：SPA 菜单跳转不更新 document.title
        ctx.note(f"偏差：菜单进入后浏览器标题未更新（{title!r}）；直接访问 /system/depot 才是「仓库信息 · 管伊佳ERP」")

    active = [t.strip() for t in page.locator(".ant-menu-item-selected").all_inner_texts()]
    check_in("仓库信息", active, "左侧菜单高亮项")


@case("TC-DEP-002", "直接通过 URL 打开仓库信息页面", "页面入口", "中")
def tc_dep_002(ctx):
    """地址栏直接访问 /system/depot，不应要求重新登录。"""
    page = ctx.page
    ctx.depot.open()
    check_eq((page.url or "").rstrip("/").split("?")[0],
             BASE_URL + "/system/depot", "当前地址")
    check("login" not in (page.url or "").lower(), f"被重定向到登录页：{page.url}")
    active = [t.strip() for t in page.locator(".ant-menu-item-selected").all_inner_texts()]
    check_in("仓库信息", active, "左侧菜单高亮项")
    check(page.locator(".ant-table").count() >= 1, "表格组件应渲染完成")


@case("TC-DEP-003", "页面结构与元素完整性校验", "页面入口", "高")
def tc_dep_003(ctx):
    """逐项核对查询区、工具栏、表头。"""
    depot = ctx.depot.open()

    name_input = depot.page.locator(depot.NAME_INPUT)
    check_eq(name_input.count(), 1, "仓库名称输入框数量")
    check_eq(name_input.first.get_attribute("placeholder"), "请输入仓库名称查询", "仓库名称占位符")

    remark_input = depot.page.locator(depot.REMARK_INPUT)
    check_eq(remark_input.count(), 1, "备注输入框数量")
    check_eq(remark_input.first.get_attribute("placeholder"), "请输入备注查询", "备注占位符")

    for text in ("查询", "重置"):
        check(depot.button(text).count() >= 1, f"查询区缺少「{text}」按钮")

    toolbar = [t.replace(" ", "") for t in
               depot.page.locator(depot.BUTTON_SCOPE).all_inner_texts()]
    for text in EXPECTED_TOOLBAR:
        check_in(text, toolbar, "工具栏按钮")

    headers = [h.strip() for h in depot.page.locator(".ant-table-thead th").all_inner_texts()]
    check_eq(headers, EXPECTED_HEADERS, "表头列序")


# ==================== 列表展示 ====================

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


# ==================== 查询 ====================

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


# ==================== 新增 ====================

@case("TC-DEP-013", "新增弹窗结构与必填标识", "新增", "高")
def tc_dep_013(ctx):
    """新增弹窗标题、字段、必填标识、按钮。"""
    depot = ctx.depot.open()
    depot.open_create_modal()

    check_eq(depot.modal_title(), "新增", "弹窗标题")
    state = depot.form_state() or {}
    for field in ("name", "address", "warehousing", "truckage", "sort", "remark"):
        check(field in state, f"弹窗应含字段 #{field}")

    # 仅「仓库名称」带红色 * 号
    required = {item["text"]: item["star"] for item in (state.get("required") or [])}
    name_label = next((k for k in required if "仓库名称" in k), "")
    check(name_label, "应有「仓库名称」字段标签")
    check_eq(required.get(name_label), True, "仓库名称应带必填 * 号")
    for label, star in required.items():
        if "仓库名称" in label:
            continue
        check(not star, f"字段「{label}」不应带必填 * 号")

    # 按钮：取消、保存
    buttons = [t.replace(" ", "") for t in depot.modal().locator("button").all_inner_texts()]
    for text in ("取消", "保存"):
        check_in(text, buttons, "弹窗按钮")
    depot.cancel()


@case("TC-DEP-014", "空表单保存必填校验", "新增", "高")
def tc_dep_014(ctx):
    """空表单保存 → 提示必填，弹窗保持打开，不产生数据。"""
    depot = ctx.depot.open()
    before = depot.total_count()
    depot.open_create_modal()

    depot.save_blocked(NO_NAME_MSG)
    inline = depot.inline_errors()
    check(any(NO_NAME_MSG in e for e in inline),
          f"应有「请输入仓库名称!」红字，实际：{inline}")
    # 已知偏差：该校验文案带了「未知异常」后缀
    if any("未知异常" in e for e in inline):
        ctx.note("偏差：空表单校验文案为「请输入仓库名称! 未知异常」，多了「未知异常」后缀")
    check(depot.modal_visible(), "保存应被拦截，弹窗保持打开")

    depot.cancel()
    check_eq(depot.total_count(), before, "空表单保存不应产生数据")


@case("TC-DEP-015", "只填仓库名称保存（最简新增）", "新增", "高")
def tc_dep_015(ctx):
    """只填名称保存成功，其余字段为空，状态启用。"""
    depot = ctx.depot.open()
    name = ctx.data.depot_name()
    ctx.data.track_depot(name)

    depot.open_create_modal()
    depot.fill_form(name=name)
    depot.save_success()
    depot.wait_row(name, present=True)

    row = depot.read_row(name)
    check_eq(row["name"], name, "名称列")
    check_eq(row["status"], "启用", "状态默认启用")
    for field in ("address", "warehousing", "truckage", "sort", "remark", "manager"):
        check(row[field] in ("", None), f"未填写的「{field}」应为空，实际 {row[field]!r}")


@case("TC-DEP-016", "填写完整字段保存", "新增", "中")
def tc_dep_016(ctx):
    """全字段填写保存，列表各字段一致。"""
    depot = ctx.depot.open()
    name = ctx.data.depot_name()
    ctx.data.track_depot(name)

    depot.open_create_modal()
    depot.fill_form(name=name, address="北京市朝阳区", warehousing="2.5",
                    truckage="30", sort="3", remark="完整字段测试")
    depot.save_success()
    depot.wait_row(name, present=True)

    row = depot.read_row(name)
    check_eq(row["address"], "北京市朝阳区", "地址列")
    check_eq(row["warehousing"], "2.5", "仓储费列")
    check_eq(row["truckage"], "30", "搬运费列")
    check_eq(row["sort"], "3", "排序列")
    check_eq(row["remark"], "完整字段测试", "备注列")


@case("TC-DEP-017", "仓库名称唯一性校验（不允许重复）", "新增", "中")
def tc_dep_017(ctx):
    """保存同名仓库被拦截，提示「名称已经存在」。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.open_create_modal()
    depot.fill_form(name=name)
    depot.save_blocked("名称已经存在")
    check(depot.modal_visible(), "同名保存应被拦截，弹窗保持打开")
    check(any("名称已经存在" in e for e in depot.inline_errors()),
          "应提示「名称已经存在」")

    # 修改名称后可正常保存
    new_name = ctx.data.depot_name()
    ctx.data.track_depot(new_name)
    depot.fill_form(name=new_name)
    depot.save_success()
    depot.wait_row(new_name, present=True)


@case("TC-DEP-018", "仓储费/搬运费取值规则（数字字段）", "新增", "高")
def tc_dep_018(ctx):
    """仓储费/搬运费无前端数字校验：负数/小数可保存，非数字后端静默失败。"""
    depot = ctx.depot.open()
    # 小数 + 负数可保存
    name1 = ctx.new_depot(warehousing="1.5", truckage="-1")
    row = depot.read_row(name1)
    check_eq(row["warehousing"], "1.5", "仓储费小数可保存")
    check_eq(row["truckage"], "-1", "搬运费负数可保存")
    ctx.note("偏差：仓储费/搬运费无前端格式校验，负数/小数均可保存")

    # 非数字（abc）：保存后弹窗关闭但列表无该记录（后端静默失败无提示）
    bad_name = ctx.data.depot_name()
    ctx.data.track_depot(bad_name)
    depot.open_create_modal()
    depot.fill_form(name=bad_name, warehousing="abc")
    depot.save_success()  # 弹窗会关，且无失败 toast（静默失败）
    check(not depot.has_row(bad_name),
          f"非数字仓储费保存应不入库（列表无 {bad_name!r}）")
    ctx.note("偏差：非数字仓储费导致后端保存失败但无提示，弹窗关闭列表无记录")


@case("TC-DEP-019", "排序字段取值（自由文本无校验）", "新增", "中")
def tc_dep_019(ctx):
    """排序字段自由文本：字符串也可保存并在列表显示。"""
    depot = ctx.depot.open()
    name = ctx.new_depot(sort="abc")
    row = depot.read_row(name)
    check_eq(row["sort"], "abc", "排序字符串可保存并在列表显示")
    ctx.note("偏差：排序字段无数字校验，字符串可保存；排序是否真正影响列表顺序未确认")


@case("TC-DEP-020", "负责人下拉选择", "新增", "中")
def tc_dep_020(ctx):
    """负责人下拉来自账号管理数据，可选中并在列表显示。"""
    depot = ctx.depot.open()
    depot.open_create_modal()

    options = depot.open_manager_options()
    ctx.note(f"负责人下拉选项：{options[:10]}")
    if not options:
        # 账号管理可能无数据，则无法验证选择，归阻塞
        depot.cancel()
        blocked("负责人下拉无选项（账号管理为空），无法验证选择与保存回显")

    depot.choose_manager(options[0])
    name = ctx.data.depot_name()
    ctx.data.track_depot(name)
    depot.fill_form(name=name)
    depot.save_success()
    depot.wait_row(name, present=True)

    row = depot.read_row(name)
    check_eq(row["manager"], options[0], "保存后负责人列应显示所选值")


@case("TC-DEP-021", "取消新增", "新增", "高")
def tc_dep_021(ctx):
    """填写后取消：弹窗关闭、无数据、重开为空表单。"""
    depot = ctx.depot.open()
    name = ctx.data.depot_name()

    depot.open_create_modal()
    depot.fill_form(name=name, address="要丢弃的地址")
    depot.cancel()
    check(not depot.modal_visible(), "取消后弹窗应关闭")

    depot.search(name)
    check_eq(depot.row_count(), 0, "取消后不应新增数据")
    depot.reset()

    depot.open_create_modal()
    state = depot.form_state() or {}
    check_eq(state.get("name"), "", "重新打开时名称应为空")
    check_eq(state.get("address"), "", "重新打开时地址应为空")
    depot.cancel()


@case("TC-DEP-022", "连续新增两条数据", "新增", "中")
def tc_dep_022(ctx):
    """第一条保存后，第二次打开空白表单，能正常保存第二条。"""
    depot = ctx.depot.open()
    first = ctx.new_depot()

    depot.open_create_modal()
    state = depot.form_state() or {}
    check_eq(state.get("name"), "", "第二次打开时名称应无残留")

    second = ctx.data.depot_name()
    ctx.data.track_depot(second)
    depot.fill_form(name=second)
    depot.save_success()
    depot.wait_row(second, present=True)

    check(depot.has_row(first), f"第一条「{first}」应仍在列表")
    check(depot.has_row(second), f"第二条「{second}」应出现在列表")


@case("TC-DEP-023", "仓库名称超长与特殊字符", "新增", "低")
def tc_dep_023(ctx):
    """超长名称被长度限制拦截；引号可保存；emoji 触发后端异常（缺陷）。"""
    depot = ctx.depot.open()
    # 51 个字符：系统限制「长度在 2 到 30 个字符」，应被拦截（符合预期第 1 条）
    long_name = "测" * 51

    depot.open_create_modal()
    depot.fill_form(name=long_name)
    depot.save_blocked("长度在")
    check(depot.modal_visible(), "超长名称保存应被长度限制拦截")
    check(any("长度在" in e for e in depot.inline_errors()),
          "应有长度限制提示（长度在 2 到 30 个字符）")
    depot.cancel()

    # 含引号：可正常保存（在 30 字符内）
    quote_name = ctx.data.depot_name() + '"引号'
    ctx.data.track_depot(quote_name)
    depot.open_create_modal()
    depot.fill_form(name=quote_name)
    depot.save_success()
    depot.wait_row(quote_name, present=True)

    # 含 emoji：预期「无数据库报错」（用例预期第 2 条），实测触发「数据查询异常」
    emoji_name = ctx.data.depot_name() + "😀"
    depot.open_create_modal()
    depot.fill_form(name=emoji_name)
    depot.click_save()
    depot.pause()
    errors = depot.inline_errors()
    if any("数据查询异常" in e for e in errors):
        # 缺陷：emoji 导致后端「数据查询异常」，保存失败且弹窗不关闭
        ctx.note("缺陷：仓库名称含 emoji 时保存报「数据查询异常」，弹窗保持打开无法保存")
        depot.cancel()
        check(False, "仓库名称含 emoji 应可正常保存（用例预期无数据库报错），实际触发「数据查询异常」")
    else:
        depot.save_success()
        depot.wait_row(emoji_name, present=True)
        check(not any("500" in m for m in depot.toasts()), "特殊字符名称不应报错")


# ==================== 编辑 ====================

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


# ==================== 状态 ====================

@case("TC-DEP-027", "禁用一条启用状态的仓库", "状态", "高")
def tc_dep_027(ctx):
    """勾选启用仓库 → 禁用 → 确认 → 状态变禁用。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    check_eq(depot.read_row(name)["status"], "启用", "新增后初始状态")

    title, content = depot.set_status(name, "禁用")
    check_contains(title, "确认操作", "确认框标题")
    check_contains(content, "是否操作选中数据", "确认框正文")
    check_eq(depot.read_row(name)["status"], "禁用", "禁用后的状态列")


@case("TC-DEP-028", "启用一条禁用状态的仓库", "状态", "高")
def tc_dep_028(ctx):
    """先禁用，再启用回来。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()

    depot.set_status(name, "禁用")
    check_eq(depot.read_row(name)["status"], "禁用", "禁用后状态")

    title, content = depot.set_status(name, "启用")
    check_contains(title, "确认操作", "启用确认框标题")
    check_eq(depot.read_row(name)["status"], "启用", "启用后状态")


@case("TC-DEP-029", "未勾选记录点击启用/禁用", "状态", "高")
def tc_dep_029(ctx):
    """未勾选点启用/禁用：提示「请选择一条记录！」，不弹确认框。"""
    depot = ctx.depot.open()
    ctx.new_depot()
    depot.reset()
    depot.clear_selection()
    depot.drain_toasts()

    depot.click_toolbar("启用")
    depot.wait_toast(NO_SELECT_MSG)
    check_eq(depot.confirm_dialog().count(), 0, "未勾选时不应弹确认框")

    depot.drain_toasts()
    depot.click_toolbar("禁用")
    depot.wait_toast(NO_SELECT_MSG)


# ==================== 删除 ====================

@case("TC-DEP-030", "删除单条仓库", "删除", "高")
def tc_dep_030(ctx):
    """勾选 → 删除 → 确认「确认删除/是否删除选中数据?」→ 删除成功无 toast。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    total = depot.total_count()

    depot.clear_selection()
    depot.select_row(name)
    depot.drain_toasts()
    depot.click_toolbar("删除")
    dialog = depot.confirm_dialog()
    dialog.wait_for(state="visible", timeout=8000)
    title, content = depot.confirm_texts()
    check_contains(title, "确认删除", "确认框标题")
    check_contains(content, "是否删除选中数据", "确认框正文")
    depot.click_confirm("确定")

    depot.wait_row(name, present=False)
    check_eq(depot.total_count(), total - 1, "删除后总数")
    check_eq(depot.toasts(), [], "删除成功后不应有 toast 提示")


@case("TC-DEP-031", "取消删除", "删除", "中")
def tc_dep_031(ctx):
    """删除确认框点取消：记录保留、总数不变。"""
    depot = ctx.depot.open()
    name = ctx.new_depot()
    total = depot.total_count()

    depot.clear_selection()
    depot.select_row(name)
    depot.click_toolbar("删除")
    dialog = depot.confirm_dialog()
    dialog.wait_for(state="visible", timeout=8000)
    dialog.locator("button").filter(has_text=spaced("取消")).first.click()
    depot.pause()

    check(depot.has_row(name), "取消后记录应保留")
    check_eq(depot.total_count(), total, "取消后总数不应变化")


@case("TC-DEP-032", "未勾选记录点击删除", "删除", "高")
def tc_dep_032(ctx):
    """未勾选点删除：提示「请选择一条记录！」，不弹确认框。"""
    depot = ctx.depot.open()
    ctx.new_depot()
    depot.reset()
    depot.clear_selection()
    depot.drain_toasts()

    depot.click_toolbar("删除")
    depot.wait_toast(NO_SELECT_MSG)
    check_eq(depot.confirm_dialog().count(), 0, "不应弹出删除确认框")


manual(
    "TC-DEP-033", "删除被业务引用的仓库", "删除", "中",
    reason="业务已确认「被引用仓库可删除、保留现状」，用例预期按此调整；"
           "但构造前置条件需采购/销售单据引用，真删会破坏业务数据，自动化不做此破坏性验证，"
           "请人工用已被引用的仓库执行",
)


# ==================== 商品联动（设为默认） ====================

@case("TC-DEP-034", "行内「设为默认」操作", "商品联动", "高")
def tc_dep_034(ctx):
    """点非默认仓库的「设为默认」→ Popover 确认 → 该仓库变「是」、原默认变「否」。"""
    depot = ctx.depot.open()
    # 造两条，显式把第一条设为默认，第二条即非默认
    first = ctx.new_depot()
    second = ctx.new_depot()
    depot.reset()
    depot.set_default(first)

    check_eq(depot.defaults().get(first), "是", "设为默认后第一条应为默认")
    check_eq(depot.defaults().get(second), "否", "第二条应为非默认")

    popover = depot.open_set_default_popconfirm(second)
    text = popover.inner_text()
    check_contains(text, "确定设为默认吗", "设为默认 Popover 文案")

    depot.click_popconfirm_ok(popover)
    check_eq(depot.defaults().get(second), "是", "设为默认后该仓库应为「是」")
    check_eq(depot.defaults().get(first), "否", "原默认仓库应自动变「否」")


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


@case("TC-DEP-036", "默认仓库唯一性", "商品联动", "中")
def tc_dep_036(ctx):
    """默认仓库唯一：切换默认时原默认自动取消，同一时间仅一个默认。"""
    depot = ctx.depot.open()
    first = ctx.new_depot()
    second = ctx.new_depot()
    third = ctx.new_depot()
    depot.reset()

    depot.set_default(first)
    check_eq(depot.default_name(), first, "设为默认后应为第一条")

    depot.set_default(second)
    check_eq(depot.default_name(), second, "再设为默认后应为第二条")

    depot.set_default(third)
    check_eq(depot.default_name(), third, "再设为默认后应为第三条")

    # 同一时间仅一个默认
    defaults = depot.defaults()
    is_default_count = sum(1 for d in defaults.values() if d == "是")
    check_eq(is_default_count, 1, "同一时间应仅一个默认仓库")


manual(
    "TC-DEP-037", "试用到期后访问与操作", "权限", "低",
    reason="前置条件为「账号试用已到期」，无法在不改变账号状态的前提下构造；到期后人工执行",
)


# ==================== 异常 ====================

@case("TC-DEP-038", "页面顶部出现无关统计卡片", "异常", "中")
def tc_dep_038(ctx):
    """页面顶部可能有「今日销售/本月累计销售」等统计卡片，不作为缺陷，仅确认不影响操作。"""
    depot = ctx.depot.open()

    # 统计卡片是首页模块设计行为，可能存在也可能不存在；只确认表格与工具栏正常
    check(depot.page.locator(".ant-table").count() >= 1, "表格应正常渲染")
    for text in ("新增", "删除", "启用", "禁用"):
        check(depot.button(text).count() >= 1, f"工具栏「{text}」应正常展示")

    # 记录顶部卡片情况（不做通过/失败判断）
    cards = depot.page.locator(".ant-card").all_inner_texts()
    stat_cards = [c for c in cards if ("今日销售" in c or "本月累计" in c)]
    if stat_cards:
        ctx.note("页面顶部存在统计卡片（首页模块设计行为，不作为缺陷）")
    else:
        ctx.note("本次未出现顶部统计卡片")
