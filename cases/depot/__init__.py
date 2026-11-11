"""仓库信息（基础资料 → 仓库信息，/system/depot）：UI 层 + 接口层。

文件按**动作**划分，与用例表的「标签」列对应：
    entry       页面入口            list_view   列表展示
    query       查询                create      新增
    edit        编辑                status      启用 / 禁用
    delete      删除                linkage     商品联动（设为默认 / 默认唯一性）
    exception   异常 / 权限         api         接口层实现

新增用例文件后必须在这里 import，否则不会被 registry 收集。
"""

from cases.depot import (  # noqa: F401
    entry,
    list_view,
    query,
    create,
    edit,
    status,
    delete,
    linkage,
    exception,
    # api 必须最后导入：@api_case 只是往已登记的编号上挂接口实现，
    # 标题/标签/优先级以 UI 层为准（见 framework/registry.py）。
    api,
)
