"""仓库信息 - 异常与权限（TC-DEP-037 ~ 038）。

页面顶部无关统计卡片、以及前置条件不具备的用例。
"""

from framework.asserts import check
from framework.registry import case, manual

manual(
    "TC-DEP-037", "试用到期后访问与操作", "权限", "低",
    reason="前置条件为「账号试用已到期」，无法在不改变账号状态的前提下构造；到期后人工执行",
)


@case("TC-DEP-038", "页面顶部出现无关统计卡片", "异常", "中")
def tc_dep_038(ctx):
    """页面顶部可能有「今日销售/本月累计销售」等统计卡片，不作为缺陷，仅确认不影响操作。"""
    depot = ctx.depot.open()

    # 统计卡片是首页模块设计行为，可能存在也可能不存在；只确认表格与工具栏正常
    check(depot.page.locator(".ant-table").count() >= 1, "表格应正常渲染")
    for text in ("新增", "删除", "启用", "禁用"):
        check(depot.button(text).count() >= 1, f"工具栏「{text}」应正常展示")

    # 记录顶部卡片情况（不做通过/失败判断）
    cards = depot.page.locator(".ant-card").all_inner_texts()
    stat_cards = [c for c in cards if ("今日销售" in c or "本月累计" in c)]
    if stat_cards:
        ctx.note("页面顶部存在统计卡片（首页模块设计行为，不作为缺陷）")
    else:
        ctx.note("本次未出现顶部统计卡片")
