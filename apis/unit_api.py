"""多单位接口封装（/jshERP-boot/unit/*）。

实测约定（2026-11-05）：
- 列表 GET /unit/list，search={"name":"","type":""}，field 省略时返回全字段；
- 新增 POST /unit/add，body={"basicUnit","otherUnit","ratio",...}；
  成功返回 {"code":200,"data":{"message":"成功"}}，**不回传 id**，需回查列表；
- 编辑 PUT /unit/update，body 需带完整对象（含 id / name / tenantId / deleteFlag）；
- 批量状态 POST /unit/batchSetStatus，body={"status":bool,"ids":"1,2,"}；
- 单删 DELETE /unit/delete?id=，批删 DELETE /unit/deleteBatch?ids=1,2,
"""

from __future__ import annotations

from apis.base import ApiBase

# 副单位字段后缀：第一个副单位没有后缀
_SUFFIX = ("", "Two", "Three")

# 编辑时回传的字段（与前端实际发出的 body 对齐）
_FIELDS = ("id", "name", "basicUnit", "otherUnit", "otherUnitTwo", "otherUnitThree",
           "ratio", "ratioTwo", "ratioThree", "enabled", "tenantId", "deleteFlag")


class UnitApi(ApiBase):
    LIST_PATH = "/unit/list"

    def _search(self, name="", type_=""):
        return {"name": name, "type": type_}

    # ---------- 查询 ----------
    def find(self, basic_unit):
        """按基本单位名精确回查一条（同名可能多条，取 createTime 倒序第一条）。"""
        rows = [r for r in self.all(name=basic_unit) if r.get("basicUnit") == basic_unit]
        return rows[0] if rows else None

    def find_all(self, basic_unit):
        return [r for r in self.all(name=basic_unit) if r.get("basicUnit") == basic_unit]

    # ---------- 新增 ----------
    @staticmethod
    def build_body(basic_unit=None, others=(), **extra):
        """组装新增请求体：others 形如 [("箱", 10), ("件", 100)]，最多三组。"""
        body = {}
        if basic_unit is not None:
            body["basicUnit"] = basic_unit
        for idx, item in enumerate(list(others)[:3]):
            unit, ratio = item
            suffix = _SUFFIX[idx]
            if unit is not None:
                body[f"otherUnit{suffix}"] = unit
            if ratio is not None:
                body[f"ratio{suffix}"] = ratio
        body.update(extra)
        return body

    def add_raw(self, body):
        """原样提交（校验类用例用它，不预设成功失败），返回 (业务码, 提示语)。"""
        return self.code_msg(self.c.call("POST", "/unit/add", body=body))

    def add_ok(self, body, label=""):
        """期望成功并回查 id，返回 (id, row)。"""
        self.c.ok("POST", "/unit/add", body=body, label=label or "新增多单位")
        basic = body.get("basicUnit")
        row = self.find(basic)
        return (row["id"] if row else None), row

    def create(self, basic_unit, others=(), **extra):
        return self.add_ok(self.build_body(basic_unit, others, **extra))

    # ---------- 编辑 ----------
    def update_raw(self, row, **changes):
        body = {k: row.get(k) for k in _FIELDS if k in row}
        body.update(changes)
        return self.code_msg(self.c.call("PUT", "/unit/update", body=body))

    def update_ok(self, row, **changes):
        return self.c.ok("PUT", "/unit/update", body={**{k: row.get(k) for k in _FIELDS if k in row},
                                                      **changes}, label="编辑多单位")

    # ---------- 状态 ----------
    def set_status(self, ids, enabled):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("POST", "/unit/batchSetStatus",
                           body={"status": bool(enabled), "ids": self.ids_param(ids)})

    def set_status_ok(self, ids, enabled):
        self.c.ok("POST", "/unit/batchSetStatus",
                  body={"status": bool(enabled), "ids": self.ids_param(
                      [ids] if isinstance(ids, int) else list(ids))}, label="批量状态")

    # ---------- 删除 ----------
    def delete(self, unit_id):
        return self.c.call("DELETE", "/unit/delete", {"id": unit_id})

    def delete_ok(self, unit_id):
        return self.c.ok("DELETE", "/unit/delete", {"id": unit_id}, label="删除多单位")

    def delete_batch(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("DELETE", "/unit/deleteBatch", {"ids": self.ids_param(ids)})

    def delete_batch_ok(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.ok("DELETE", "/unit/deleteBatch", {"ids": self.ids_param(ids)},
                         label="批量删除多单位")

    # ---------- 下拉联动 ----------
    def options(self, page=1, size=100):
        """商品页「多单位」下拉走的是 getAllList（简单数组）。"""
        return self.c.ok("GET", "/unit/getAllList", {"currentPage": page, "pageSize": size},
                         label="多单位下拉") or []
