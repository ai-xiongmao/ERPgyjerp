"""多单位（商品管理 → 多单位，/system/unit）：UI 层 + 接口层。

文件按**动作**划分，与用例表的「标签」列对应：
    entry       页面入口            list_view   列表展示
    query       查询                create      新增
    edit        编辑 / 复制         status      启用 / 禁用
    delete      删除                linkage     跨模块联动
    exception   异常 / 权限         api         接口层实现

新增用例文件后必须在这里 import，否则不会被 registry 收集。
"""

from cases.unit import (  # noqa: F401
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
    # 标题/标签/优先级以 UI 层为准（见 framework/registry.py）。改动这行前先读那段注释。
    api,
)
