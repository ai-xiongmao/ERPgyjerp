"""连接桌面 MyTest 浏览器（Chromium + CDP）。

设计要点：
1. 只做「接入」，不新开浏览器——复用用户已经打开的窗口和登录态；
2. 退出时只断开 CDP 连接，绝不调用 browser.close()，否则会关掉用户的浏览器进程；
3. 找不到业务页面时明确报错，而不是悄悄新建一个空白页。
"""

from contextlib import contextmanager
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

from config import APP_URL_KEYWORD, BASE_URL, CDP_ENDPOINT, DEFAULT_TIMEOUT, LOGIN_PATH


def _find_app_page(browser):
    """在所有已打开的标签页里挑出管伊佳 ERP 页。"""
    for context in browser.contexts:
        for page in context.pages:
            if APP_URL_KEYWORD in page.url:
                return page
    return None


@contextmanager
def connect(cdp_endpoint=CDP_ENDPOINT):
    """连接 MyTest 浏览器并交出一个可操作的 page。

    用法：
        with connect() as page:
            ...
    """
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp(cdp_endpoint)
        except Exception as exc:  # noqa: BLE001 - 统一转成可读的启动指引
            raise RuntimeError(
                f"无法连接桌面 MyTest 浏览器（{cdp_endpoint}）。\n"
                "请先双击桌面 MyTest.exe 打开浏览器，并确认页面已登录管伊佳 ERP。\n"
                f"原始错误：{exc}"
            ) from exc

        page = _find_app_page(browser)
        if page is None:
            raise RuntimeError(
                "MyTest 浏览器里没有找到管伊佳 ERP 页面。\n"
                "请先在 MyTest 中打开并登录 https://cloud.gyjerp.com 。"
            )

        page.set_default_timeout(DEFAULT_TIMEOUT)
        yield page
        # 这里刻意不调用 browser.close()：断开连接即可，保留用户浏览器现场


class SessionExpiredError(RuntimeError):
    """登录会话已过期，需要人工重新登录。"""


# 服务端判定会话失效后，前端会弹出全局模态框遮挡页面（此时本地 token 可能还没到期）
_EXPIRED_KEYWORDS = ("登录已过期", "请重新登录", "登录超时", "请先登录", "登录状态已失效")

_DETECT_EXPIRED_JS = """() => {
    const keywords = %s;
    const nodes = document.querySelectorAll(
        '.ant-modal-wrap, .ant-modal-confirm, .ant-message-notice, .ant-notification-notice, .ant-alert');
    for (const node of nodes) {
        const style = getComputedStyle(node);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        const text = (node.innerText || '').trim();
        if (!text) continue;
        if (keywords.some(keyword => text.includes(keyword))) return text.slice(0, 200);
    }
    return null;
}""" % json.dumps(list(_EXPIRED_KEYWORDS), ensure_ascii=False)


def expired_modal_text(page):
    """返回「登录已过期」提示文案；没有则返回 None。"""
    try:
        return page.evaluate(_DETECT_EXPIRED_JS)
    except Exception:  # 页面正在跳转时上下文会销毁，此时不具备判定条件
        return None


def _token_present(page):
    try:
        return bool(page.evaluate(
            "() => { try { const v = JSON.parse(localStorage.getItem('pro__Access-Token'));"
            " return v && v.value; } catch (e) { return null; } }"
        ))
    except Exception:
        return False


def is_logged_in(page):
    """当前页面是否处于已登录的业务状态。

    只看 URL / token 容易误判（SPA 路由跳转后 URL 可能是业务页，但服务端已判失效），
    所以要求页面真的渲染出了登录后的用户信息。
    """
    url = (page.url or "").lower()
    if APP_URL_KEYWORD not in url or "login" in url:
        return False
    if not _token_present(page) or expired_modal_text(page):
        return False
    try:
        body = page.evaluate("() => document.body.innerText || ''")
    except Exception:  # 导航中上下文销毁
        return False
    return "欢迎您" in body or "退出登录" in body


def _on_login_page(page):
    """当前是否停在登录页（登录页有验证码输入框 #inputCode）。"""
    if "login" in (page.url or "").lower():
        return True
    try:
        return page.locator("#inputCode").count() > 0
    except Exception:
        return False


# 服务端会话探活：接口失效时前端不一定弹框（实测删除失败返回 500 + "loginOut" 却无提示），
# 所以以服务端响应为准，不能只看 DOM。
_SESSION_PROBE_JS = """async () => {
    try {
        const raw = localStorage.getItem('pro__Access-Token');
        const tok = raw ? JSON.parse(raw) : null;
        if (!tok || !tok.value) return {ok: false, reason: 'no-token'};
        const r = await fetch('/jshERP-boot/unit/list?currentPage=1&pageSize=1', {
            headers: {'X-Access-Token': tok.value}
        });
        const text = await r.text();
        if (r.status === 401 || text.indexOf('loginOut') >= 0) return {ok: false, reason: 'loginOut'};
        return {ok: r.ok, reason: 'status-' + r.status};
    } catch (e) {
        return {ok: false, reason: 'error:' + (e && e.message)};
    }
}"""


def session_alive(page):
    """用一次轻量只读请求确认服务端会话是否有效：{'ok': bool, 'reason': str}。"""
    try:
        return page.evaluate(_SESSION_PROBE_JS)
    except Exception as exc:
        return {"ok": False, "reason": f"exception:{exc}"}


def login_problem(page):
    """返回 None（正常）/ 'expired'（弹了过期框）/ 'logged_out'（未登录或会话已被服务端判失效）。"""
    if expired_modal_text(page):
        return "expired"
    if _on_login_page(page) or not _token_present(page):
        return "logged_out"
    probe = session_alive(page)
    if not probe.get("ok") and probe.get("reason") in ("loginOut", "no-token"):
        return "logged_out"
    return None


def ensure_login(page, wait_seconds=None, log=print):
    """确保登录态可用；过期或掉登录时引导重新登录并等待用户完成。

    返回 True 表示本次曾掉登录并已恢复，False 表示本来就没问题。
    wait_seconds=0（或环境变量 ERP_RELOGIN_WAIT=0）表示不等待、直接抛错，供无人值守场景使用。
    """
    problem = login_problem(page)
    if problem is None:
        return False

    if wait_seconds is None:
        wait_seconds = int(os.environ.get("ERP_RELOGIN_WAIT", "180"))

    if problem == "expired":
        text = expired_modal_text(page) or ""
        log(f"        ! 检测到登录已过期：{text.replace(chr(10), ' / ')}")
    else:
        log("        ! 当前处于未登录状态")

    if wait_seconds <= 0:
        raise SessionExpiredError(
            "登录已过期或未登录。请先在 MyTest 浏览器里登录管伊佳 ERP，再重跑脚本。"
        )

    if problem == "expired":
        # 点弹窗里的「重新登录」跳到登录页
        for locator in (
            page.locator(".ant-modal-wrap:visible button", has_text=re.compile(r"重新登录")),
            page.locator("button", has_text=re.compile(r"重新登录")),
        ):
            try:
                if locator.count():
                    locator.first.click()
                    break
            except Exception:
                continue
    elif not _on_login_page(page):
        # 停在业务页但登录态已失效：直接打开登录页，给用户一个明确入口
        try:
            page.goto(BASE_URL + LOGIN_PATH, wait_until="domcontentloaded")
        except Exception:
            pass

    log("        请在 MyTest 浏览器完成登录（账号密码通常已自动填充，只需输入验证码）")
    log(f"        等待登录完成（最多 {wait_seconds}s）…")

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_logged_in(page):
            log("        登录成功，继续执行")
            return True
        try:
            page.wait_for_timeout(1000)
        except Exception:
            time.sleep(1)

    raise SessionExpiredError(
        f"等待重新登录超时（{wait_seconds}s）。请先在 MyTest 浏览器登录管伊佳 ERP，再重跑脚本。"
    )
