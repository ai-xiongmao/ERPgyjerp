"""商品信息（商品管理 → 商品信息，/material/material）：UI 层 + 接口层。

文件按**动作**划分，与用例表的「标签」列对应：
    entry       页面入口            list_view   列表展示
    query       查询                create      新增
    edit        编辑 / 复制         status      启用 / 禁用
    delete      删除                exception   异常 / 权限

没有 linkage.py：商品是多单位的**下游**，联动用例记在 cases/unit/linkage.py 里。

新增用例文件后必须在这里 import，否则不会被 registry 收集。
"""

from cases.material import (  # noqa: F401
    entry,
    list_view,
    query,
    create,
    edit,
    status,
    delete,
    exception,
    # api 必须最后导入：@api_case 只是往已登记的编号上挂接口实现，
    # 标题/标签/优先级以 UI 层为准（见 framework/registry.py）。
    api,
)
