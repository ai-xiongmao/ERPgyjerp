"""页面对象公共能力。

本文件只放「所有业务页面都长一个样」的交互：Ant Design 的按钮、toast、
确认框、Popconfirm、表单内联校验。业务语义留在各页面对象里。

实测要点（改前端后请重新核对）：
- 查询/重置按钮文案被 Ant Design 拆成「查 询」「重 置」，因此按钮匹配统一用
  `spaced()` 生成 `查\\s*询` 这种正则；工具栏的「新增/删除/启用/禁用」没有空格。
- toast 是 `.ant-message-notice`（约 3 秒自动消失），必须在动作后立刻读。
- 表单内联红字在 `.ant-form-explain` 里，`has-error` 类名不一定加。
- 确认框是 `.ant-modal-confirm`（标题 `.ant-modal-confirm-title`，正文
  `.ant-modal-confirm-content`，主按钮为「确 定」），它不是普通弹窗，
  所以普通弹窗选择器必须排除它。
- 行内删除确认是 `.ant-popover`（文案「确定删除吗?」），且该浮层是**预渲染**的，
  必须带 `:visible` 才是真正弹出的那个。
"""

import re
import time

from browser import SessionExpiredError, ensure_login, expired_modal_text, session_alive

from config import ACTION_DELAY_MS

MODAL = ".ant-modal:visible:not(.ant-modal-confirm)"
CONFIRM = ".ant-modal-confirm:visible"
POPOVER = ".ant-popover:visible"
TOAST = ".ant-message-notice"
SPIN = ".ant-spin-spinning"


def spaced(text):
    """「查 询」这类被 Ant Design 插空格的按钮文案，用宽松正则匹配。"""
    return re.compile(r"\s*".join(re.escape(ch) for ch in text))


class BasePage:
    # 工具栏与查询区都在「含表格的卡片」里；用 :has(.ant-table) 避开顶部统计卡片
    BUTTON_SCOPE = ".ant-card:has(.ant-table) button"

    # 登录态探活是真实的网络请求，缓存一小段时间，避免每个动作都打一次接口
    LOGIN_TTL = 20.0

    def __init__(self, page):
        self.page = page
        self.action_delay = ACTION_DELAY_MS
        self._login_checked_at = 0.0

    # ---------------- 基础 ----------------
    def pause(self, ms=None):
        delay = self.action_delay if ms is None else ms
        if delay:
            self.page.wait_for_timeout(delay)

    def ensure_alive(self, force=False):
        """确认登录态；TTL 内不重复探活（掉登录仍会由操作失败兜住）。"""
        now = time.time()
        if not force and now - self._login_checked_at < self.LOGIN_TTL:
            return False
        recovered = ensure_login(self.page)
        self._login_checked_at = time.time()
        return recovered

    def _safe_evaluate(self, script, default=None):
        """页面跳转中执行 JS 会抛「context destroyed」，这里统一降级。"""
        try:
            return self.page.evaluate(script)
        except Exception:  # noqa: BLE001
            return default

    # ---------------- 按钮 ----------------
    def button(self, text, scope=None):
        return self.page.locator(scope or self.BUTTON_SCOPE).filter(has_text=spaced(text))

    def click_button(self, text, scope=None, timeout=15000):
        locator = self.button(text, scope).first
        locator.wait_for(state="visible", timeout=timeout)
        locator.click()
        self.pause()
        return self

    # ---------------- 导航 ----------------
    def goto(self, url, retries=2, wait_after=500):
        """跳转并容忍「被另一次导航打断」。

        SPA 自身的路由跳转（或上一条用例尚未结束的导航）会和手动 goto 撞车，
        Playwright 抛 "interrupted by another navigation"；这类冲突重试即可恢复。
        """
        for attempt in range(retries + 1):
            try:
                self.page.goto(url, wait_until="domcontentloaded")
                break
            except Exception as exc:  # noqa: BLE001
                if "interrupted by another navigation" not in str(exc) or attempt == retries:
                    raise
                self.page.wait_for_timeout(800)
        if wait_after:
            self.page.wait_for_timeout(wait_after)
        return self

    # ---------------- 输入 ----------------
    def fill(self, target, value, timeout=15000):
        """填写输入框并保持动作间隔（统一入口，不要在外面直接调 page.fill）。

        target 支持两种写法：
        - 选择器字符串，如 self.fill("#basicUnit", "瓶")
        - Locator，如 self.fill(modal.locator("#name"), "箱")
        value=None 视为清空。
        """
        locator = target.first if hasattr(target, "fill") else self.page.locator(target).first
        locator.fill("" if value is None else str(value), timeout=timeout)
        self.pause()
        return self

    # ---------------- toast ----------------
    def toasts(self):
        return self._safe_evaluate(
            "() => Array.from(document.querySelectorAll('.ant-message-notice'))"
            ".map(n => (n.innerText || '').trim()).filter(Boolean)",
            default=[]) or []

    def wait_toast(self, needle=None, timeout=6000, label="toast"):
        """等一条 toast；needle=None 表示任意一条。返回命中的文案。"""
        deadline = time.time() + timeout / 1000
        seen = []
        while time.time() < deadline:
            seen = self.toasts()
            for text in seen:
                if needle is None or needle in text:
                    return text
            self.page.wait_for_timeout(150)
        raise AssertionError(f"等待{label}「{needle or '任意'}」超时，页面提示：{seen}")

    def drain_toasts(self, timeout=8000):
        """等旧 toast 消失，避免「上一条提示」冒充本条结果。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            if not self.toasts():
                return True
            self.page.wait_for_timeout(200)
        return False

    # ---------------- 弹窗 ----------------
    def modal(self):
        return self.page.locator(MODAL).last

    def modal_visible(self):
        return self.page.locator(MODAL).count() > 0

    def modal_title(self):
        locator = self.modal().locator(".ant-modal-title")
        return locator.first.inner_text().strip() if locator.count() else ""

    def modal_body_text(self):
        return self.modal().inner_text()

    def inline_errors(self):
        """表单内联校验红字。"""
        if not self.modal_visible():
            return []
        return self._safe_evaluate(
            "() => Array.from(document.querySelectorAll('.ant-modal:not(.ant-modal-confirm) .ant-form-explain'))"
            ".map(n => (n.innerText || '').trim()).filter(Boolean)",
            default=[]) or []

    def wait_message(self, needle, timeout=6000, label="提示"):
        """内联红字与 toast 任一命中即可（页面不同分支用不同方式提示）。"""
        deadline = time.time() + timeout / 1000
        seen = []
        while time.time() < deadline:
            seen = self.toasts() + self.inline_errors()
            for text in seen:
                if needle in text:
                    return text
            self.page.wait_for_timeout(150)
        raise AssertionError(f"等待{label}「{needle}」超时，页面提示：{seen}")

    def cancel_modal(self):
        """关闭普通弹窗（丢弃未保存内容）；弹窗自己已经关掉时不算失败。"""
        if not self.modal_visible():
            return self
        try:
            self.modal().locator("button").filter(
                has_text=spaced("取消")).first.click(timeout=6000)
        except Exception:  # noqa: BLE001 - 动画/自动关闭导致点不到，交给下面的兜底
            pass
        self.pause()
        if self.modal_visible():
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                pass
        try:
            if self.modal_visible():
                self.modal().wait_for(state="hidden", timeout=5000)
        except Exception:  # noqa: BLE001
            pass
        return self

    # ---------------- 确认框 ----------------
    def confirm_dialog(self):
        return self.page.locator(CONFIRM)

    def confirm_texts(self):
        dialog = self.confirm_dialog()
        title = dialog.locator(".ant-modal-confirm-title").inner_text().strip()
        content = dialog.locator(".ant-modal-confirm-content").inner_text().strip()
        return title, content

    def click_confirm(self, text="确定"):
        dialog = self.confirm_dialog()
        dialog.locator("button").filter(has_text=spaced(text)).first.click()
        self.pause()
        try:
            dialog.wait_for(state="hidden", timeout=12000)
        except Exception:  # noqa: BLE001
            pass
        return self

    # ---------------- 收尾 ----------------
    def close_overlays(self, limit=4):
        """关掉所有挡路的浮层：确认框 → Popconfirm → 普通弹窗。"""
        for _ in range(limit):
            try:
                if self.confirm_dialog().count():
                    self.confirm_dialog().locator("button").filter(
                        has_text=spaced("取消")).first.click()
                    self.page.wait_for_timeout(300)
                    continue
                if self.page.locator(POPOVER).count():
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(200)
                    continue
                if self.modal_visible():
                    self.cancel_modal()
                    continue
                break
            except Exception:  # noqa: BLE001 - 收尾尽力而为
                break
        return self

    def _raise_if_session_dead(self):
        probe = session_alive(self.page)
        if not probe.get("ok") and probe.get("reason") in ("loginOut", "no-token"):
            raise SessionExpiredError(
                "操作失败：服务端会话已失效（loginOut）。请在 MyTest 浏览器重新登录后重跑脚本。")

    def _expired_or_raise(self, action, exc):
        expired = expired_modal_text(self.page)
        if expired:
            raise SessionExpiredError(
                f"{action}失败：{expired.splitlines()[0].strip()}。"
                "请在 MyTest 浏览器重新登录后重跑脚本。") from exc
        self._raise_if_session_dead()
