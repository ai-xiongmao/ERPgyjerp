"""测试数据工厂。

数据纪律（务必保持）：
1. 本次运行的所有名字都带同一个运行前缀（`AT` + 4 位 36 进制时间片，共 6 字符），
   因此「同一脚本反复跑」不会撞名，跑完也能按前缀精确回收；
2. 基本单位输入框限制 1~10 个字符，所以名字统一 9 字符：
   `<运行前缀><类型位><2 位序号>`，例如 ATK3F9U01；
3. 只清理「自己造的数据」，绝不按关键字批量删既有业务数据——
   `pages.unit_page.cleanup_contains` 里还会再校验一遍名字里是否含本次前缀。
"""

import time

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base36(number, width=4):
    digits = ""
    while number:
        number, rem = divmod(number, 36)
        digits = _ALPHABET[rem] + digits
    return (digits or "0").rjust(width, "0")[-width:]


class TestData:
    """生成并记住本次运行用到的测试数据。"""

    def __init__(self, run_id=None):
        self.run_id = run_id or "AT" + _base36(int(time.time()) % (36 ** 4))
        self._seq = 0
        self._created = []      # [(基本单位, 副单位列表)]
        self._materials = []    # [商品名称]

    # ---------- 命名 ----------
    def name(self, kind="U"):
        """生成一个 9 字符的基本单位名（kind 用于区分角色：U 被测 / Z 副单位）。"""
        self._seq += 1
        return f"{self.run_id}{kind}{self._seq:02d}"

    def material_name(self, kind="M"):
        """生成一个商品名称（名称字段无 10 字符限制，仍带运行前缀便于回收）。"""
        self._seq += 1
        return f"{self.run_id}{kind}{self._seq:02d}"

    @property
    def token(self):
        """本次运行的关键字，可用于模糊查询 / 清理。"""
        return self.run_id

    # ---------- 记账 ----------
    def track(self, basic, others=()):
        self._created.append((basic, list(others)))
        return basic

    def track_material(self, name):
        """记账一条商品名称，跑完按前缀回收。"""
        self._materials.append(name)
        return name

    @property
    def created(self):
        return list(self._created)

    @property
    def materials(self):
        return list(self._materials)

    @property
    def has_material(self):
        return bool(self._materials)

    def unmatched_names(self):
        """记账里「不含运行前缀」的名字——按前缀搜不到，需要按名字精确回收。"""
        return [basic for basic, _ in self._created if basic and self.run_id not in basic]

    def __str__(self):
        return f"TestData(run_id={self.run_id}, 已创建 {len(self._created)} 条)"
