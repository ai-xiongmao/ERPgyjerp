"""接口封装层：一个业务模块一个类，对标 pages/ 的页面对象。"""

from apis.depot_api import DepotApi
from apis.material_api import MaterialApi
from apis.unit_api import UnitApi

__all__ = ["DepotApi", "MaterialApi", "UnitApi"]
