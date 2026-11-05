"""cases 包：导入即把用例注册进 framework.registry。

新增用例文件后记得在这里加一行 import，否则不会被收集。
"""

from cases import (  # noqa: F401
    c_create,
    c_delete,
    c_depot,
    c_edit,
    c_entry,
    c_list,
    c_material,
    c_product,
    c_query,
    c_status,
    # a_* 是接口层实现，必须放在 UI 层之后导入：
    # 它们用 @api_case 往已登记的编号上挂实现，元信息以 UI 层为准
    a_depot,
    a_material,
    a_unit,
)
