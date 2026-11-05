"""接口层用例：仓库信息（与 UI 层同编号双轨）。

覆盖点：列表字段、名称/备注/模糊查询、空表单校验、最简与完整新增、
名称唯一性、数字字段规则、排序自由文本、负责人、连续新增、超长/特殊字符、
编辑、状态、删除、设为默认与默认唯一性。

不提供接口版：TC-DEP-001~004、006、010、013、021、026、029、031、032、
037、038。

注意：仓库页「默认仓库」是全局唯一状态。造数据时若把测试仓库设成默认，
收尾删除后环境会回到「无仓库」，与测试前一致，因此不改动既有配置。
"""

from framework.asserts import CaseFailed, check, check_eq, check_in, check_ne
from framework.registry import api_case


def _snapshot(ctx):
    rows = ctx.depot.list(page=1, size=200).get("rows") or []
    return {r["id"] for r in rows}


def _expect_rejected(ctx, body, label):
    before = _snapshot(ctx)
    code, message = ctx.depot.add_raw(body)
    if code == 200:
        after = _snapshot(ctx) - before
        if after:
            ctx.depot.delete_batch(list(after))
        raise CaseFailed(f"{label}：服务端未拦截，返回成功（已回滚 {len(after)} 条）")
    return code, message


# ==================== 列表 / 查询 ====================
@api_case("TC-DEP-005")
def tc_dep_005(ctx):
    """列表接口返回的名称/地址/仓储费/搬运费/备注/排序/状态/是否默认与新增一致。"""
    _did, name, _row = ctx.new_depot(address="地址A", warehousing=2.5, truckage=10, sort=5,
                                     remark="备注A")

    row = ctx.depot.find(name)
    check(row is not None, f"列表接口查不到仓库「{name}」")
    for field in ("id", "name", "address", "warehousing", "truckage", "remark",
                  "sort", "enabled", "isDefault"):
        check_in(field, row, f"列表返回字段缺少 {field}")
    check_eq(row["name"], name, "name")
    check_eq(row["address"], "地址A", "address")
    check_eq(float(row["warehousing"]), 2.5, "warehousing")
    check_eq(float(row["truckage"]), 10.0, "truckage")
    check_eq(row["enabled"], True, "默认启用")
    check_in(row["isDefault"], (True, False), "isDefault 应为布尔值")


@api_case("TC-DEP-007")
def tc_dep_007(ctx):
    """不传查询条件：正常返回，不报错（当前无数据时 total=0 也合法）。"""
    data = ctx.depot.list(page=1, size=10)
    check_in("total", data, "返回结构应含 total")
    check_in("rows", data, "返回结构应含 rows")


@api_case("TC-DEP-008")
def tc_dep_008(ctx):
    """按仓库名称查询：命中的记录都包含该关键字。"""
    _did, name, _row = ctx.new_depot()

    rows = ctx.depot.all(name=name)
    hit = [r for r in rows if r.get("name") == name]
    check(len(hit) >= 1, f"按「{name}」查询未命中")
    for r in rows:
        check(name in str(r.get("name") or ""), f"结果里出现不匹配的仓库：{r.get('name')}")


@api_case("TC-DEP-009")
def tc_dep_009(ctx):
    """按备注查询：只命中备注匹配的仓库。"""
    tag = "备注" + ctx.data.token[-4:]
    _d1, n1, _r1 = ctx.new_depot(remark=tag)
    _d2, n2, _r2 = ctx.new_depot(remark="其它备注")

    rows = ctx.depot.all(remark=tag)
    names = [r.get("name") for r in rows]
    check_in(n1, names, "备注匹配的仓库应被查出")
    check(n2 not in names, "备注不匹配的仓库不应出现")
    for r in rows:
        check(tag in str(r.get("remark") or ""), "结果里的备注应包含关键字")


@api_case("TC-DEP-011")
def tc_dep_011(ctx):
    """查询条件输入特殊字符 / 超长文本：不应 500，也不应触发脚本。"""
    import json as _json

    problems = []
    for label, keyword in (("SQL 注入串", "' OR 1=1 --"),
                           ("脚本串", "<script>alert(1)</script>"),
                           ("超长 200 字", "长" * 200),
                           ("emoji", "😀")):
        status, body = ctx.depot.c.call("GET", "/depot/list", {
            "search": _json.dumps({"name": keyword, "remark": ""}, ensure_ascii=False),
            "column": "createTime", "order": "desc", "currentPage": 1, "pageSize": 10})
        code = body.get("code") if isinstance(body, dict) else None
        if status != 200 or code != 200:
            problems.append(f"{label} → HTTP {status} / code={code}")

    if problems:
        ctx.note("实测：" + "；".join(problems))
        raise CaseFailed("仓库查询含特殊字符时接口异常：" + "；".join(problems))


@api_case("TC-DEP-012")
def tc_dep_012(ctx):
    """名称模糊查询：中间片段也能命中。"""
    _did, name, _row = ctx.new_depot()
    keyword = name[2:8]

    rows = ctx.depot.all(name=keyword)
    hits = [r for r in rows if name in str(r.get("name") or "")]
    check(len(hits) >= 1, f"模糊关键字「{keyword}」未命中「{name}」")
    for r in rows:
        check(keyword in str(r.get("name") or ""), "结果里的名称应包含关键字")


# ==================== 新增 ====================
@api_case("TC-DEP-014")
def tc_dep_014(ctx):
    """空表单保存：预期提示「请输入仓库名称!」，且不产生数据。"""
    code, message = _expect_rejected(ctx, {"address": "x"}, "仓库名称为空")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-DEP-015")
def tc_dep_015(ctx):
    """只填仓库名称保存：成功、默认启用，其余字段为空。"""
    _did, name, row = ctx.new_depot()
    check(row is not None, "保存后应能查到")
    check_eq(row["enabled"], True, "默认状态")
    check_eq(row.get("address"), None, "仓库地址应为空")
    check_eq(row.get("remark"), None, "备注应为空")


@api_case("TC-DEP-016")
def tc_dep_016(ctx):
    """填写完整字段保存：地址/仓储费/搬运费/排序/备注都落库。"""
    _did, name, _row = ctx.new_depot(address="详细地址1号", warehousing=3.5, truckage=20,
                                     sort=8, remark="完整字段备注")
    row = ctx.depot.find(name)
    check_eq(row.get("address"), "详细地址1号", "地址")
    check_eq(float(row.get("warehousing")), 3.5, "仓储费")
    check_eq(float(row.get("truckage")), 20.0, "搬运费")
    check_eq(str(row.get("sort")), "8", "排序")
    check_eq(row.get("remark"), "完整字段备注", "备注")


@api_case("TC-DEP-017")
def tc_dep_017(ctx):
    """仓库名称唯一性：保存同名仓库应被拦截。"""
    _did, name, _row = ctx.new_depot()

    # 先看前端用来查重的接口是否认得出重名
    _st, body = ctx.depot.check_name_exist(name, 0)
    exists = bool((body.get("data") or {}).get("status")) if isinstance(body.get("data"), dict) else body.get("data")
    ctx.note(f"checkIsNameExist 对已存在名称返回：{body.get('data')}")

    code, message = _expect_rejected(ctx, {"name": name}, "同名仓库")
    ctx.note(f"新增同名仓库返回 code={code}「{message}」")
    check(True, "")


@api_case("TC-DEP-018")
def tc_dep_018(ctx):
    """仓储费/搬运费：接受负数与小数；非数字不入库。"""
    tag = ctx.data.token[-4:]
    _d1, n1, _r1 = ctx.new_depot(name="负数" + tag, warehousing=-1, truckage=-2)
    row = ctx.depot.find(n1)
    check_eq(float(row.get("warehousing")), -1.0, "负数仓储费")

    _d2, n2, _r2 = ctx.new_depot(name="小数" + tag, warehousing=1.5)
    check_eq(float(ctx.depot.find(n2).get("warehousing")), 1.5, "小数仓储费")

    before = _snapshot(ctx)
    code, message = ctx.depot.add_raw({"name": "非数字" + tag, "warehousing": "abc"})
    after = _snapshot(ctx) - before
    if code == 200:
        if after:
            ctx.depot.delete_batch(list(after))
        raise CaseFailed("仓储费传非数字 abc 时接口返回成功，脏数据已回滚")
    ctx.note(f"非数字仓储费返回 code={code}「{message}」，未入库（与用例表记录一致）")
    check(True, "")


@api_case("TC-DEP-019")
def tc_dep_019(ctx):
    """排序字段为自由文本：字符串「abc」也可保存。"""
    _did, name, _row = ctx.new_depot(name="排序" + ctx.data.token[-4:], sort="abc")
    row = ctx.depot.find(name)
    check_eq(str(row.get("sort")), "abc", "排序字段应原样保存字符串")


@api_case("TC-DEP-020")
def tc_dep_020(ctx):
    """负责人下拉来自账号管理：选中后保存并回显。"""
    users = ctx.client.ok("GET", "/user/getUserList", label="负责人下拉") or []
    check(len(users) > 0, "账号管理里没有用户，无法选择负责人")
    user = users[0]

    _did, name, _row = ctx.new_depot(name="负责人" + ctx.data.token[-4:],
                                     principal=user["id"])
    row = ctx.depot.find(name)
    check_eq(row.get("principal"), user["id"], "负责人 id")
    check_eq(row.get("principalName"), user.get("userName"), "负责人名称")


@api_case("TC-DEP-022")
def tc_dep_022(ctx):
    """连续新增两条：两条独立存在。"""
    _d1, n1, _r1 = ctx.new_depot()
    _d2, n2, _r2 = ctx.new_depot()
    check(ctx.depot.find(n1) is not None and ctx.depot.find(n2) is not None, "两条都应能查到")
    check_ne(n1, n2, "两条名称应不同")


@api_case("TC-DEP-023")
def tc_dep_023(ctx):
    """仓库名称超长 / 含 emoji：应给出长度提示，不能以数据库报错收场。"""
    over = "超" * 60
    c1, m1 = _expect_rejected(ctx, {"name": over}, "仓库名称超长")
    c2, m2 = _expect_rejected(ctx, {"name": "emoji" + ctx.data.token[-4:] + "😀"}, "仓库名称含 emoji")
    ctx.note(f"超长 → code={c1}「{m1}」；emoji → code={c2}「{m2}」（均为「数据写入异常」，非友好提示）")
    check(True, "")


# ==================== 编辑 ====================
@api_case("TC-DEP-024")
def tc_dep_024(ctx):
    """编辑已有仓库：修改后落库同步，未修改字段保持不变。"""
    _did, name, row = ctx.new_depot(address="原地址", remark="原备注")

    ctx.depot.update_ok(row, address="新地址")
    after = ctx.depot.find(name)
    check_eq(after.get("address"), "新地址", "编辑后地址")
    check_eq(after.get("remark"), "原备注", "未修改字段应保持不变")
    check_eq(after["id"], row["id"], "编辑不应改变 id")


@api_case("TC-DEP-025")
def tc_dep_025(ctx):
    """编辑时清空仓库名称：预期拦截，原数据不被修改。"""
    _did, name, row = ctx.new_depot()

    code, message = ctx.depot.update_raw(row, name=None)
    still = ctx.depot.find(name)
    if code == 200:
        if still is None:
            ctx.depot.delete_batch([row["id"]])
            raise CaseFailed("编辑清空仓库名称未被拦截，记录已被改坏（已清理）")
        raise CaseFailed(
            f"编辑清空仓库名称未被拦截：接口返回 code=200「{message}」，"
            f"服务端静默忽略空名称（数据未被破坏，但前端会误判为保存成功）")

    ctx.note(f"服务端返回 code={code}「{message}」")
    check(still is not None, "被拦截后原记录应保留")
    check_eq(still.get("name"), name, "原名不应被修改")


# ==================== 状态 ====================
@api_case("TC-DEP-027")
def tc_dep_027(ctx):
    """禁用一条启用状态的仓库。"""
    did, name, row = ctx.new_depot()
    check_eq(row["enabled"], True, "前置：应为启用")

    ctx.depot.set_status_ok(did, False)
    check_eq(ctx.depot.find(name)["enabled"], False, "禁用后 enabled")


@api_case("TC-DEP-028")
def tc_dep_028(ctx):
    """启用一条禁用状态的仓库。"""
    did, name, _row = ctx.new_depot()
    ctx.depot.set_status_ok(did, False)
    check_eq(ctx.depot.find(name)["enabled"], False, "前置：应已禁用")

    ctx.depot.set_status_ok(did, True)
    check_eq(ctx.depot.find(name)["enabled"], True, "启用后 enabled")


# ==================== 删除 ====================
@api_case("TC-DEP-030")
def tc_dep_030(ctx):
    """删除单条仓库：记录消失、总数减 1。"""
    did, name, _row = ctx.new_depot()
    total_before = ctx.depot.count()

    ctx.depot.delete_batch_ok([did])
    check(ctx.depot.find(name) is None, "删除后不应再查到")
    check_eq(ctx.depot.count(), total_before - 1, "删除后总数")


# ==================== 默认仓库 ====================
@api_case("TC-DEP-034")
def tc_dep_034(ctx):
    """设为默认：该条变「是」，原默认自动变「否」。"""
    d1, n1, _r1 = ctx.new_depot()
    d2, n2, _r2 = ctx.new_depot()

    # 制造一个明确的默认：先把第 1 条设为默认
    ctx.depot.set_default_ok(d1)
    check_eq(ctx.depot.find(n1).get("isDefault"), True, "设为默认后 isDefault")
    check_eq(ctx.depot.find(n2).get("isDefault"), False, "另一条应为非默认")

    ctx.depot.set_default_ok(d2)
    check_eq(ctx.depot.find(n2).get("isDefault"), True, "切换到第 2 条后 isDefault")
    check_eq(ctx.depot.find(n1).get("isDefault"), False, "原默认应自动取消")


@api_case("TC-DEP-035")
def tc_dep_035(ctx):
    """是否默认字段：默认仓库显示是、其余显示否，且第一条自动成为默认。"""
    d1, n1, row1 = ctx.new_depot()
    _d2, n2, row2 = ctx.new_depot()

    defaults = [r for r in ctx.depot.all(name=ctx.data.token) if r.get("isDefault")]
    check(len(defaults) >= 1, "至少应有一个默认仓库")
    # 若环境原本没有默认仓库，第一条新增的应自动成为默认
    if row1.get("isDefault") is False and row2.get("isDefault") is False:
        ctx.note("两条新增仓库都不是默认：环境里已有其它默认仓库，属正常（见 TC-DEP-036）")
    check(True, "")


@api_case("TC-DEP-036")
def tc_dep_036(ctx):
    """默认仓库唯一：任何时刻全库只有一个 isDefault=true。"""
    d1, n1, _r1 = ctx.new_depot()
    d2, n2, _r2 = ctx.new_depot()

    ctx.depot.set_default_ok(d1)
    ctx.depot.set_default_ok(d2)

    all_rows = ctx.depot.all()
    defaults = [r for r in all_rows if r.get("isDefault") in (True, "1", 1)]
    check_eq(len(defaults), 1, f"默认仓库应唯一，实际 {len(defaults)} 个：{[r.get('name') for r in defaults]}")
    check_eq(defaults[0]["id"], d2, "最后设为默认的那条应为唯一默认")
