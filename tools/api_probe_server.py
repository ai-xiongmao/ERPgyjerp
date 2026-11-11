"""服务端行为探测：把边界请求直接打到后端，看它到底校验到什么程度。

UI 上的红色提示有可能是前端拦的，接口层未必校验——这个脚本就是为了把
「服务端真实口径」摸清楚，接口用例的预期结果以此为准。

只用测试前缀 ATZ9 造数据，结尾按 id 删除。
输出：tools/api_dump/server_behavior.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from framework.api_client import ApiClient  # noqa: E402

PFX = "ATZ9"
RESULTS = []
CLEANUP = []   # [(kind, id)]


def rec(label, method, path, params=None, body=None, note=""):
    status, parsed = client.call(method, path, params, body)
    code = parsed.get("code") if isinstance(parsed, dict) else None
    msg = parsed.get("message") if isinstance(parsed, dict) else None
    RESULTS.append({
        "label": label, "method": method, "path": path,
        "params": params, "body": body, "status": status,
        "code": code, "message": msg, "note": note,
        "resp": json.dumps(parsed, ensure_ascii=False)[:400],
    })
    flag = "OK " if (status == 200 and code == 200) else "REJ"
    print(f"  {flag} {label:<34} status={status} code={code} msg={msg}")
    return status, parsed


def _note_query_error(label, path, params, exc):
    RESULTS.append({"label": label, "method": "GET", "path": path, "params": params,
                    "body": None, "status": 0, "code": None,
                    "message": f"查询异常：{exc}", "note": "查询接口报错", "resp": str(exc)[:300]})
    print(f"  ERR {label:<34} 查询异常：{str(exc)[:90]}")


def find_unit(name):
    params = {"search": json.dumps({"name": name, "type": ""}),
              "column": "createTime", "order": "desc",
              "field": "id,name,basicUnit,otherUnit,enabled", "currentPage": 1, "pageSize": 50}
    try:
        data = client.ok("GET", "/unit/list", params)
    except Exception as exc:  # noqa: BLE001 - 查询本身可能报错，不能中断整轮
        _note_query_error(f"查询「{name[:10]}」", "/unit/list", params, exc)
        return None
    for r in (data or {}).get("rows", []):
        if name in (r.get("basicUnit") or "") or name in (r.get("name") or ""):
            return r
    return None


def find_depot(name):
    params = {"search": json.dumps({"name": name, "remark": ""}),
              "column": "createTime", "order": "desc",
              "field": "id,name,address,enabled,isDefault", "currentPage": 1, "pageSize": 50}
    try:
        data = client.ok("GET", "/depot/list", params)
    except Exception as exc:  # noqa: BLE001
        _note_query_error(f"查询仓库「{name[:10]}」", "/depot/list", params, exc)
        return None
    for r in (data or {}).get("rows", []):
        if r.get("name") == name:
            return r
    return None


def find_material(name):
    params = {"search": json.dumps({"materialParam": name}),
              "column": "createTime", "order": "desc",
              "field": "id,name,unit,mBarCode,enabled", "currentPage": 1, "pageSize": 50}
    try:
        data = client.ok("GET", "/material/list", params)
    except Exception as exc:  # noqa: BLE001
        _note_query_error(f"查询商品「{name[:10]}」", "/material/list", params, exc)
        return None
    for r in (data or {}).get("rows", []):
        if r.get("name") == name:
            return r
    return None


client = ApiClient()

print("[多单位] 新增校验")
rec("缺副单位", "POST", "/unit/add", body={"basicUnit": PFX + "U01"})
# 服务端若不校验基本单位必填，会落一条 basicUnit=null 的脏数据，立刻按特征回收
_st, _p = rec("缺基本单位", "POST", "/unit/add", body={"otherUnit": "箱", "ratio": "10"})
if isinstance(_p, dict) and _p.get("code") == 200:
    allunits = client.ok("GET", "/unit/getAllList", {"currentPage": 1, "pageSize": 200}) or []
    for r in allunits:
        if not r.get("basicUnit"):
            client.call("DELETE", "/unit/delete", {"id": r["id"]})
            print(f"    （已回收 basicUnit 为空的脏数据 id={r['id']}）")
rec("缺比例", "POST", "/unit/add", body={"basicUnit": PFX + "U02", "otherUnit": "箱"})
rec("比例非数字", "POST", "/unit/add", body={"basicUnit": PFX + "U03", "otherUnit": "箱", "ratio": "abc"})
rec("比例=0", "POST", "/unit/add", body={"basicUnit": PFX + "U04", "otherUnit": "箱", "ratio": "0"})
rec("比例四位小数", "POST", "/unit/add", body={"basicUnit": PFX + "U05", "otherUnit": "箱", "ratio": "1.2345"})
rec("比例超大值", "POST", "/unit/add", body={"basicUnit": PFX + "U06", "otherUnit": "箱", "ratio": "99999999"})
rec("基本单位超长20字", "POST", "/unit/add",
    body={"basicUnit": PFX + "U" + "超" * 18, "otherUnit": "箱", "ratio": "10"})
rec("基本单位含emoji", "POST", "/unit/add", body={"basicUnit": PFX + "U😀", "otherUnit": "箱", "ratio": "10"})
rec("空请求体", "POST", "/unit/add", body={})
rec("正常新增A", "POST", "/unit/add", body={"basicUnit": PFX + "UA", "otherUnit": "箱", "ratio": "10"})
rec("重名再新增（允许？）", "POST", "/unit/add", body={"basicUnit": PFX + "UA", "otherUnit": "箱", "ratio": "10"})
rec("更新不存在id", "PUT", "/unit/update", body={"id": 999999999, "basicUnit": PFX + "UX",
                                                "otherUnit": "箱", "ratio": "2"})
rec("删除不存在id", "DELETE", "/unit/delete", params={"id": 999999999})

for n in [PFX + "U01", PFX + "U02", PFX + "U03", PFX + "U04", PFX + "U05", PFX + "U06",
          PFX + "UA", PFX + "U" + "超" * 18, PFX + "U😀"]:
    r = find_unit(n)
    if r:
        CLEANUP.append(("unit", r["id"]))
        if r["basicUnit"] == n:
            rec(f"回查到「{n[:12]}」", "GET", "/unit/list",
                params={"search": json.dumps({"name": n, "type": ""}), "currentPage": 1,
                        "pageSize": 5}, note=f"id={r['id']} name={r.get('name')}")

print("\n[仓库] 新增校验")
rec("缺名称", "POST", "/depot/add", body={"address": "x"})
rec("空请求体", "POST", "/depot/add", body={})
rec("名称重复", "POST", "/depot/add", body={"name": PFX + "DA"})
rec("正常新增A", "POST", "/depot/add", body={"name": PFX + "DA", "address": "地址"})
rec("名称重复再新增", "POST", "/depot/add", body={"name": PFX + "DA"})
rec("名称超长", "POST", "/depot/add", body={"name": PFX + "D" + "超" * 60})
rec("仓储费非数字", "POST", "/depot/add", body={"name": PFX + "DB", "warehousing": "abc"})
rec("设为默认-不存在id", "POST", "/depot/updateIsDefault", body={"id": 999999999})
rec("批量状态-空ids", "POST", "/depot/batchSetStatus", body={"status": False, "ids": ""})
rec("名称查重接口-已存在", "GET", "/depot/checkIsNameExist", params={"name": PFX + "DA", "id": 0})

for n in [PFX + "DA", PFX + "D" + "超" * 60, PFX + "DB"]:
    r = find_depot(n)
    if r:
        CLEANUP.append(("depot", r["id"]))

print("\n[商品] 新增校验")
rec("缺名称", "POST", "/material/add", body={"unit": "个"})
rec("缺单位", "POST", "/material/add", body={"name": PFX + "MA"})
rec("空请求体", "POST", "/material/add", body={})
rec("正常新增", "POST", "/material/add", body={
    "name": PFX + "MA", "unit": "个", "mnemonic": PFX + "MA",
    "meList": [{"id": "1", "barCode": "9900" + PFX[-3:], "commodityUnit": "个",
                "sku": "", "purchaseDecimal": "", "commodityDecimal": "",
                "wholesaleDecimal": "", "lowDecimal": ""}],
    "stock": [], "sortList": [], "unitId": "", "imgName": "", "meDeleteIdList": []})
rec("同名同规格再新增", "POST", "/material/add", body={
    "name": PFX + "MA", "unit": "个", "mnemonic": PFX + "MA",
    "meList": [{"id": "2", "barCode": "9901" + PFX[-3:], "commodityUnit": "个",
                "sku": "", "purchaseDecimal": "", "commodityDecimal": "",
                "wholesaleDecimal": "", "lowDecimal": ""}],
    "stock": [], "sortList": [], "unitId": "", "imgName": "", "meDeleteIdList": []})
rec("查重接口", "GET", "/material/checkIsExist",
    params={"id": 0, "name": PFX + "MA", "model": "", "color": "", "standard": "",
            "mfrs": "", "otherField1": "", "otherField2": "", "otherField3": "",
            "unit": "个", "unitId": ""})
rec("条码查重", "GET", "/materialsExtend/checkIsBarCodeExist",
    params={"barCode": "9900" + PFX[-3:], "id": 0})
rec("批量状态-空ids", "POST", "/material/batchSetStatus", body={"status": False, "ids": ""})

r = find_material(PFX + "MA")
if r:
    CLEANUP.append(("material", r["id"]))

print("\n[清理]")
for kind, rid in CLEANUP:
    path = {"unit": "/unit/delete", "depot": "/depot/deleteBatch",
            "material": "/material/deleteBatch"}[kind]
    try:
        if kind == "unit":
            status, parsed = client.call("DELETE", path, {"id": rid})
        else:
            status, parsed = client.call("DELETE", path, {"ids": f"{rid},"})
        print(f"  删除 {kind} id={rid} → status={status} {parsed.get('code') if isinstance(parsed, dict) else parsed}")
    except Exception as exc:  # noqa: BLE001
        print(f"  删除 {kind} id={rid} 失败：{exc}")

out = HERE / "api_dump" / "server_behavior.md"
out.parent.mkdir(parents=True, exist_ok=True)
lines = [f"# 服务端校验行为实测（{datetime.now():%Y-%m-%d %H:%M}）", ""]
for r in RESULTS:
    lines += [f"## {r['label']}", "",
              f"- `{r['method']} {r['path']}`",
              f"- 请求：`{json.dumps(r['body'] or r['params'], ensure_ascii=False)}`",
              f"- 响应：HTTP {r['status']} / code={r['code']} / message=`{r['message']}`",
              f"- 原文：`{r['resp']}`", ""]
out.write_text("\n".join(lines), encoding="utf-8")
print(f"\n结果：{out}")

# 自检：清理后不应残留
left = [n for n in [PFX + "UA", PFX + "DA", PFX + "MA"] if (find_unit(n) or find_depot(n) or find_material(n))]
print("残留检查：", left or "无残留")
