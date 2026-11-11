"""执行上下文：用例函数拿到的「工具箱」。

用例只和 ctx 打交道：
    ctx.new_unit(...)   造数据（自动记账，跑完回收）
    ctx.unit / ctx.product  页面对象
    ctx.note(...)       记录偏差、缺陷候选等观察结论（进报告，不影响通过与否）
"""

from config import BASE_URL, UNIT_PATH
from framework.browser import SessionExpiredError
from framework.data import TestData
from pages.depot_page import DepotPage
from pages.product_page import ProductPage
from pages.unit_page import UnitPage


class Context:
    def __init__(self, page, data=None, log=print):
        self.page = page
        self.data = data or TestData()
        self.unit = UnitPage(page)
        self.product = ProductPage(page)
        self.depot = DepotPage(page)
        self.notes = []
        self._log = log

    # ---------- 日志 / 记录 ----------
    def log(self, message):
        self._log(f"        {message}")

    def note(self, message):
        """记录观察结论（偏差 / 缺陷候选 / 数据约定），只进报告不判失败。"""
        self.notes.append(str(message))
        self._log(f"        · {message}")

    # ---------- 页面 ----------
    def open_unit(self):
        return self.unit.open()

    def open_product(self):
        return self.product.open()

    def open_depot(self):
        return self.depot.open()

    # ---------- 数据 ----------
    def new_unit(self, others=(), basic=None, kind="U"):
        """造一条多单位数据并记账，返回基本单位名。

        先记账再落库：即使创建过程中途失败（例如校验不通过），
        收尾时也会去把这半个数据清掉。
        """
        basic = basic or self.data.name(kind)
        self.data.track(basic, others)
        self.open_unit()
        self.unit.create(basic, others)
        return basic

    def new_material(self, name=None, unit="个", kind="M"):
        """造一条商品并记账，返回商品名称（条码由系统自动生成）。"""
        name = name or self.data.material_name(kind)
        self.data.track_material(name)
        self.open_product()
        self.product.create(name, unit)
        return name

    def new_depot(self, name=None, address=None, warehousing=None,
                  truckage=None, sort=None, remark=None, kind="D"):
        """造一条仓库并记账，返回仓库名称。"""
        name = name or self.data.depot_name(kind)
        self.data.track_depot(name)
        self.open_depot()
        self.depot.create(name, address, warehousing, truckage, sort, remark)
        return name

    # ---------- 收尾 ----------
    def _current_page(self):
        """判断当前停在哪个业务页面：返回 'product' / 'depot' / 'unit'。"""
        url = self.page.url or ""
        if "/material/material" in url:
            return "product"
        if "/system/depot" in url:
            return "depot"
        return "unit"

    def reset(self):
        """把页面恢复到干净状态：关浮层、清勾选、清查询条件。

        根据当前页面选择对应的页面对象做收尾，不强制跳转——
        用例结束后若被导航回其他页面，会让对应页面对象的清理找不到查询框。
        """
        try:
            current = self._current_page()
            if current == "product":
                self.product.close_overlays()
                self.product.clear_selection()
                self.product.reset()
            elif current == "depot":
                self.depot.close_overlays()
                self.depot.clear_selection()
                self.depot.reset()
            else:
                if UNIT_PATH not in (self.page.url or ""):
                    self.page.goto(BASE_URL + UNIT_PATH, wait_until="domcontentloaded")
                    self.page.wait_for_timeout(500)
                self.unit.close_overlays()
                self.unit.clear_selection()
                self.unit.reset()
                # 分页状态要归位：某些用例会切每页条数/翻页，留着会污染下一条用例
                info = self.unit.pagination_info()
                if info.get("pageSize") not in (None, 10):
                    self.unit.set_page_size(10)
                if info.get("current") not in (None, 1):
                    self.unit.goto_page(1)
        except SessionExpiredError:
            raise
        except Exception:  # noqa: BLE001 - 收尾失败不能盖住用例本身的失败
            pass

    def cleanup(self):
        """回收本次运行造的数据（多单位 + 商品 + 仓库）。

        按运行前缀模糊回收（覆盖绝大多数）；没有造过数据就直接返回。
        """
        if not self.data.created and not self.data.materials and not self.data.depots:
            return 0
        removed = 0
        try:
            if self.data.created:
                self.open_unit()  # 确保停在多单位页，清理才找得到查询框
                removed += self.unit.cleanup_contains(self.data.token)
                for name in self.data.unmatched_names():
                    removed += self.unit.cleanup_names([name])
        except SessionExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log(f"清理多单位残留失败：{type(exc).__name__}: {exc}")
        try:
            if self.data.materials:
                self.open_product()  # 确保停在商品页，清理才找得到查询框
                removed += self.product.cleanup_contains(self.data.token)
        except SessionExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log(f"清理商品残留失败：{type(exc).__name__}: {exc}")
        try:
            if self.data.depots:
                self.open_depot()  # 确保停在仓库页，清理才找得到查询框
                removed += self.depot.cleanup_contains(self.data.token)
        except SessionExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log(f"清理仓库残留失败：{type(exc).__name__}: {exc}")
        return removed
