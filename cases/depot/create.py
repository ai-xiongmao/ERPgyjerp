"""仓库信息 - 新增（TC-DEP-013 ~ 023）。

弹窗结构与必填标识、空表单校验、最简与完整新增、名称唯一性、
数字与排序字段规则、负责人下拉、连续新增、超长与特殊字符。
"""

from cases.depot._const import NO_NAME_MSG
from framework.asserts import blocked, check, check_eq, check_in
from framework.registry import case


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
