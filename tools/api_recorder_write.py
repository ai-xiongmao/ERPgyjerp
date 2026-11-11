"""写接口抓取：用 UI 操作触发完整 CRUD，把写接口请求体一并录下来。

只在测试前缀（AT+4位）下造数据，跑完按前缀回收，不碰既有业务数据。

用法：
    ./.venv/Scripts/python.exe tools/api_recorder_write.py
    ./.venv/Scripts/python.exe tools/api_recorder_write.py unit
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from api_recorder import Recorder, mask, summarize  # noqa: E402

from framework.browser import connect  # noqa: E402
from framework.context import Context  # noqa: E402
from framework.data import TestData  # noqa: E402

OUT_DIR = HERE / "api_dump"


def step(label, fn):
    """单步执行，失败只记一行，不中断整轮抓取。"""
    print(f"  · {label}")
    try:
        fn()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"    ✗ {type(exc).__name__}: {str(exc)[:160]}")
        return False


def grab_unit(ctx):
    name = ctx.data.name("U")[:10]
    print(f"  多单位 {name}")
    step("新增", lambda: (ctx.data.track(name, [("箱", 10)]), ctx.open_unit(), ctx.unit.create(name, [("箱", 10)])))
    new = ctx.data.name("U")[:10]
    step("编辑（改名+改比例）", lambda: ctx.unit.update(name, new_basic=new, others=[("箱", 12)]))
    step("禁用（批量状态）", lambda: ctx.unit.set_status(new, "禁用"))
    step("启用（批量状态）", lambda: ctx.unit.set_status(new, "启用"))
    step("行内删除", lambda: ctx.unit.delete(new))

    # 批量删除：造两条 → 勾选 → 工具栏删除
    b1 = ctx.data.name("U")[:10]
    b2 = ctx.data.name("U")[:10]

    def batch_delete():
        ctx.data.track(b1, [("箱", 2)])
        ctx.data.track(b2, [("箱", 3)])
        ctx.open_unit()
        ctx.unit.create(b1, [("箱", 2)])
        ctx.unit.create(b2, [("箱", 3)])
        ctx.unit.select_rows([b1, b2])
        ctx.unit.delete_selected()

    step("批量删除", batch_delete)


def grab_depot(ctx):
    name = ctx.data.depot_name("D")
    print(f"  仓库 {name}")
    step("新增", lambda: (ctx.data.track_depot(name), ctx.open_depot(),
                       ctx.depot.create(name, address="接口抓取地址", sort=99)))
    new = ctx.data.depot_name("D")
    ctx.data.track_depot(new)

    def edit():
        ctx.depot.open_edit_modal(name)
        ctx.depot.fill_form(name=new, address="接口抓取地址改")
        ctx.depot.click_save()
        ctx.depot.save_success()

    step("编辑（改名）", edit)
    step("设为默认", lambda: ctx.depot.set_default(new))
    step("禁用（批量状态）", lambda: ctx.depot.set_status(new, "禁用"))
    step("启用（批量状态）", lambda: ctx.depot.set_status(new, "启用"))
    step("行内删除", lambda: ctx.depot.delete(new))

    d1 = ctx.data.depot_name("D")
    d2 = ctx.data.depot_name("D")

    def batch_delete():
        ctx.data.track_depot(d1)
        ctx.data.track_depot(d2)
        ctx.open_depot()
        ctx.depot.create(d1)
        ctx.depot.create(d2)
        ctx.depot.select_rows([d1, d2])
        ctx.depot.batch_action("删除")

    step("批量删除", batch_delete)


def grab_product(ctx):
    name = ctx.data.material_name("M")
    print(f"  商品 {name}")
    step("新增", lambda: (ctx.data.track_material(name), ctx.open_product(),
                       ctx.product.create(name, "个")))
    new = ctx.data.material_name("M")
    ctx.data.track_material(new)

    def edit():
        ctx.product.open_edit_modal(name)
        ctx.product.fill_name(new)
        ctx.product.click_save()
        ctx.product.save_success()

    step("编辑（改名）", edit)
    step("禁用（批量状态）", lambda: ctx.product.set_status(new, "禁用"))
    step("启用（批量状态）", lambda: ctx.product.set_status(new, "启用"))
    step("行内删除", lambda: ctx.product.delete(new))

    m1 = ctx.data.material_name("M")
    m2 = ctx.data.material_name("M")

    def batch_delete():
        ctx.data.track_material(m1)
        ctx.data.track_material(m2)
        ctx.open_product()
        ctx.product.create(m1, "个")
        ctx.product.create(m2, "个")
        ctx.product.select_rows([m1, m2])
        ctx.product.batch_action("删除")

    step("批量删除", batch_delete)


GRABBERS = {"unit": grab_unit, "depot": grab_depot, "product": grab_product}


def main():
    only = sys.argv[1:] or list(GRABBERS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as page:
        rec = Recorder(page)
        ctx = Context(page, TestData())
        print(f"运行前缀 {ctx.data.token}")
        for key in only:
            fn = GRABBERS.get(key)
            if fn is None:
                print(f"未知模块：{key}")
                continue
            print(f"[{key}]")
            try:
                fn(ctx)
            except Exception as exc:  # noqa: BLE001
                print(f"  模块中断：{type(exc).__name__}: {exc}")
        # 收尾：按前缀回收（本身也会产生 delete 请求，正好一并录下）
        print("[收尾] 按前缀回收")
        try:
            ctx.cleanup()
        except Exception as exc:  # noqa: BLE001
            print(f"  回收失败：{type(exc).__name__}: {exc}")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump = OUT_DIR / f"write_{stamp}.json"
        items = [it for it in rec.drain() if "status" in it]
        for it in items:
            it["headers"] = mask(it["headers"])
        dump.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        md = OUT_DIR / f"write_{stamp}.md"
        md.write_text(summarize(items, dump), encoding="utf-8")
        print(f"\n捕获 {len(items)} 个请求")
        print(f"原始：{dump}")
        print(f"清单：{md}")


if __name__ == "__main__":
    main()
