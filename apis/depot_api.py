"""仓库接口封装（/jshERP-boot/depot/*）。

实测约定（2026-11-05）：
- 列表 GET /depot/list，search={"name","remark"}；
- 新增 POST /depot/add，body={"name","address","warehousing","truckage","sort","remark","principal"}，
  成功不回传 id，需回查；
- 编辑 PUT /depot/update，body 需带完整对象；
- 批量状态 POST /depot/batchSetStatus，body={"status":bool,"ids":"1,2,"}；
- 设为默认 POST /depot/updateIsDefault，body={"id":...}；
- 批删 DELETE /depot/deleteBatch?ids=1,2,
- 名称查重 GET /depot/checkIsNameExist?name=&id=
"""

from __future__ import annotations

from apis.base import ApiBase

_FIELDS = ("id", "name", "address", "warehousing", "truckage", "type", "sort", "remark",
           "principal", "enabled", "tenantId", "deleteFlag", "isDefault",
           "principalName", "initStock", "currentStock", "lowSafeStock", "highSafeStock")


class DepotApi(ApiBase):
    LIST_PATH = "/depot/list"

    def _search(self, name="", remark=""):
        return {"name": name, "remark": remark}

    # ---------- 查询 ----------
    def find(self, name):
        rows = [r for r in self.all(name=name) if r.get("name") == name]
        return rows[0] if rows else None

    def find_all(self, name):
        return [r for r in self.all(name=name) if r.get("name") == name]

    def default_depot(self):
        rows = [r for r in self.all() if r.get("isDefault") in (True, "1", 1)]
        return rows[0] if rows else None

    def with_stock(self, m_id=0):
        return self.c.ok("GET", "/depot/getAllListWithStock", {"mId": m_id}, label="仓库下拉") or []

    # ---------- 新增 ----------
    def add_raw(self, body):
        return self.code_msg(self.c.call("POST", "/depot/add", body=body))

    def add_ok(self, body, label=""):
        self.c.ok("POST", "/depot/add", body=body, label=label or "新增仓库")
        row = self.find(body.get("name"))
        return (row["id"] if row else None), row

    def create(self, name, **fields):
        body = {"name": name}
        body.update({k: v for k, v in fields.items() if v is not None})
        return self.add_ok(body)

    # ---------- 编辑 ----------
    def update_raw(self, row, **changes):
        body = {k: row.get(k) for k in _FIELDS if k in row}
        body.update(changes)
        return self.code_msg(self.c.call("PUT", "/depot/update", body=body))

    def update_ok(self, row, **changes):
        body = {k: row.get(k) for k in _FIELDS if k in row}
        body.update(changes)
        return self.c.ok("PUT", "/depot/update", body=body, label="编辑仓库")

    # ---------- 状态 / 默认 ----------
    def set_status(self, ids, enabled):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("POST", "/depot/batchSetStatus",
                           body={"status": bool(enabled), "ids": self.ids_param(ids)})

    def set_status_ok(self, ids, enabled):
        ids = [ids] if isinstance(ids, int) else list(ids)
        self.c.ok("POST", "/depot/batchSetStatus",
                  body={"status": bool(enabled), "ids": self.ids_param(ids)}, label="仓库批量状态")

    def set_default(self, depot_id):
        return self.c.call("POST", "/depot/updateIsDefault", body={"id": depot_id})

    def set_default_ok(self, depot_id):
        return self.c.ok("POST", "/depot/updateIsDefault", body={"id": depot_id}, label="设为默认")

    # ---------- 删除 ----------
    def delete_batch(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.call("DELETE", "/depot/deleteBatch", {"ids": self.ids_param(ids)})

    def delete_batch_ok(self, ids):
        ids = [ids] if isinstance(ids, int) else list(ids)
        return self.c.ok("DELETE", "/depot/deleteBatch", {"ids": self.ids_param(ids)},
                         label="删除仓库")

    # ---------- 查重 ----------
    def check_name_exist(self, name, depot_id=0):
        return self.c.call("GET", "/depot/checkIsNameExist", {"name": name, "id": depot_id})
