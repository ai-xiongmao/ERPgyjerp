"""接口执行上下文：接口用例拿到的「工具箱」，接口版 Context。

与 framework/context.py 的区别：
- 不持有 page，全程走 HTTP，一条用例通常 <1s（UI 版要 15~30s）；
- 造数据同样遵守前缀纪律：先记账再落库，跑完按前缀回收，且回收前校验名字含前缀；
- 提供 note()，接口层的偏差/缺陷候选照样进报告。
"""

from __future__ import annotations

from apis.depot_api import DepotApi
from apis.material_api import MaterialApi
from apis.unit_api import UnitApi
from framework.api_client import ApiClient
from framework.data import TestData


class ApiContext:
    def __init__(self, client=None, data=None, log=print):
        self.client = client or ApiClient()
        self.data = data or TestData()
        self.unit = UnitApi(self.client)
        self.depot = DepotApi(self.client)
        self.material = MaterialApi(self.client)
        self.notes = []
        self.page = None          # 接口层没有页面；保留属性是为了让共用代码不炸
        self.created = []         # [[kind, name, id]]，id 在落库后回填
        self._log = log

    # ---------- 日志 / 记录 ----------
    def log(self, message):
        self._log(f"        {message}")

    def note(self, message):
        self.notes.append(str(message))
        self._log(f"        · {message}")

    # ---------- 造数据 ----------
    def _track(self, kind, name):
        """先记账再落库：即使创建失败或后续把名字改坏，也能按 id 精确回收。"""
        entry = [kind, name, None]
        self.created.append(entry)
        return entry

    def new_unit(self, others=(("箱", 10),), basic=None, kind="U"):
        """造一条多单位，返回 (id, 基本单位名, 行)。"""
        basic = basic or self.data.name(kind)[:10]
        entry = self._track("unit", basic)
        unit_id, row = self.unit.create(basic, others)
        entry[2] = unit_id
        return unit_id, basic, row

    def new_depot(self, name=None, kind="D", **fields):
        name = name or self.data.depot_name(kind)
        entry = self._track("depot", name)
        depot_id, row = self.depot.create(name, **fields)
        entry[2] = depot_id
        return depot_id, name, row

    def new_material(self, name=None, unit="个", kind="M", bar_code=None, **extra):
        name = name or self.data.material_name(kind)
        entry = self._track("material", name)
        material_id, row = self.material.create(name, unit, bar_code=bar_code, **extra)
        entry[2] = material_id
        return material_id, name, row
    # ---------- 收尾 ----------
    def reset(self):
        """接口层没有页面状态需要复位，保留空实现让 runner 可以统一调用。"""
        return None

    def cleanup(self):
        """回收本次造的数据。

        优先按 id 精确删（用例可能把名称/基本单位改坏，按名字根本搜不到）；
        再按运行前缀兜底扫一遍。任何删除都不碰本次前缀之外的记录。
        """
        if not self.created:
            return 0
        token = self.data.token
        removed = 0
        by_kind = {"unit": [], "depot": [], "material": []}
        for kind, _name, rid in self.created:
            if rid:
                by_kind.setdefault(kind, []).append(rid)

        # 1) 按 id 精确删
        for rid in by_kind["unit"]:
            try:
                self.unit.delete(rid)
                removed += 1
            except Exception as exc:  # noqa: BLE001 - 已删过的会报错，忽略
                self.log(f"回收多单位 id={rid} 失败：{type(exc).__name__}")
        for kind in ("depot", "material"):
            ids = by_kind[kind]
            if not ids:
                continue
            api = self.depot if kind == "depot" else self.material
            try:
                api.delete_batch(ids)
                removed += len(ids)
            except Exception as exc:  # noqa: BLE001
                self.log(f"回收 {kind} 失败：{type(exc).__name__}: {exc}")

        # 2) 按前缀兜底（覆盖创建成功但当时没拿到 id 的情况）
        try:
            rows = [r for r in self.unit.all(name=token)
                    if token in str(r.get("basicUnit") or "") or token in str(r.get("name") or "")]
            for r in rows:
                self.unit.delete(r["id"])
                removed += 1
        except Exception as exc:  # noqa: BLE001
            self.log(f"按前缀回收多单位失败：{type(exc).__name__}: {exc}")
        for kind, api, key in (("depot", self.depot, "name"), ("material", self.material, "keyword")):
            try:
                rows = [r for r in api.all(**{key: token}) if token in str(r.get("name") or "")]
                if rows:
                    api.delete_batch([r["id"] for r in rows])
                    removed += len(rows)
            except Exception as exc:  # noqa: BLE001
                self.log(f"按前缀回收 {kind} 失败：{type(exc).__name__}: {exc}")
        # 回收完就清账，避免下一次 cleanup 重复删除已删的 id（计数虚高）
        self.created.clear()
        return removed

    def __str__(self):
        return f"ApiContext({self.data})"
