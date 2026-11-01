"""商品联动：TC-UNIT-042，以及无法构造前置条件的 TC-UNIT-037 / 044。"""

import re

from framework.asserts import check, check_contains, check_eq
from framework.registry import case, manual
from cases._helpers import expected_name

OPTION_PATTERN = re.compile(r"^.+/.+=.+$")


@case("TC-UNIT-042", "商品端「多单位」下拉与本单位数据联动", "商品联动", "高")
def tc_unit_042(ctx):
    """商品信息新增弹窗：勾「多单位」→ 下拉应列出单位页面已录入的记录。"""
    basic = ctx.new_unit([("箱", 10)])
    expected = expected_name(basic, "箱", 10)

    product = ctx.product.open()
    product.open_create_modal()
    product.enable_multi_unit()
    check_eq(product.multi_unit_select().count(), 1, "勾选多单位后应出现「选择多单位」下拉")

    options = product.multi_unit_options()
    check(options, "多单位下拉不应为空")
    check_contains("\n".join(options), expected,
                   f"下拉未包含单位页面新录入的「{expected}」，前几项：{options[:5]}")

    bad = [text for text in options if not OPTION_PATTERN.match(text)]
    check(not bad, f"选项格式应为「基本单位/(副单位=比例基本单位)」：{bad[:5]}")

    duplicated = sorted({text for text in options if options.count(text) > 1})
    if duplicated:
        ctx.note(f"同名单位在下拉中重复出现：{duplicated[:3]}（已知偏差，见用例备注）")

    product.cancel()
    check(not product.modal_visible(), "取消后商品新增弹窗应关闭")


manual(
    "TC-UNIT-037", "试用到期后访问与操作", "权限", "低",
    reason="前置条件为「账号试用已到期」（当前页面显示试用到期 2026-11-08），"
           "无法在不改变账号状态的前提下构造；到期后人工执行",
)

manual(
    "TC-UNIT-044", "删除被拦截后商品数据不受影响", "删除", "中",
    reason="依赖 TC-UNIT-033（删除被商品引用的单位）与商品详情核对，"
           "涉及真实业务数据的破坏性操作，留人工执行",
)
