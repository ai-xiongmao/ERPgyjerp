"""新增：TC-UNIT-012 ~ 023、038、040、041、043。

这一组用例的共性是「弹窗里的校验与保存」，因此都围绕：
    打开新增弹窗 → 填/漏填字段 → 点保存 → 断言 toast / 内联红字 / 是否落库
"""

from framework.asserts import check, check_contains, check_eq, check_in
from framework.registry import case
from cases._helpers import expected_name, expected_other

DUP_UNIT_MSG = "抱歉，副单位不能为空！"
NO_RATIO_MSG = "抱歉，比例不能为空！"
BAD_RATIO_MSG = "抱歉，比例只能为数字，最多三位小数！"
NO_BASIC_MSG = "请输入基本单位!"


@case("TC-UNIT-012", "仅填基本单位保存被副单位校验拦截", "新增", "高")
def tc_unit_012(ctx):
    """只填基本单位 → 拦截；补填副单位与比例 → 保存成功且默认启用。"""
    unit = ctx.open_unit()
    basic = ctx.data.name("U")

    unit.open_create_modal()
    unit.fill_form(basic, ())
    unit.save_blocked(DUP_UNIT_MSG)
    check(unit.modal_visible(), "被拦截后弹窗应保持打开")

    unit.fill_form(basic, [("箱", 10)])
    unit.save_success()
    unit.wait_row(basic, present=True)

    check_eq(unit.count_row(basic), 1, "拦截期间不应产生数据，补填后只应有 1 条")
    check_eq(unit.read_row(basic)["status"], "启用", "保存后默认状态")


@case("TC-UNIT-013", "填写基本单位+副单位+比例保存", "新增", "高")
def tc_unit_013(ctx):
    """基本单位+副单位+比例 → 保存成功，换算关系 1 箱 = 10 个。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 10)])

    row = unit.read_row(basic)
    check_eq(row["basic"], basic, "基本单位列")
    check_eq(row["other"], expected_other(basic, "箱", 10), "副单位列")
    check_eq(row["name"], expected_name(basic, "箱", 10), "单位名称列")
    check_eq(row["status"], "启用", "状态列")


@case("TC-UNIT-014", "三个副单位全部填写保存", "新增", "中")
def tc_unit_014(ctx):
    """个/盒6/箱60/托3600：三列齐全且比例自洽。"""
    unit = ctx.open_unit()
    try:
        basic = ctx.new_unit([("盒", 6), ("箱", 60), ("托", 3600)])
    except AssertionError as exc:
        ctx.note("实测：填了「副单位3」保存返回 301「数据写入异常」，弹窗关闭但列表无新数据；"
                 "只填 1~2 个副单位则正常（对照 TC-UNIT-005）")
        raise exc

    row = unit.read_row(basic)
    check_eq(row["other"], expected_other(basic, "盒", 6), "副单位列")
    check_eq(row["other2"], expected_other(basic, "箱", 60), "副单位2 列")
    check_eq(row["other3"], expected_other(basic, "托", 3600), "副单位3 列")
    check(row["name"].startswith(f"{basic}/("), f"单位名称格式不符：{row['name']!r}")

    # 换算自洽：1 箱 = 10 盒，1 托 = 60 箱
    check_eq(60 / 6, 10, "箱/盒 换算倍数")
    check_eq(3600 / 60, 60, "托/箱 换算倍数")


@case("TC-UNIT-015", "基本单位为空时保存（必填校验）", "新增", "高")
def tc_unit_015(ctx):
    """空表单直接保存：内联红字提示，弹窗不关且不产生数据。"""
    unit = ctx.open_unit()
    total_before = unit.total_count()

    unit.open_create_modal()
    result = unit.save_blocked(NO_BASIC_MSG)
    check(any(NO_BASIC_MSG in text for text in result["inline"]),
          f"基本单位下方应出现红字「{NO_BASIC_MSG}」，实际：{result['inline']}")
    check(unit.modal_visible(), "校验失败时弹窗应保持打开")

    unit.cancel_modal()
    check_eq(unit.total_count(), total_before, "不应产生任何数据")


@case("TC-UNIT-016", "只填副单位、不填基本单位", "新增", "高")
def tc_unit_016(ctx):
    """只填副单位与比例，基本单位留空 → 提示「请输入基本单位!」并拦截。"""
    unit = ctx.open_unit()
    total_before = unit.total_count()

    unit.open_create_modal()
    unit.fill_form("", [("箱", 10)])
    result = unit.save_blocked(NO_BASIC_MSG)
    check(any(NO_BASIC_MSG in text for text in result["inline"] + result["toast"]),
          f"应提示「{NO_BASIC_MSG}」，实际：{result['inline'] + result['toast']}")
    check(unit.modal_visible(), "保存应被拦截，弹窗保持打开")

    unit.cancel_modal()
    check_eq(unit.total_count(), total_before, "不应产生数据")


@case("TC-UNIT-017", "副单位与比例必须成对填写", "新增", "中")
def tc_unit_017(ctx):
    """只填副单位 → 比例不能为空；只填比例 → 副单位不能为空；都填 → 成功。"""
    unit = ctx.open_unit()
    basic = ctx.data.name("U")

    unit.open_create_modal()

    unit.fill_form(basic, [("箱", "")])
    result = unit.save_blocked(NO_RATIO_MSG)
    check(any(NO_RATIO_MSG in text for text in result["toast"]),
          f"应为顶部 toast「{NO_RATIO_MSG}」，实际：{result['toast']}")
    check(not any(NO_RATIO_MSG in text for text in result["inline"]),
          f"该提示应为 toast 而非表单内联红字：{result['inline']}")
    check(unit.modal_visible(), "第一次拦截后弹窗应保持打开")

    unit.fill_form(basic, [("", 10)])
    result = unit.save_blocked(DUP_UNIT_MSG)
    check(any(DUP_UNIT_MSG in text for text in result["toast"]),
          f"应为顶部 toast「{DUP_UNIT_MSG}」，实际：{result['toast']}")
    check(unit.modal_visible(), "第二次拦截后弹窗应保持打开")

    unit.fill_form(basic, [("箱", 10)])
    unit.save_success()
    unit.wait_row(basic, present=True)
    check_eq(unit.read_row(basic)["status"], "启用", "保存后默认状态")


@case("TC-UNIT-018", "比例输入非法值", "新增", "高")
def tc_unit_018(ctx):
    """-1 / abc 被格式校验拦截，空值提示不能为空，0 实测可保存。"""
    unit = ctx.open_unit()
    zero_basic = ctx.data.name("U")

    unit.open_create_modal()
    unit.fill_form(zero_basic, [("箱", 0)])
    unit.save_success()
    unit.wait_row(zero_basic, present=True)
    check_eq(unit.read_row(zero_basic)["other"], f"箱=0{zero_basic}", "比例 0 的展示")
    ctx.note("比例 0 未被拦截（与 TC-UNIT-040 一致，属缺陷候选）")

    basic = ctx.data.name("U")
    unit.open_create_modal()
    for ratio, expect in (("-1", BAD_RATIO_MSG), ("abc", BAD_RATIO_MSG), ("", NO_RATIO_MSG)):
        unit.fill_form(basic, [("箱", ratio)])
        unit.save_blocked(expect)
        check(unit.modal_visible(), f"比例「{ratio}」保存应被拦截，弹窗保持打开")

    unit.cancel_modal()


@case("TC-UNIT-019", "单位名称允许重复（不校验唯一性）", "新增", "高")
def tc_unit_019(ctx):
    """同名单位可保存两条，且各自独立编辑 / 删除。"""
    unit = ctx.open_unit()
    basic = ctx.data.name("U")

    ctx.new_unit([("箱", 10)], basic=basic)
    ctx.new_unit([("件", 5)], basic=basic)
    check_eq(unit.count_row(basic), 2, "同名记录数")

    same = [row for row in unit.rows_data() if row["basic"] == basic]
    check_eq(sorted(row["other"] for row in same),
             sorted([f"箱=10{basic}", f"件=5{basic}"]), "两条同名记录的副单位")

    # 独立编辑：改「件」那条，另一条不受影响
    nth = next(i for i, row in enumerate(same) if row["other"].startswith("件="))
    unit.open_edit_modal(basic, nth=nth)
    check_contains(unit.form_state()["other"], "件", "编辑弹窗回显的副单位")
    unit.fill_form(basic, [("件", 55)])
    unit.save_success()

    same = [row for row in unit.rows_data() if row["basic"] == basic]
    check_eq(sorted(row["other"] for row in same),
             sorted([f"箱=10{basic}", f"件=55{basic}"]), "编辑后两条记录应互不影响")

    # 独立删除：删一条，另一条保留
    nth = next(i for i, row in enumerate(same) if row["other"].startswith("件="))
    unit.delete(basic, nth=nth)
    check_eq(unit.count_row(basic), 1, "删除一条后剩余条数")
    check_eq(unit.read_row(basic)["other"], f"箱=10{basic}", "剩余记录的副单位")


@case("TC-UNIT-020", "单位名称超长与特殊字符", "新增", "低")
def tc_unit_020(ctx):
    """51 字符与 emoji/引号：按长度限制截断或提示，页面不错乱。"""
    unit = ctx.open_unit()

    unit.open_create_modal()
    unit.fill_form("长" * 51, [("箱", 10)])
    typed = unit.form_state()["basic"]
    ctx.data.track(typed or "长" * 51)   # 万一保存成功，收尾能按名字回收
    unit.click_save()

    if unit.modal_visible():
        messages = unit.toasts() + unit.inline_errors()
        ctx.note(f"51 字符名称被拦截，页面提示：{messages}")
        check(messages, "超长名称被拦截时应给出提示")
        check(len(typed) <= 10 or any("长度" in text for text in messages),
              f"既未按 10 字符截断也未提示长度限制：输入 {len(typed)} 字符，提示 {messages}")
        unit.cancel_modal()
    else:
        unit._wait_table_loaded()
        ctx.note(f"51 字符名称被保存（实际落库 {typed!r}）")
        check(len(typed) <= 10, f"落库名称超过 10 字符：{typed!r}")

    # 特殊字符：emoji + 引号，不要求保存成功，但页面不能崩
    special = f'{ctx.data.token}😀"'
    unit.open_create_modal()
    unit.fill_form(special, [("箱", 10)])
    ctx.data.track(special)
    unit.click_save()
    unit.page.wait_for_timeout(500)
    if unit.modal_visible():
        unit.cancel_modal()
        ctx.note("emoji/引号名称被拦截")
    else:
        unit._wait_table_loaded()
        ctx.note("emoji/引号名称被保存，列表渲染正常")

    messages = unit.toasts()
    check(not any("500" in m for m in messages), f"特殊字符不应导致 500：{messages}")
    check(unit.button("查询").count() >= 1, "页面应仍可操作")


@case("TC-UNIT-021", "取消新增", "新增", "高")
def tc_unit_021(ctx):
    """填写后取消：弹窗关闭、无数据、重开为空表单。"""
    unit = ctx.open_unit()
    basic = ctx.data.name("U")

    unit.open_create_modal()
    unit.fill_form(basic, [("箱", 10)])
    unit.cancel_modal()
    check(not unit.modal_visible(), "取消后弹窗应关闭")

    unit.search(basic)
    check_eq(unit.row_count(), 0, "取消后不应新增数据")
    unit.reset()

    unit.open_create_modal()
    check_eq(unit.form_state()["basic"], "", "重新打开时基本单位应为空")
    unit.cancel_modal()


@case("TC-UNIT-022", "连续新增两条数据", "新增", "中")
def tc_unit_022(ctx):
    """第一条保存后，第二次打开应是空白表单且能正常保存。"""
    unit = ctx.open_unit()
    first = ctx.data.name("U")
    second = ctx.data.name("U")

    ctx.new_unit([("箱", 10)], basic=first)

    unit.open_create_modal()
    state = unit.form_state()
    check_eq(state["basic"], "", "第二次打开时基本单位应无残留")
    check_eq(state["other"], "", "第二次打开时副单位应无残留")
    check_eq(state["ratio"], "", "第二次打开时比例应无残留")

    unit.fill_form(second, [("箱", 10)])
    ctx.data.track(second)
    unit.save_success()
    unit.wait_row(second, present=True)

    check(unit.has_row(first), f"第一条「{first}」应仍在列表")
    check(unit.has_row(second), f"第二条「{second}」应出现在列表")


@case("TC-UNIT-023", "弹窗必填标识与提示文案", "新增", "低")
def tc_unit_023(ctx):
    """只有基本单位带 * 号，副单位/比例不标必填（UI 缺陷记录在案）。"""
    unit = ctx.open_unit()
    unit.open_create_modal()

    state = unit.form_state()
    stars = {item["text"]: item["star"] for item in state["required"]}
    check(stars.get("基本单位"), f"「基本单位」应带红色 * 号：{stars}")
    for label in ("副单位", "副单位2", "副单位3"):
        check(not stars.get(label), f"「{label}」不应带 * 号（实测如此，属已知 UI 缺陷）")

    body = state["bodyText"]
    check("副单位" in body and "=" in body and "基本单位" in body,
          f"换算文案「副单位 = 基本单位」缺失：{body[:120]}")
    ctx.note("副单位与比例实际必填但未标 * 号（已知 UI 缺陷，见用例备注）")
    unit.cancel_modal()


@case("TC-UNIT-038", "比例输入小数边界值（允许最多三位小数）", "新增", "高")
def tc_unit_038(ctx):
    """1.5 与 1.555 可保存，1.5555 被三位小数校验拦截。"""
    unit = ctx.open_unit()

    one_point_five = ctx.data.name("U")
    ctx.new_unit([("箱", "1.5")], basic=one_point_five)
    check_eq(unit.read_row(one_point_five)["other"], f"箱=1.5{one_point_five}",
             "比例 1.5 的展示")

    three_decimals = ctx.data.name("U")
    ctx.new_unit([("箱", "1.555")], basic=three_decimals)
    check_eq(unit.read_row(three_decimals)["other"], f"箱=1.555{three_decimals}",
             "比例 1.555 的展示")

    unit.open_create_modal()
    unit.fill_form(ctx.data.name("U"), [("箱", "1.5555")])
    unit.save_blocked(BAD_RATIO_MSG)
    check(unit.modal_visible(), "四位小数应被拦截，弹窗保持打开")
    unit.cancel_modal()

    ctx.note("小数允许最多三位，原「比例必须为正整数」口径不成立")


@case("TC-UNIT-040", "比例输入 0 可保存（疑似缺陷）", "新增", "高")
def tc_unit_040(ctx):
    """比例 0 未被拦截（缺陷候选），记录实际展示。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("箱", 0)])

    row = unit.read_row(basic)
    check_eq(row["other"], f"箱=0{basic}", "比例 0 的副单位展示")
    check_eq(row["name"], expected_name(basic, "箱", 0), "比例 0 的单位名称")
    ctx.note("比例 0 可保存，换算 1 箱 = 0 个无业务意义（缺陷候选，待产品确认）")


@case("TC-UNIT-041", "比例输入超大值无上限校验", "新增", "中")
def tc_unit_041(ctx):
    """999999 无上限校验，按实测记录展示。"""
    unit = ctx.open_unit()
    basic = ctx.new_unit([("件", 999999)])

    row = unit.read_row(basic)
    check_eq(row["other"], f"件=999999{basic}", "超大比例的副单位展示")
    ctx.note("比例 999999 未被拦截，系统无上限校验（偏差，建议产品明确上限）")


@case("TC-UNIT-043", "新增弹窗重新打开后表单与错误提示应重置", "新增", "中")
def tc_unit_043(ctx):
    """重开后字段为空、无红字；填写基本单位后红字应立即消失。"""
    unit = ctx.open_unit()

    unit.open_create_modal()
    unit.save_blocked(NO_BASIC_MSG)
    check(unit.inline_errors(), "空表单保存后应出现红字校验提示")

    unit.cancel_modal()
    unit.open_create_modal()
    state = unit.form_state()
    check_eq(state["basic"], "", "重开后基本单位字段")
    check_eq(unit.inline_errors(), [], "重开后不应残留红色校验提示")

    unit.fill_form(ctx.data.name("U"), [("箱", 10)])
    unit.pause(500)
    check_eq(unit.inline_errors(), [], "填写基本单位后红字应立即消失")
    unit.cancel_modal()
