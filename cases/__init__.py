"""cases 包：导入即把用例注册进 framework.registry。

新增用例文件后记得在这里加一行 import，否则不会被收集。
"""

from cases import (  # noqa: F401
    c_create,
    c_delete,
    c_edit,
    c_entry,
    c_list,
    c_material,
    c_product,
    c_query,
    c_status,
)
