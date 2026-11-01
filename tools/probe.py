"""页面探查工具：核对选择器、查看弹窗与下拉结构。

新增用例或页面改版后，先跑它确认 DOM，再改 pages/*.py。

用法：
    python tools/probe.py                # 当前页面结构（默认 dom）
    python tools/probe.py dom            # 同上
    python tools/probe.py modal          # 多单位新增弹窗 / 校验提示 / 批量确认框
    python tools/probe.py product        # 商品信息页「多单位」下拉

注意：modal / product 会真实打开弹窗并做少量交互（结尾会取消关闭），
会短暂占用浏览器，但不会留下业务数据。
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


MODES = {
    "dom": probe_dom,
    "modal": probe_modal,
    "product": probe_product,
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
