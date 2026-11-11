"""cases 包：导入即把用例注册进 framework.registry。

按**业务模块**分子包，每个模块内部再按**动作**拆文件：

    cases/unit/      多单位      TC-UNIT-*
    cases/depot/     仓库信息    TC-DEP-*
    cases/material/  商品信息    TC-MAT-*

找一条用例：先按编号前缀定模块，再按用例表的「标签」列定文件。
新增一个模块：照着 unit/ 抄一遍目录（含 api.py 与 __init__.py 的导入顺序说明）。

模块内的 api.py 必须最后导入 —— @api_case 只是往已登记的编号上挂实现，
标题/标签/优先级以 UI 层为准。这个顺序是语义不是风格，ruff 已豁免 I001。
"""

from cases import depot, material, unit  # noqa: F401
