"""商品管理 - 多单位：增删改查端到端脚本。

运行前提：
1. 桌面 MyTest 浏览器已打开，且其中已在 https://cloud.gyjerp.com 登录；
2. 已安装依赖：.venv/Scripts/python.exe -m pip install -r requirements.txt

运行：
    .venv/Scripts/python.exe run_unit_crud.py
"""

import sys
import time

from browser import SessionExpiredError, connect
from pages.unit_page import UnitPage

# 测试数据前缀：既保证可重复运行，又保证清理时只动自己造的数据。
# 注意基本单位输入框限制「长度 1 到 10 个字符」，所以名字必须短。
PREFIXES = ("AT_U", "AT_V", "AT_Z")
RATIO = 12
TOTAL_STEPS = 6


def step(index, text):
    print(f"[{index}/{TOTAL_STEPS}] {text}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    started = time.time()
    stamp = time.strftime("%H%M%S")
    basic = f"AT_U{stamp}"      # 基本单位，创建时用
    other = f"AT_Z{stamp}"      # 副单位
    new_basic = f"AT_V{stamp}"  # 修改后的基本单位
    others = [(other, RATIO)]

    with connect() as page:
        unit = UnitPage(page).open()

        step(1, "清理历史测试数据")
        removed = unit.cleanup_prefix(PREFIXES)
        print(f"        清理 {removed} 条历史数据")

        try:
            step(2, f"新增：{basic}，副单位 {other}={RATIO}{basic}")
            unit.create(basic, others)
            data = unit.read_row(basic)
            assert data["basic"] == basic, f"基本单位列不符：{data['basic']!r}"
            expected_other = f"{other}={RATIO}{basic}"
            assert data["other"] == expected_other, f"副单位列不符：{data['other']!r} != {expected_other!r}"
            expected_name = f"{basic}/({expected_other})"
            assert data["name"] == expected_name, f"单位名称列不符：{data['name']!r} != {expected_name!r}"
            print(f"        OK 单位名称={data['name']}；状态={data['status']}")

            step(3, f"查询：按单位名称搜索「{basic}」")
            unit.search(basic)
            hits = unit.basic_units()
            assert len(hits) == 1 and hits[0] == basic, f"查询「{basic}」应只命中它自己，实际命中：{hits}"
            print(f"        OK 命中 1 行：{unit.read_row(basic)['name']}")
            unit.reset()

            step(4, f"修改：基本单位 {basic} → {new_basic}")
            unit.update(basic, new_basic, others)
            assert unit.has_row(new_basic), "修改后的新值没有出现在表格里"
            assert not unit.has_row(basic), "修改前的旧值仍然存在"
            print(f"        OK 新名称={unit.read_row(new_basic)['name']}")

            step(5, f"删除：{new_basic}")
            unit.delete(new_basic)
            assert not unit.has_row(new_basic), "删除后该行仍然存在"
            print("        OK 该行已从表格消失")

            step(6, "校验无残留测试数据")
            leftovers = [b for b in unit.basic_units() if b.startswith(PREFIXES)]
            assert not leftovers, f"仍有残留测试数据：{leftovers}"
            print("        OK 表格干净")
        finally:
            # 中途失败也不把测试数据留在系统里；但清理失败不能盖住原始异常
            try:
                leftover = unit.cleanup_prefix(PREFIXES)
                if leftover:
                    print(f"        已清理中途残留 {leftover} 条")
            except SessionExpiredError:
                # 登录已过期时页面上的删除只是前端移除，跳过清理以免误报
                print("        登录已过期，跳过残留清理")
            except Exception as cleanup_exc:  # noqa: BLE001
                print(f"        清理残留失败：{type(cleanup_exc).__name__}: {cleanup_exc}")

    print(f"\n全部通过：新增 → 查询 → 修改 → 删除（耗时 {time.time() - started:.1f}s）")


if __name__ == "__main__":
    try:
        main()
    except SessionExpiredError as exc:  # noqa: BLE001 - 登录过期单独给出可操作指引
        print(f"\n[需要重新登录] {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，打印后按失败退出
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
