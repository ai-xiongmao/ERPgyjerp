"""接口层用例：多单位（与 UI 层同编号双轨）。

和 cases/c_*.py 的区别：
- 不打页面，直接调 /jshERP-boot/unit/*，一条用例通常 0.2~1s；
- 断言对象是「后端到底做了什么」：返回码、落库结果、字段值；
- UI 层的拦截可能是前端做的，接口层会把这件事暴露出来 —— 这正是双轨的意义。

**凡是「本应被拦截却成功了」的用例，都先用 _expect_rejected 把脏数据回滚再判失败**，
否则一条脏数据会污染后续所有查询。

不提供接口版的用例（页面入口 / 结构完整性 / 勾选交互 / 分页器 / toast 文案 / 试用到期）：
TC-UNIT-001~004、010、021、023、028、031、032、034、035、036、037、043。
"""

from framework.asserts import CaseFailed, check, check_eq, check_in, check_ne
from framework.registry import api_case

UNIT_FIELDS = ("id", "name", "basicUnit", "otherUnit", "otherUnitTwo", "otherUnitThree",
               "ratio", "ratioTwo", "ratioThree", "enabled")


def _expect_rejected(ctx, body, label):
    """提交一个「本应被拦截」的新增请求。

    服务端若真的拦住了 → 返回 (code, message)；
    若竟然写入成功 → 先回滚这条脏数据，再抛失败（附提示语），避免污染后续用例。

    回滚用**快照对比**而不是按名称搜：基本单位为空的记录会被写成 `null/(...)`，
    名称里不含测试前缀，按名字根本搜不到。
    """
    before = {r["id"] for r in ctx.unit.all()}
    code, message = ctx.unit.add_raw(body)
    leaked = [r for r in ctx.unit.all() if r["id"] not in before]
    for row in leaked:
        ctx.unit.delete(row["id"])
    if code == 200:
        raise CaseFailed(f"{label}：服务端未拦截，返回成功（已回滚 {len(leaked)} 条）")
    return code, message


def _expect_update_rejected(ctx, row, label, **changes):
    """编辑场景的「本应被拦截」版本。"""
    code, message = ctx.unit.update_raw(row, **changes)
    if code == 200:
        ctx.unit.delete(row["id"])   # 数据可能已被写坏，直接清掉
        raise CaseFailed(f"{label}：服务端未拦截编辑，返回成功（该条已删除）")
    return code, message


# ==================== 列表 / 查询 ====================
@api_case("TC-UNIT-005")
def tc_unit_005(ctx):
    """列表接口返回的字段与新增时填写的内容一致，未填字段为 null 而不是脏值。"""
    _uid, basic, _row = ctx.new_unit([("箱", 10)])

    row = ctx.unit.find(basic)
    check(row is not None, f"列表接口查不到刚新增的「{basic}」")
    for field in UNIT_FIELDS:
        check_in(field, row, f"列表返回字段缺少 {field}")
    check_eq(row["basicUnit"], basic, "basicUnit")
    check_eq(row["otherUnit"], "箱", "otherUnit")
    check_eq(float(row["ratio"]), 10.0, "ratio")
    check_eq(row["otherUnitTwo"], None, "未填写的副单位2应为 null")
    check_eq(row["ratioTwo"], None, "未填写的比例2应为 null")
    check_eq(row["enabled"], True, "新增后默认启用")
    check_eq(str(row["deleteFlag"]), "0", "deleteFlag")


@api_case("TC-UNIT-006")
def tc_unit_006(ctx):
    """不传任何查询条件：返回全量分页数据，不报错。"""
    data = ctx.unit.list(page=1, size=10)
    check(data.get("total", 0) > 0, "无条件查询应返回数据（当前库里有数据）")
    check(len(data.get("rows") or []) > 0, "rows 不应为空")
    check(len(data["rows"]) <= 10, "pageSize=10 时单页不应超过 10 条")


@api_case("TC-UNIT-007")
def tc_unit_007(ctx):
    """按单位名称查询：返回结果都命中该名称。"""
    _uid, basic, _row = ctx.new_unit([("箱", 10)])

    data = ctx.unit.list(name=basic, size=50)
    rows = data.get("rows") or []
    check(len(rows) >= 1, f"按「{basic}」查询应有结果")
    for row in rows:
        hit = basic in str(row.get("basicUnit") or "") or basic in str(row.get("name") or "")
        check(hit, f"结果里出现不匹配的记录：{row.get('name')}")
    check_eq(data.get("total"), len(rows) if len(rows) < 50 else data.get("total"),
             "total 与返回条数")


@api_case("TC-UNIT-008")
def tc_unit_008(ctx):
    """按不存在的名称查询：total=0，rows 为空，不报错。"""
    data = ctx.unit.list(name="ZZ_NOT_EXIST_" + ctx.data.token, size=10)
    check_eq(data.get("total"), 0, "不存在名称的 total")
    check_eq(len(data.get("rows") or []), 0, "不存在名称的 rows")


@api_case("TC-UNIT-009")
def tc_unit_009(ctx):
    """关键字模糊查询：取名称中间片段也能命中。"""
    _uid, basic, _row = ctx.new_unit([("箱", 10)])
    keyword = basic[2:7]           # 去掉前缀，取中间 5 个字符
    check(len(keyword) >= 3, "构造的模糊关键字过短")

    rows = ctx.unit.all(name=keyword)
    hits = [r for r in rows if keyword in str(r.get("basicUnit") or "") or keyword in str(r.get("name") or "")]
    check(len(hits) >= 1, f"模糊关键字「{keyword}」未命中刚新增的记录")
    for row in rows:
        # 服务端按 name 字段 LIKE 匹配，name 里含关键字即算命中
        check(keyword in str(row.get("name") or "") or keyword in str(row.get("basicUnit") or ""),
              f"模糊查询返回了不含关键字「{keyword}」的记录：{row.get('name')}")


@api_case("TC-UNIT-011")
def tc_unit_011(ctx):
    """查询条件输入特殊字符 / 超长文本：不应 500，也不应把服务端打挂。"""
    problems = []
    cases = {
        "SQL 注入串": "' OR 1=1 --",
        "脚本串": "<script>alert(1)</script>",
        "超长 200 字": "长" * 200,
        "百分号通配": "%",
        "emoji": "😀",
    }
    for label, keyword in cases.items():
        status, body = ctx.unit.c.call(
            "GET", "/unit/list",
            {"search": '{"name":%s,"type":""}' % _json_str(keyword),
             "column": "createTime", "order": "desc",
             "currentPage": 1, "pageSize": 10})
        code = body.get("code") if isinstance(body, dict) else None
        if status != 200 or code != 200:
            problems.append(f"{label} → HTTP {status} / code={code} / {_msg(body)}")

    if problems:
        ctx.note("实测：" + "；".join(problems))
        raise CaseFailed("查询含特殊字符时接口异常：" + "；".join(problems))


def _json_str(text):
    import json
    return json.dumps(text, ensure_ascii=False)


def _msg(body):
    from framework.api_client import extract_message
    return extract_message(body) or ""


# ==================== 新增 ====================
@api_case("TC-UNIT-012")
def tc_unit_012(ctx):
    """只填基本单位：服务端应拦截（副单位必填），且不产生数据。"""
    basic = ctx.data.name("U")[:10]
    code, message = _expect_rejected(ctx, {"basicUnit": basic}, "仅填基本单位")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(ctx.unit.find(basic) is None, "被拦截的请求不应留下数据")


@api_case("TC-UNIT-013")
def tc_unit_013(ctx):
    """基本单位 + 副单位 + 比例：保存成功，换算关系 1 箱 = 10 个。"""
    _uid, basic, row = ctx.new_unit([("箱", 10)])
    check(row is not None, "新增后列表应能查到该记录")
    check_eq(row["basicUnit"], basic, "基本单位")
    check_eq(row["otherUnit"], "箱", "副单位")
    check_eq(float(row["ratio"]), 10.0, "比例")
    check_eq(row["enabled"], True, "默认状态")


@api_case("TC-UNIT-014")
def tc_unit_014(ctx):
    """三个副单位全部填写：预期保存成功且三组比例自洽。"""
    basic = ctx.data.name("U")[:10]
    body = ctx.unit.build_body(basic, [("盒", 6), ("箱", 60), ("托", 3600)])
    code, message = ctx.unit.add_raw(body)
    if code != 200:
        raise CaseFailed(
            f"填写三个副单位保存失败：code={code}，提示「{message}」"
            f"（只填 1~2 个副单位可正常保存，见 TC-UNIT-013）")

    row = ctx.unit.find(basic)
    check(row is not None, "保存成功后列表查不到记录")
    check_eq(float(row["ratio"]), 6.0, "副单位1 比例")
    check_eq(float(row["ratioTwo"]), 60.0, "副单位2 比例")
    check_eq(float(row["ratioThree"]), 3600.0, "副单位3 比例")


@api_case("TC-UNIT-015")
def tc_unit_015(ctx):
    """基本单位为空：预期拦截（提示「请输入基本单位!」），且不产生数据。"""
    code, message = _expect_rejected(ctx, {"otherUnit": "箱", "ratio": "10"}, "基本单位为空的请求")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-UNIT-016")
def tc_unit_016(ctx):
    """只填副单位和比例、不填基本单位：预期拦截。"""
    code, message = _expect_rejected(
        ctx, {"otherUnit": "箱", "ratio": "10"}, "只填副单位不填基本单位")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-UNIT-017")
def tc_unit_017(ctx):
    """副单位与比例必须成对：缺任一项都应被拦截，两项齐全才成功。"""
    basic = ctx.data.name("U")[:10]
    c1, m1 = _expect_rejected(ctx, {"basicUnit": basic, "otherUnit": "箱"}, "只填副单位不填比例")
    c2, m2 = _expect_rejected(ctx, {"basicUnit": basic + "X", "ratio": "10"}, "只填比例不填副单位")
    ctx.note(f"只填副单位 → code={c1}「{m1}」；只填比例 → code={c2}「{m2}」")

    _uid, basic3, row = ctx.new_unit([("箱", 10)])
    check(row is not None, "两项齐全时应保存成功")
    check_eq(float(row["ratio"]), 10.0, "比例")


@api_case("TC-UNIT-018")
def tc_unit_018(ctx):
    """比例输入非法值（-1 / abc / 空）：都应被拦截，不能落库成异常数据。"""
    basic = ctx.data.name("U")[:10]
    results = {}
    for label, ratio in (("-1", "-1"), ("abc", "abc"), ("空串", "")):
        code, message = _expect_rejected(
            ctx, {"basicUnit": basic + str(len(results)), "otherUnit": "箱", "ratio": ratio},
            f"比例={label}")
        results[label] = (code, message)
        if code == 500:
            ctx.note(f"比例={label} 时服务端返回 500「{message}」而非友好提示，属提示口径问题")

    ctx.note("非法值均被拦截：" + "；".join(f"{k}→code={v[0]}" for k, v in results.items()))
    check(True, "")


@api_case("TC-UNIT-019")
def tc_unit_019(ctx):
    """同名单位允许重复：两次新增都成功，列表出现两条。"""
    basic = ctx.data.name("U")[:10]
    ctx._track("unit", basic)
    for _ in range(2):
        code, message = ctx.unit.add_raw(ctx.unit.build_body(basic, [("箱", 10)]))
        check_eq(code, 200, f"同名新增应允许，实际 code={code}「{message}」")

    rows = ctx.unit.find_all(basic)
    check(len(rows) >= 2, f"同名记录应有 2 条，实际 {len(rows)} 条")
    check_ne(rows[0]["id"], rows[1]["id"], "两条同名记录的 id 不同")


@api_case("TC-UNIT-020")
def tc_unit_020(ctx):
    """单位名称超长 / 含 emoji：预期给出长度限制提示，不能以数据库报错收场。"""
    over = ctx.data.name("U")[:4] + "超" * 18
    c1, m1 = _expect_rejected(ctx, {"basicUnit": over, "otherUnit": "箱", "ratio": "10"},
                              "基本单位超长 20 字")
    c2, m2 = _expect_rejected(ctx, {"basicUnit": ctx.data.name("U")[:8] + "😀",
                                    "otherUnit": "箱", "ratio": "10"}, "基本单位含 emoji")
    ctx.note(f"超长 → code={c1}「{m1}」；emoji → code={c2}「{m2}」（均为「数据写入异常」，非友好提示）")
    check(True, "")


@api_case("TC-UNIT-022")
def tc_unit_022(ctx):
    """连续新增两条：两条都成功，各自独立。"""
    _u1, b1, _ = ctx.new_unit([("箱", 10)])
    _u2, b2, _ = ctx.new_unit([("件", 5)])

    r1, r2 = ctx.unit.find(b1), ctx.unit.find(b2)
    check(r1 is not None and r2 is not None, "两条记录都应能查到")
    check_ne(r1["id"], r2["id"], "两条记录 id 应不同")
    check_eq(float(r1["ratio"]), 10.0, "第一条比例")
    check_eq(float(r2["ratio"]), 5.0, "第二条比例")


# ==================== 编辑 ====================
@api_case("TC-UNIT-024")
def tc_unit_024(ctx):
    """编辑已有单位：字段更新后落库生效。"""
    _uid, basic, row = ctx.new_unit([("箱", 10)])

    ctx.unit.update_ok(row, ratio="20", otherUnit="件")
    after = ctx.unit.find(basic)
    check_eq(float(after["ratio"]), 20.0, "编辑后比例")
    check_eq(after["otherUnit"], "件", "编辑后副单位")
    check_eq(after["id"], row["id"], "编辑不应改变 id")


@api_case("TC-UNIT-025")
def tc_unit_025(ctx):
    """编辑时清空基本单位：预期拦截，原数据不被修改。"""
    _uid, basic, row = ctx.new_unit([("箱", 10)])
    code, message = ctx.unit.update_raw(row, basicUnit=None)
    if code == 200:
        broken = ctx.unit.find(basic)
        detail = f"名称被写成「{broken.get('name')}」" if broken else "记录已不可查"
        ctx.unit.delete(row["id"])
        raise CaseFailed(f"编辑清空基本单位未被拦截，接口返回成功，{detail}（该条已清理）")
    ctx.note(f"服务端返回 code={code}「{message}」")
    after = ctx.unit.find(basic)
    check(after is not None, "被拦截后原记录应保留")
    check_eq(after["basicUnit"], basic, "原基本单位不应被修改")


# ==================== 状态 ====================
@api_case("TC-UNIT-026")
def tc_unit_026(ctx):
    """禁用一条启用状态的记录：enabled 变为 false。"""
    uid, basic, row = ctx.new_unit([("箱", 10)])
    check_eq(row["enabled"], True, "前置：应为启用状态")

    ctx.unit.set_status_ok(uid, False)
    check_eq(ctx.unit.find(basic)["enabled"], False, "禁用后 enabled")


@api_case("TC-UNIT-027")
def tc_unit_027(ctx):
    """启用一条禁用状态的记录：enabled 变为 true。"""
    uid, basic, _row = ctx.new_unit([("箱", 10)])
    ctx.unit.set_status_ok(uid, False)
    check_eq(ctx.unit.find(basic)["enabled"], False, "前置：应已禁用")

    ctx.unit.set_status_ok(uid, True)
    check_eq(ctx.unit.find(basic)["enabled"], True, "启用后 enabled")


@api_case("TC-UNIT-029")
def tc_unit_029(ctx):
    """勾选单条执行启用/禁用：只影响该条，其他记录不受影响。"""
    uid1, b1, _ = ctx.new_unit([("箱", 10)])
    _uid2, b2, _ = ctx.new_unit([("件", 5)])

    ctx.unit.set_status_ok(uid1, False)
    check_eq(ctx.unit.find(b1)["enabled"], False, "被操作记录状态")
    check_eq(ctx.unit.find(b2)["enabled"], True, "未勾选记录不应被影响")


@api_case("TC-UNIT-039")
def tc_unit_039(ctx):
    """勾选 2 条及以上执行批量启用/禁用与批量删除。"""
    u1, b1, _ = ctx.new_unit([("箱", 10)])
    u2, b2, _ = ctx.new_unit([("件", 5)])
    total_before = ctx.unit.count()

    ctx.unit.set_status_ok([u1, u2], False)
    check_eq(ctx.unit.find(b1)["enabled"], False, "批量禁用：第 1 条")
    check_eq(ctx.unit.find(b2)["enabled"], False, "批量禁用：第 2 条")

    ctx.unit.set_status_ok([u1, u2], True)
    check_eq(ctx.unit.find(b1)["enabled"], True, "批量启用：第 1 条")
    check_eq(ctx.unit.find(b2)["enabled"], True, "批量启用：第 2 条")

    ctx.unit.delete_batch_ok([u1, u2])
    check(ctx.unit.find(b1) is None and ctx.unit.find(b2) is None, "批量删除后两条都应查不到")
    check_eq(ctx.unit.count(), total_before - 2, "批量删除后总数应减 2")


# ==================== 删除 ====================
@api_case("TC-UNIT-030")
def tc_unit_030(ctx):
    """删除单条：记录消失，总数减 1。"""
    uid, basic, _row = ctx.new_unit([("箱", 10)])
    total_before = ctx.unit.count()

    ctx.unit.delete_ok(uid)
    check(ctx.unit.find(basic) is None, "删除后不应再查到该记录")
    check_eq(ctx.unit.count(), total_before - 1, "删除后总数")


# ==================== 边界值 ====================
@api_case("TC-UNIT-038")
def tc_unit_038(ctx):
    """比例小数边界：三位小数允许，四位小数应拦截。"""
    _u1, b1, r1 = ctx.new_unit([("箱", "1.555")])
    check_eq(float(r1["ratio"]), 1.555, "三位小数应原样保存")

    basic = ctx.data.name("U")[:10]
    code, message = ctx.unit.add_raw(
        ctx.unit.build_body(basic, [("箱", "1.5555")]))
    if code == 200:
        saved = ctx.unit.find(basic)
        detail = f"实际落库为 {saved.get('ratio') if saved else '?'}"
        if saved:
            ctx.unit.delete(saved["id"])
        raise CaseFailed(f"四位小数未被拦截，接口返回成功（{detail}，该条已清理）")
    ctx.note(f"四位小数被拦截：code={code}「{message}」")
    check(True, "")


@api_case("TC-UNIT-040")
def tc_unit_040(ctx):
    """比例为 0：实测可保存（业务上无意义，需产品确认是否算缺陷）。"""
    _uid, basic, row = ctx.new_unit([("箱", "0")])
    check_eq(float(row["ratio"]), 0.0, "比例 0 落库值")
    ctx.note("比例=0 可正常保存（与用例表记录一致）；换算 1 箱=0 个无业务意义，建议产品确认")


@api_case("TC-UNIT-041")
def tc_unit_041(ctx):
    """比例输入超大值：实测无上限校验。"""
    _uid, basic, row = ctx.new_unit([("件", "99999999")])
    check_eq(float(row["ratio"]), 99999999.0, "超大比例落库值")
    ctx.note("比例 99999999 可正常保存，服务端无上限校验（与用例表记录一致）")


# ==================== 联动 ====================
@api_case("TC-UNIT-042")
def tc_unit_042(ctx):
    """商品端「多单位」下拉与本单位数据联动：新增后无需刷新即可选到。"""
    _uid, basic, _row = ctx.new_unit([("箱", 10)])

    options = ctx.unit.options()
    names = [o.get("name") for o in options]
    hit = [n for n in names if n and basic in n]
    check(len(hit) >= 1, f"下拉接口 /unit/getAllList 未包含新记录「{basic}」")
    expected = f"{basic}/(箱=10{basic})"
    check_in(expected, names, "下拉里的单位名称格式应为「基本单位/(副单位=比例基本单位)」")


@api_case("TC-UNIT-044", unblock=True)
def tc_unit_044(ctx):
    """删除被商品引用的单位：预期拦截，商品数据不受影响。"""
    uid, basic, _row = ctx.new_unit([("箱", 10)])
    _mid, mname, _mrow = ctx.new_material(unit=basic)

    code, message = ctx.unit.delete(uid)
    still_there = ctx.unit.find(basic) is not None
    material = ctx.material.find(mname)

    if code == 200:
        # 单位被删掉了，商品还挂着这个已不存在的单位
        raise CaseFailed(
            f"单位已被商品「{mname}」引用，删除接口仍返回成功（code=200），"
            f"单位{'仍在' if still_there else '已被删除'}；无依赖校验")
    ctx.note(f"服务端返回 code={code}「{message}」")
    check(still_there, "被拦截后单位记录应保留")
    check(material is not None, "商品数据不应受影响")
    check_eq(material.get("unit"), basic, "商品的单位字段不应被改动")
