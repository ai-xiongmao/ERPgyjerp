"""页面探查工具：核对选择器、查看弹窗与下拉结构。

新增用例或页面改版后，先跑它确认 DOM，再改 pages/*.py。

用法：
    python tools/probe.py                # 当前页面结构（默认 dom）
    python tools/probe.py dom            # 同上
    python tools/probe.py modal          # 多单位新增弹窗 / 校验提示 / 批量确认框
    python tools/probe.py product        # 商品信息页「多单位」下拉
    python tools/probe.py depot          # 仓库信息页：表头列序 / 操作列链接 / 新增弹窗 / 设为默认 Popover

注意：modal / product / depot 会真实打开弹窗并做少量交互（结尾会取消关闭），
会短暂占用浏览器，但不会留下业务数据（depot 只做空表单保存 + Popover 取消）。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser import connect  # noqa: E402
from config import BASE_URL  # noqa: E402


# ==================== dom：当前页面结构 ====================
DOM_JS = """() => {
    const text = (el) => (el ? (el.innerText || el.textContent || '').trim() : null);
    const q = (sel) => Array.from(document.querySelectorAll(sel));
    const info = {};

    info.title = document.title;
    info.url = location.href;

    const bc = document.querySelector('.ant-breadcrumb');
    info.breadcrumb = bc ? bc.innerText.replace(/\\s+/g, ' ').trim() : null;

    info.activeMenu = q('.ant-menu-item-selected').map(text);

    info.inputs = q('.ant-card input, form input, .ant-input').map(el => ({
        placeholder: el.getAttribute('placeholder'),
        id: el.id || null,
        cls: el.className,
        type: el.type,
    }));

    info.buttons = q('button').map(el => ({
        text: text(el),
        cls: el.className,
        disabled: el.disabled,
    })).filter(b => b.text);

    info.headers = q('.ant-table-thead th').map(el => ({
        text: text(el),
        cls: el.className,
        hasCheckbox: !!el.querySelector('input[type=checkbox], .ant-checkbox'),
    }));

    const rows = q('.ant-table-tbody tr');
    info.rowCount = rows.length;
    info.rows = rows.slice(0, 3).map(tr => ({
        cls: tr.className,
        cells: Array.from(tr.children).map(td => text(td)),
        checkbox: !!tr.querySelector('.ant-checkbox, input[type=checkbox]'),
        links: Array.from(tr.querySelectorAll('a')).map(text),
        tds: tr.children.length,
    }));

    const pag = document.querySelector('.ant-pagination');
    info.pagination = pag ? {
        text: text(pag).replace(/\\s+/g, ' '),
        items: Array.from(pag.querySelectorAll('li')).map(li => ({cls: li.className, text: text(li)})),
    } : null;

    info.statusCells = q('.ant-table-tbody tr').slice(0, 3)
        .map(tr => text(tr.lastElementChild));

    info.empty = text(document.querySelector('.ant-empty'));
    info.messageHosts = q('.ant-message, .ant-notification, .ant-modal-root').length;

    return info;
}"""


def probe_dom(page):
    print(json.dumps(page.evaluate(DOM_JS), ensure_ascii=False, indent=2))


# ==================== modal：多单位弹窗与确认框 ====================
MODAL_JS = """() => {
    const m = document.querySelector('.ant-modal-wrap:not([style*="display: none"]) .ant-modal') ||
              document.querySelector('.ant-modal');
    if (!m) return null;
    const text = el => (el ? (el.innerText || '').trim() : null);
    return {
        title: text(m.querySelector('.ant-modal-title, .ant-modal-confirm-title')),
        bodyText: text(m.querySelector('.ant-modal-body')),
        cls: m.className,
        labels: Array.from(m.querySelectorAll('.ant-form-item-label')).map(l => ({
            text: text(l),
            required: !!l.querySelector('.ant-form-item-required'),
        })),
        fields: Array.from(m.querySelectorAll('input')).map(i => ({
            id: i.id || null,
            placeholder: i.getAttribute('placeholder'),
            value: i.value,
            cls: i.className,
        })),
        buttons: Array.from(m.querySelectorAll('button')).map(b => ({
            text: text(b), cls: b.className,
        })),
        formItems: Array.from(m.querySelectorAll('.ant-form-item')).map(it => ({
            label: text(it.querySelector('.ant-form-item-label')),
            explain: text(it.querySelector('.ant-form-explain')),
            hasError: it.className.indexOf('has-error') >= 0,
        })),
    };
}"""

TOAST_JS = """() => Array.from(document.querySelectorAll('.ant-message-notice, .ant-notification-notice'))
    .map(n => n.innerText.trim())"""


def probe_modal(page):
    page.locator("button").filter(has_text="新增").first.click()
    page.wait_for_timeout(1200)
    print("== 新增弹窗 ==")
    print(json.dumps(page.evaluate(MODAL_JS), ensure_ascii=False, indent=2))

    page.locator(".ant-modal:visible button").filter(has_text="保 存").first.click()
    page.wait_for_timeout(1200)
    print("\n== 空表单保存后 ==")
    print("toast:", json.dumps(page.evaluate(TOAST_JS), ensure_ascii=False))
    print("modal:", json.dumps(page.evaluate(MODAL_JS), ensure_ascii=False, indent=2)[:1600])

    page.fill("#basicUnit", "AT_PR1")
    page.locator(".ant-modal:visible button").filter(has_text="保 存").first.click()
    page.wait_for_timeout(1200)
    print("\n== 只填基本单位保存后 toast ==", json.dumps(page.evaluate(TOAST_JS), ensure_ascii=False))

    page.locator(".ant-modal:visible button").filter(has_text="取 消").first.click()
    page.wait_for_timeout(800)
    print("弹窗还开着？", page.locator(".ant-modal:visible").count())

    row = page.locator(".ant-table-tbody tr.ant-table-row").first
    row.locator(".ant-checkbox-input").click(force=True)
    page.wait_for_timeout(500)
    page.locator("button").filter(has_text="启用").first.click()
    page.wait_for_timeout(1200)
    print("\n== 批量确认框 ==")
    print(json.dumps(page.evaluate("""() => {
        const c = document.querySelector('.ant-modal-confirm');
        if (!c) return {none: true, body: document.body.innerText.slice(0, 300)};
        return {
            title: (c.querySelector('.ant-modal-confirm-title')||{}).innerText,
            content: (c.querySelector('.ant-modal-confirm-content')||{}).innerText,
            buttons: Array.from(c.querySelectorAll('button')).map(b => b.innerText.trim() + '|' + b.className),
        };
    }"""), ensure_ascii=False, indent=2))

    page.locator(".ant-modal-confirm button").filter(has_text="取 消").first.click()
    page.wait_for_timeout(500)
    row.locator(".ant-checkbox-input").click(force=True)
    page.wait_for_timeout(300)


# ==================== product：商品页多单位下拉 ====================
def probe_product(page):
    page.goto(BASE_URL + "/material/material", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    print("url:", page.url, "title:", page.title())

    print("\n== 工具栏按钮 ==")
    print(json.dumps(page.evaluate(
        "() => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean)"
    ), ensure_ascii=False))

    page.locator("button").filter(has_text="新增").first.click()
    page.wait_for_timeout(2500)

    print("\n== 新增商品弹窗中的「单位」相关元素 ==")
    print(json.dumps(page.evaluate("""() => {
        const vis = Array.from(document.querySelectorAll('.ant-modal')).find(x => x.offsetWidth||x.offsetHeight);
        if (!vis) return {none: true};
        return {
            title: (vis.querySelector('.ant-modal-title')||{}).innerText,
            labels: Array.from(vis.querySelectorAll('.ant-form-item-label')).map(l => l.innerText.trim()),
            checkboxes: Array.from(vis.querySelectorAll('.ant-checkbox-wrapper')).map(c => ({
                text: c.innerText.trim(), cls: c.className,
            })),
        };
    }"""), ensure_ascii=False, indent=1))

    dz = page.locator(".ant-modal:visible .ant-checkbox-wrapper").filter(has_text="多单位")
    print("\n多单位勾选框数量:", dz.count())
    if dz.count():
        dz.first.click()
        page.wait_for_timeout(1500)
        print("\n== 勾选多单位后：单位区域 ==")
        print(json.dumps(page.evaluate("""() => {
            const vis = Array.from(document.querySelectorAll('.ant-modal')).find(x => x.offsetWidth||x.offsetHeight);
            return {
                hasSelect: !!document.querySelector('.ant-modal .ant-select'),
                selects: Array.from(document.querySelectorAll('.ant-modal .ant-select')).map(s => ({
                    text: s.innerText.replace(/\\n+/g,' | ').trim(),
                    cls: s.className,
                })),
                inputs: Array.from(vis.querySelectorAll('input')).slice(0, 25).map(i => ({
                    id: i.id, placeholder: i.getAttribute('placeholder'), value: i.value,
                })).filter(i => i.placeholder || i.id),
            };
        }"""), ensure_ascii=False, indent=1))

    sel = page.locator(".ant-modal:visible .ant-select").filter(has_text="选择多单位")
    print("\n选择多单位 select 数量:", sel.count())
    if sel.count():
        sel.first.click()
        page.wait_for_timeout(1500)
        print("\n== 下拉选项 ==")
        print(json.dumps(page.evaluate("""() => {
            const dds = Array.from(document.querySelectorAll('.ant-select-dropdown'))
                .filter(d => d.offsetWidth || d.offsetHeight);
            return dds.map(d => ({
                cls: d.className,
                options: Array.from(d.querySelectorAll('.ant-select-dropdown-menu-item')).map(o => o.innerText.trim()),
            }));
        }"""), ensure_ascii=False, indent=1))

    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    cancel = page.locator(".ant-modal:visible button").filter(has_text="取 消")
    if cancel.count():
        cancel.first.click()
        page.wait_for_timeout(800)
    print("\n弹窗剩余:", page.locator(".ant-modal:visible").count())


# ==================== depot：仓库信息页 ====================
DEPOT_PATH = "/system/depot"

DEPOT_TABLE_JS = """() => {
    const text = el => (el ? (el.innerText || '').trim() : null);
    const ths = Array.from(document.querySelectorAll('.ant-table-thead th'));
    const rows = Array.from(document.querySelectorAll('.ant-table-tbody tr.ant-table-row'));
    return {
        headers: ths.map((th, i) => ({
            i,
            text: text(th),
            hasCheckbox: !!th.querySelector('.ant-checkbox, input[type=checkbox]'),
        })),
        rowCount: rows.length,
        empty: text(document.querySelector('.ant-empty')),
        rows: rows.slice(0, 3).map(tr => ({
            cells: Array.from(tr.children).map(td => text(td)),
            links: Array.from(tr.querySelectorAll('a')).map(text),
            selects: tr.querySelectorAll('.ant-select').length,
        })),
        pagination: text(document.querySelector('.ant-pagination')),
    };
}"""

DEPOT_ERRORS_JS = """() => {
    const m = Array.from(document.querySelectorAll('.ant-modal'))
        .filter(x => x.offsetWidth || x.offsetHeight).pop();
    if (!m) return {none: true};
    // 这套系统的校验提示挂在 .ant-form-explain 上，父级 .ant-form-item 不加 has-error，
    // 所以只能按「非空提示文本」收集，不能靠 has-error 筛选。
    return Array.from(m.querySelectorAll('.ant-form-explain'))
        .map(e => (e.innerText || '').trim())
        .filter(t => t);
}"""

DEPOT_POPOVER_JS = """() => {
    const p = Array.from(document.querySelectorAll('.ant-popover'))
        .filter(x => x.offsetWidth || x.offsetHeight).pop();
    if (!p) return {none: true};
    const t = el => (el ? (el.innerText || '').trim() : null);
    return {
        text: t(p),
        cls: p.className,
        buttons: Array.from(p.querySelectorAll('button')).map(b => ({
            text: t(b), cls: b.className,
        })),
    };
}"""


def probe_depot(page):
    """仓库信息页：表头列序、操作列链接、新增弹窗字段、空表单校验、设为默认 Popover。

    表头列序是 pages/depot_page.py 里 ROWS_JS 列索引的唯一依据，
    改版后先跑这个，再对照 cells 下标改索引。

    只做不落库的交互：空表单保存会被校验拦住；设为默认只开 Popover 后取消。
    """
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    page.goto(BASE_URL + DEPOT_PATH, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    print("url:", page.url, "title:", page.title())

    table = page.evaluate(DEPOT_TABLE_JS)
    print("\n== 表头（下标 = JS 里 cells[i]，即第 i+1 个 td）==")
    for h in table["headers"]:
        mark = "  <- 勾选框列" if h["hasCheckbox"] else ""
        print(f"  cells[{h['i']}] = {h['text']!r}{mark}")
    print("\n行数:", table["rowCount"], "| 空态:", table["empty"], "| 分页:", table["pagination"])
    print("\n== 前 3 行（cells / 操作列链接）==")
    print(json.dumps(table["rows"], ensure_ascii=False, indent=1))

    print("\n== 工具栏按钮 ==")
    print(json.dumps(page.evaluate(
        "() => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean)"
    ), ensure_ascii=False))

    page.locator("button").filter(has_text="新增").first.click()
    page.wait_for_timeout(1500)
    print("\n== 新增弹窗 ==")
    print(json.dumps(page.evaluate(MODAL_JS), ensure_ascii=False, indent=1))

    # 空表单保存：只验证校验提示，不会落库
    page.locator(".ant-modal-wrap:visible button").filter(has_text="保 存").first.click()
    page.wait_for_timeout(1500)
    print("\n== 空表单保存后 ==")
    print("toast:", json.dumps(page.evaluate(TOAST_JS), ensure_ascii=False))
    print("校验提示:", json.dumps(page.evaluate(DEPOT_ERRORS_JS), ensure_ascii=False))
    print("弹窗还开着？", page.locator(".ant-modal-wrap:visible").count())

    cancel = page.locator(".ant-modal-wrap:visible button").filter(has_text="取 消")
    if cancel.count():
        cancel.first.click()
        try:  # 关闭动画比想象的慢，等可见性消失而不是固定 sleep
            page.locator(".ant-modal-wrap:visible").first.wait_for(state="hidden", timeout=6000)
        except Exception:  # noqa: BLE001 - 关不掉也不该让探查中断
            pass
    print("取消后弹窗剩余:", page.locator(".ant-modal-wrap:visible").count())

    # 设为默认：只打开 Popover 看结构，随后取消，不动真实默认仓库
    link = page.locator(".ant-table-tbody tr.ant-table-row a").filter(has_text="设为默认")
    print("\n「设为默认」链接数量:", link.count())
    if not link.count():
        print("列表无数据行，跳过设为默认（Popover）探查")
        return
    link.first.click()
    page.wait_for_timeout(1000)
    print("\n== 设为默认 Popover ==")
    print(json.dumps(page.evaluate(DEPOT_POPOVER_JS), ensure_ascii=False, indent=1))

    pc = page.locator(".ant-popover:visible button").filter(has_text="取 消")
    if pc.count():
        pc.first.click()
        try:
            page.locator(".ant-popover:visible").first.wait_for(state="hidden", timeout=6000)
        except Exception:  # noqa: BLE001
            pass
    print("Popover 剩余:", page.locator(".ant-popover:visible").count())


MODES = {
    "dom": probe_dom,
    "modal": probe_modal,
    "product": probe_product,
    "depot": probe_depot,
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    mode = sys.argv[1] if len(sys.argv) > 1 else "dom"
    if mode not in MODES:
        print(f"未知模式：{mode}\n可用：{' / '.join(MODES)}", file=sys.stderr)
        return 2

    with connect() as page:
        MODES[mode](page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
