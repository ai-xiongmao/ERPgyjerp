"""接口封装层（对标 pages/）：一个业务模块一个类，暴露「人话」级别的方法。

设计原则：
1. 用例只关心业务语义（add_unit / set_status / set_default），不拼 URL；
2. 返回原始 (status, body) 的方法用 `_raw` 后缀，期望成功的用 `ok` 语义；
3. 所有方法都记录到 client.calls，失败时能直接回放请求。
"""

from __future__ import annotations

import json


class ApiBase:
    LIST_PATH = ""
    MAX_PAGES = 20

    def __init__(self, client):
        self.c = client

    # ---------- 子类实现搜索条件 ----------
    def _search(self, **kwargs):
        raise NotImplementedError

    # ---------- 查询 ----------
    def list(self, page=1, size=10, column="createTime", order="desc", field="", **search):
        params = {
            "search": json.dumps(self._search(**search), ensure_ascii=False),
            "column": column, "order": order,
            "currentPage": page, "pageSize": size,
        }
        if field:
            params["field"] = field
        data = self.c.ok("GET", self.LIST_PATH, params, label=f"{self.LIST_PATH} 列表查询")
        return data or {"total": 0, "rows": []}

    def all(self, size=100, **search):
        """翻完所有页，返回行列表（用于断言「库里到底有没有」）。"""
        rows, page = [], 1
        while page <= self.MAX_PAGES:
            data = self.list(page=page, size=size, **search)
            chunk = data.get("rows") or []
            rows.extend(chunk)
            total = data.get("total") or 0
            if not chunk or len(rows) >= total:
                break
            page += 1
        return rows

    def count(self, **search):
        return self.list(page=1, size=1, **search).get("total", 0)

    # ---------- 通用断言 ----------
    @staticmethod
    def ids_param(ids):
        """接口要求的 ids 形态：'1,2,'（每个 id 后面都带逗号）。"""
        return "".join(f"{i}," for i in ids)

    @staticmethod
    def code_msg(result):
        """把 (HTTP status, body) 收敛成 (业务码, 提示语)。

        注意：jshERP 的业务失败也返回 HTTP 200，只看 HTTP 状态会全部误判为成功，
        因此这里必须以 body.code 为准（缺失时才退回 HTTP status）。
        """
        from framework.api_client import extract_message

        status, parsed = result
        code = parsed.get("code") if isinstance(parsed, dict) else None
        return (code if code is not None else status), extract_message(parsed)
