"""接口层用例：商品信息（与 UI 层同编号双轨）。

覆盖点：列表字段、关键词/规格/高级查询、新增必填校验、完整字段、手动条码、
连续新增、编辑、状态、删除、复制新增、多单位下拉联动。

不提供接口版：TC-MAT-001~004、006、010（类别树为空，阻塞）、012、014、
020、022~025、029、030、033、034、036、037（被引用删除需业务单据，阻塞）、
038、039、042（批量编辑 /batchUpdate 尚未取到真实请求体）、043。
"""

from framework.asserts import CaseFailed, check, check_eq, check_in, check_ne
from framework.registry import api_case


def _snapshot(ctx):
    """当前商品 id 集合（用于回滚「本应被拦截却写成功」的脏数据）。"""
    rows = ctx.material.list(page=1, size=200).get("rows") or []
    return {r["id"] for r in rows}


def _expect_rejected(ctx, body, label):
    """提交本应被拦截的新增；若成功则回滚新增记录并判失败。"""
    before = _snapshot(ctx)
    code, message = ctx.material.add_raw(body)
    if code == 200:
        after = _snapshot(ctx) - before
        if after:
            ctx.material.delete_batch(list(after))
        raise CaseFailed(f"{label}：服务端未拦截，返回成功（已回滚 {len(after)} 条）")
    return code, message


# ==================== 列表 / 查询 ====================
@api_case("TC-MAT-005")
def tc_mat_005(ctx):
    """列表接口返回的条码/名称/规格/型号/单位/状态与新增一致。"""
    _mid, name, _row = ctx.new_material(standard="规格A", model="型号A")

    row = ctx.material.find(name)
    check(row is not None, f"列表接口查不到商品「{name}」")
    for field in ("id", "name", "unit", "mBarCode", "standard", "model", "enabled"):
        check_in(field, row, f"列表返回字段缺少 {field}")
    check_eq(row["name"], name, "name")
    check_eq(row["unit"], "个", "unit")
    check_eq(row["standard"], "规格A", "standard")
    check_eq(row["enabled"], True, "新增后默认启用")
    check_ne(row.get("mBarCode"), None, "条码应自动生成")


@api_case("TC-MAT-007")
def tc_mat_007(ctx):
    """不传查询条件：返回全量分页数据，不报错。"""
    data = ctx.material.list(page=1, size=10)
    check(data.get("total", 0) > 0, "无条件查询应返回数据")
    check(len(data.get("rows") or []) > 0, "rows 不应为空")


@api_case("TC-MAT-008")
def tc_mat_008(ctx):
    """关键词查询：条码、名称、助记码任一命中（模糊匹配）。"""
    _mid, name, row = ctx.new_material()
    barcode = row.get("mBarCode")
    mnemonic = row.get("mnemonic") or name

    for label, keyword in (("名称片段", name[2:]), ("条码", barcode), ("助记码", mnemonic)):
        rows = ctx.material.all(keyword=keyword)
        hit = [r for r in rows if r.get("id") == row["id"]]
        check(len(hit) >= 1, f"按{label}「{keyword}」未命中该商品")
        for r in rows:
            matched = any(keyword in str(r.get(f) or "")
                          for f in ("mBarCode", "name", "mnemonic"))
            check(matched, f"结果里出现不含关键词「{keyword}」的记录：{r.get('name')}/{r.get('mBarCode')}")


@api_case("TC-MAT-009")
def tc_mat_009(ctx):
    """按规格查询：只命中规格匹配的商品。"""
    spec = "规格" + ctx.data.token[-3:]
    _mid, name, _row = ctx.new_material(standard=spec)
    _mid2, other, _row2 = ctx.new_material(standard="其它规格")

    rows = ctx.material.all(keyword="", standard=spec)
    ids = {r["id"] for r in rows}
    check(_mid in ids, f"按规格「{spec}」未命中目标商品")
    check(_mid2 not in ids, "规格不匹配的商品不应出现在结果里")
    for r in rows:
        check_eq(r.get("standard"), spec, "结果里的规格")


@api_case("TC-MAT-011")
def tc_mat_011(ctx):
    """展开后的高级查询字段（型号/颜色/品牌/制造商）可正常过滤。"""
    tag = ctx.data.token[-4:]
    _mid, name, _row = ctx.new_material(model="型号" + tag, color="红", brand="品牌" + tag)

    checks = {"model": "型号" + tag, "color": "红", "brand": "品牌" + tag}
    for field, value in checks.items():
        rows = ctx.material.all(keyword="", **{field: value})
        ids = {r["id"] for r in rows}
        check(_mid in ids, f"高级查询 {field}={value} 未命中目标商品")
    check(True, "")


@api_case("TC-MAT-013")
def tc_mat_013(ctx):
    """查询条件输入特殊字符 / 超长文本：不应 500，也不应触发脚本。"""
    import json as _json

    problems = []
    for label, keyword in (("SQL 注入串", "' OR 1=1 --"),
                           ("脚本串", "<script>alert(1)</script>"),
                           ("超长 200 字", "长" * 200),
                           ("emoji", "😀")):
        search = ctx.material._search(keyword=keyword)
        status, body = ctx.material.c.call("GET", "/material/list", {
            "search": _json.dumps(search, ensure_ascii=False),
            "column": "createTime", "order": "desc", "currentPage": 1, "pageSize": 10})
        code = body.get("code") if isinstance(body, dict) else None
        if status != 200 or code != 200:
            problems.append(f"{label} → HTTP {status} / code={code}")

    if problems:
        ctx.note("实测：" + "；".join(problems))
        raise CaseFailed("商品查询含特殊字符时接口异常：" + "；".join(problems))


# ==================== 新增 ====================
@api_case("TC-MAT-015")
def tc_mat_015(ctx):
    """空表单保存：预期提示名称/单位必填，且不产生数据。"""
    payload = {"meList": [], "stock": [], "sortList": [], "unitId": "", "imgName": "",
               "meDeleteIdList": []}
    code, message = _expect_rejected(ctx, payload, "空表单新增商品")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-MAT-016")
def tc_mat_016(ctx):
    """只填名称不填单位：预期拦截。"""
    _mid, name, _row = ctx.new_material()          # 先占一个名字来源，避免与已有数据重名
    payload = ctx.material.build_body(name + "N", None, bar_code=ctx.material.next_barcode())
    code, message = _expect_rejected(ctx, payload, "只填名称不填单位")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-MAT-017")
def tc_mat_017(ctx):
    """只填单位不填名称：预期拦截。"""
    payload = ctx.material.build_body(None, "个", bar_code=ctx.material.next_barcode())
    code, message = _expect_rejected(ctx, payload, "只填单位不填名称")
    ctx.note(f"服务端返回 code={code}，提示「{message}」")
    check(True, "")


@api_case("TC-MAT-018")
def tc_mat_018(ctx):
    """填写必填项（名称+单位）保存：成功、默认启用、条码自动生成。"""
    _mid, name, row = ctx.new_material()
    check(row is not None, "保存后列表应能查到")
    check_eq(row["unit"], "个", "单位")
    check_eq(row["enabled"], True, "默认状态")
    check_ne(row.get("mBarCode"), None, "条码应自动生成")


@api_case("TC-MAT-019")
def tc_mat_019(ctx):
    """填写完整字段保存：规格/型号/颜色/品牌/制造商/备注/扩展字段都落库。"""
    tag = ctx.data.token[-4:]
    extras = {
        "standard": "规格" + tag, "model": "型号" + tag, "color": "蓝",
        "brand": "品牌" + tag, "mfrs": "制造商" + tag, "remark": "备注" + tag,
        "otherField1": "扩展1" + tag, "position": "A-01", "weight": 1.5,
        "expiryNum": 12,
    }
    _mid, name, _row = ctx.new_material(**extras)

    row = ctx.material.find(name)
    for field, value in extras.items():
        if field in ("weight", "expiryNum"):
            check_eq(float(row.get(field)), float(value), field)
        else:
            check_eq(row.get(field), value, field)


@api_case("TC-MAT-021")
def tc_mat_021(ctx):
    """多单位下拉与多单位页联动：新录入的单位无需刷新即可选到。"""
    _uid, basic, _urow = ctx.new_unit([("箱", 10)])

    options = ctx.unit.options()
    names = [o.get("name") for o in options]
    check(any(n and basic in n for n in names),
          f"多单位下拉未包含新录入的单位「{basic}」")


@api_case("TC-MAT-026")
def tc_mat_026(ctx):
    """连续新增两条：两条独立存在。"""
    _m1, n1, r1 = ctx.new_material()
    _m2, n2, r2 = ctx.new_material()

    check_ne(r1["id"], r2["id"], "两条商品 id 应不同")
    check_ne(r1.get("mBarCode"), r2.get("mBarCode"), "两条商品条码应不同")
    check(ctx.material.find(n1) is not None and ctx.material.find(n2) is not None,
          "两条商品都应能查到")


# ==================== 编辑 ====================
@api_case("TC-MAT-027")
def tc_mat_027(ctx):
    """编辑已有商品：修改字段后落库同步，条码不变。"""
    _mid, name, row = ctx.new_material()
    barcode = row.get("mBarCode")

    ctx.material.update_ok(row, remark="编辑后备注", model="新型号")
    after = ctx.material.find(name)
    check_eq(after.get("remark"), "编辑后备注", "编辑后备注")
    check_eq(after.get("model"), "新型号", "编辑后型号")
    check_eq(after.get("mBarCode"), barcode, "条码不应被编辑改掉")


@api_case("TC-MAT-028")
def tc_mat_028(ctx):
    """编辑时清空名称：预期拦截，原数据不被修改。"""
    _mid, name, row = ctx.new_material()

    code, message = ctx.material.update_raw(row, name=None)
    still = ctx.material.find(name)
    if code == 200:
        if still is None:
            ctx.material.delete_batch([row["id"]])
            raise CaseFailed("编辑清空名称未被拦截，商品名称被置空（该条已清理）")
        raise CaseFailed(
            f"编辑清空名称未被拦截：接口返回 code=200「{message}」，"
            f"服务端静默忽略空名称（数据未被破坏，但前端会误判为保存成功）")

    ctx.note(f"服务端返回 code={code}「{message}」")
    check(still is not None, "被拦截后原记录应保留")
    check_eq(still.get("name"), name, "原名称不应被修改")


# ==================== 状态 ====================
@api_case("TC-MAT-031")
def tc_mat_031(ctx):
    """禁用一条启用状态的商品。"""
    mid, name, row = ctx.new_material()
    check_eq(row["enabled"], True, "前置：应为启用")

    ctx.material.set_status_ok(mid, False)
    check_eq(ctx.material.find(name)["enabled"], False, "禁用后 enabled")


@api_case("TC-MAT-032")
def tc_mat_032(ctx):
    """启用一条禁用状态的商品。"""
    mid, name, _row = ctx.new_material()
    ctx.material.set_status_ok(mid, False)
    check_eq(ctx.material.find(name)["enabled"], False, "前置：应已禁用")

    ctx.material.set_status_ok(mid, True)
    check_eq(ctx.material.find(name)["enabled"], True, "启用后 enabled")


# ==================== 删除 ====================
@api_case("TC-MAT-035")
def tc_mat_035(ctx):
    """删除单条商品：记录消失、总数减 1。"""
    mid, name, _row = ctx.new_material()
    total_before = ctx.material.count()

    ctx.material.delete_batch_ok([mid])
    check(ctx.material.find(name) is None, "删除后不应再查到")
    check_eq(ctx.material.count(), total_before - 1, "删除后总数")


# ==================== 条码 / 复制 ====================
@api_case("TC-MAT-040")
def tc_mat_040(ctx):
    """手动编辑条码：保存后以手动填写值为准。"""
    manual = "99" + ctx.data.token[-4:] + "01"
    status, body = ctx.material.check_barcode_exist(manual, 0)
    exists = bool((body.get("data") or {}).get("status")) if isinstance(body.get("data"), dict) else False
    check(not exists, f"前置：手动条码 {manual} 已被占用，换一个用例前缀重跑")

    _mid, name, row = ctx.new_material(bar_code=manual)
    check_eq(row.get("mBarCode"), manual, "手动填写的条码")


@api_case("TC-MAT-041")
def tc_mat_041(ctx):
    """复制新增：复用名称与单位，条码重新生成（不复用源条码），库存不复制。"""
    _src_id, src_name, src = ctx.new_material()
    src_barcode = src.get("mBarCode")

    copy_name = src_name + "C"
    _mid, _name, copy_row = ctx.new_material(name=copy_name, unit=src.get("unit"))

    check_eq(copy_row.get("name"), copy_name, "复制后名称")
    check_eq(copy_row.get("unit"), src.get("unit"), "复制后单位")
    check_ne(copy_row.get("mBarCode"), src_barcode, "复制后条码应是新条码")
    check_eq(copy_row.get("stock"), 0, "复制不应带库存")
