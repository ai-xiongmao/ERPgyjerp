"""商品接口封装（/jshERP-boot/material/*）。

实测约定（2026-11-05）：
- 列表 GET /material/list，search 是一大坨（materialParam 是关键词，其余是高级查询）；
  不传 field 时返回 53 个字段，编辑所需的完整对象直接从列表行取；
- 新增 POST /material/add，body 必带 meList（条码明细，至少一条），否则商品没有条码；
- 编辑 PUT /material/update，body 是完整对象（含 id/tenantId/deleteFlag/attribute 等）；
- 批量状态 POST /material/batchSetStatus，body={"status":bool,"ids":"1,2,"}；
- 批删 DELETE /material/deleteBatch?ids=1,2,
- 条码：GET /material/getMaxBarCode 取下一个可用条码；
- 查重：GET /material/checkIsExist?...、GET /materialsExtend/checkIsBarCodeExist?barCode=&id=
"""

from __future__ import annotations

import random
import string
import time

from apis.base import ApiBase

# 列表默认搜索条件（照抄前端的字段集，少一个都可能被当成高级查询炸掉）
DEFAULT_SEARCH = {
    "materialParam": "", "standard": "", "model": "", "color": "", "brand": "",
    "mfrs": "", "otherField1": "", "otherField2": "", "otherField3": "",
    "weight": "", "expiryNum": "", "position": "", "remark": "",
    "mpList": "扩展1,扩展2,扩展3",
}

# 编辑时回传的字段（与前端 update 请求体一致）
_FIELDS = ("id", "categoryId", "name", "mfrs", "model", "standard", "brand", "mnemonic",
           "color", "unit", "remark", "imgName", "unitId", "expiryNum", "weight", "enabled",
           "otherField1", "otherField2", "otherField3", "enableSerialNumber",
           "enableBatchNumber", "position", "attribute", "tenantId", "deleteFlag",
           "unitName", "ratio", "categoryName", "materialOther", "stock",
           "purchaseDecimal", "commodityDecimal", "wholesaleDecimal", "lowDecimal",
           "billPrice", "mBarCode")


def _random_id():
    """前端 meList 里的 id 是 20 位随机数字，这里照做。"""
    return "".join(random.choices(string.digits, k=20))


def _num_text(value):
    """明细里的价格字段前端按字符串回传，None 传空串。"""
    return "" if value is None else str(value)


class MaterialApi(ApiBase):
    LIST_PATH = "/material/list"

    def _search(self, keyword="", **overrides):
        search = dict(DEFAULT_SEARCH)
        search["materialParam"] = keyword
        search.update({k: v for k, v in overrides.items() if v is not None})
        return search

    # ---------- 查询 ----------
    def find(self, name, page_size=100):
        rows = [r for r in self.all(keyword=name) if r.get("name") == name]
        if not rows:
            return None
        # 同名多条时按 id 倒序取最新
        return sorted(rows, key=lambda r: r.get("id") or 0, reverse=True)[0]

    def find_all(self, name):
        return [r for r in self.all(keyword=name) if r.get("name") == name]

    # ---------- 新增 ----------
    def next_barcode(self):
        """取一个可用条码。

        注意：`getMaxBarCode` 返回的是**当前最大条码**（不是下一个），
        前端自己 +1 后提交；这里同样 +1，并用查重接口跳过已被占用的号段。
        """
        data = self.c.ok("GET", "/material/getMaxBarCode", label="取最大条码") or {}
        raw = str(data.get("barCode") or "0")
        try:
            number = int(raw) + 1
        except ValueError:
            return raw
        for _ in range(50):
            code = str(number)
            status, body = self.check_barcode_exist(code, 0)
            exists = bool((body.get("data") or {}).get("status")) if isinstance(body.get("data"), dict) else False
            if status == 200 and not exists:
                return code
            number += 1
        return str(number)

    @staticmethod
    def build_body(name=None, unit=None, bar_code=None, mnemonic=None, **extra):
        body = {}
        if name is not None:
            body["name"] = name
            body["mnemonic"] = mnemonic if mnemonic is not None else name
        if unit is not None:
            body["unit"] = unit
        me = {
            "id": _random_id(),
            "barCode": bar_code or "",
            "commodityUnit": unit or "",
            "sku": "", "purchaseDecimal": "", "commodityDecimal": "",
            "wholesaleDecimal": "", "lowDecimal": "",
        }
        body["meList"] = [me]
        body.update({"stock": [], "sortList": [], "unitId": "", "imgName": "",
                     "meDeleteIdList": []})
        body.update(extra)
        return body

    def add_raw(self, body):
        return self.code_msg(self.c.call("POST", "/material/add", body=body))

    def add_ok(self, body, label=""):
        self.c.ok("POST", "/material/add", body=body, label=label or "新增商品")
        row = self.find(body.get("name"))
        return (row["id"] if row else None), row

    def create(self, name, unit="个", bar_code=None, **extra):
        """新增一条商品；不传条码时自动取系统下一个条码。"""
        if bar_code is None:
            bar_code = self.next_barcode()
        body = self.build_body(name, unit, bar_code, **extra)
        return self.add_ok(body)

    # ---------- 编辑 ----------
    def _update_body(self, row, **changes):
        """组装编辑 body：照抄列表行的全部字段，再把 stock 改成前端形态（数组）。

        只挑部分字段回传会被后端判「数据写入异常」（301），必须整对象回传。
        """
        body = {k: v for k, v in row.items() if k not in ("meList", "sortList", "meDeleteIdList")}
        if not isinstance(body.get("stock"), list):
            body["stock"] = []
        body.update(changes)
        if "meList" not in body:
            details = self.barcode_details(row.get("id"))
            body["meList"] = [{
                "id": str(d.get("id")),
                "barCode": d.get("barCode") or "",
                "commodityUnit": d.get("commodityUnit") or row.get("unit") or "",
                "sku": d.get("sku") or "",
                "purchaseDecimal": _num_text(d.get("purchaseDecimal")),
                "commodityDecimal": _num_text(d.get("commodityDecimal")),
                "wholesaleDecimal": _num_text(d.get("wholesaleDecimal")),
                "lowDecimal": _num_text(d.get("lowDecimal")),
            } for d in details]
        body.setdefault("sortList", [])
        body.setdefault("meDeleteIdList", [])
        return body

    def update_raw(self, row, **changes):
        return self.code_msg(
            self.c.call("PUT", "/material/update", body=self._update_body(row, **changes)))

    def update_ok(self, row, **changes):
        return self.c.ok("PUT", "/material/update", body=self._update_body(row, **changes),
                         label="编辑商品")

    # ---------- 状态 ----------
    def set_status(self, ids, enabled):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("POST", "/material/batchSetStatus",
                           body={"status": bool(enabled), "ids": self.ids_param(ids)})

    def set_status_ok(self, ids, enabled):
        ids = [ids] if isinstance(ids, int) else list(ids)
        self.c.ok("POST", "/material/batchSetStatus",
                  body={"status": bool(enabled), "ids": self.ids_param(ids)}, label="商品批量状态")

    # ---------- 删除 ----------
    def delete_batch(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("DELETE", "/material/deleteBatch", {"ids": self.ids_param(ids)})

    def delete_batch_ok(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.ok("DELETE", "/material/deleteBatch", {"ids": self.ids_param(ids)},
                         label="删除商品")

    # ---------- 查重 / 条码 ----------
    def check_exist(self, name, unit="个", model="", color="", standard="",
                    mfrs="", material_id=0, unit_id=""):
        return self.c.call("GET", "/material/checkIsExist", {
            "id": material_id, "name": name, "model": model, "color": color,
            "standard": standard, "mfrs": mfrs, "otherField1": "", "otherField2": "",
            "otherField3": "", "unit": unit, "unitId": unit_id})

    def check_barcode_exist(self, bar_code, material_id=0):
        return self.c.call("GET", "/materialsExtend/checkIsBarCodeExist",
                           {"barCode": bar_code, "id": material_id})

    def barcode_details(self, material_id):
        data = self.c.ok("GET", "/materialsExtend/getDetailList", {"materialId": material_id},
                         label="条码明细") or {}
        return data.get("rows") or [] if isinstance(data, dict) else (data or [])

    def pinyin(self, name):
        return self.c.call("POST", "/material/changeNameToPinYin", body={"name": name})

    # ---------- 下拉 ----------
    def categories(self):
        return self.c.ok("GET", "/materialCategory/getMaterialCategoryTree", {"id": ""},
                         label="商品类别树") or []

    def attributes(self):
        return self.c.ok("GET", "/materialAttribute/getNameList", label="商品属性") or []
