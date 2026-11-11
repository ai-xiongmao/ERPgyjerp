"""接口客户端：直接对 jshERP 后端发 HTTP 请求，不经过浏览器页面。

认证只有一个请求头 `x-access-token`（前端存在 localStorage 的 pro__Access-Token）。
token 获取顺序：
    1. 缓存文件 `.api_token`（跑过一次后复用，浏览器没开也能跑）；
    2. 缓存失效 → 连 MyTest 浏览器从 localStorage 取一次，再写回缓存。

约定：业务接口统一返回 `{"code": 200, "data": ...}`，code != 200 视为失败；
个别接口（如菜单树）直接返回数组，因此不在 transport 层做结构假设。
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 允许 `python framework/api_client.py` 直接自检（此时项目根不在 sys.path）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import API_PREFIX, BASE_URL

TOKEN_CACHE = Path(__file__).resolve().parents[1] / ".api_token"
DEFAULT_TIMEOUT = 25


class ApiError(AssertionError):
    """接口返回不符合预期（业务码异常 / 结构不符）。"""


def _token_from_browser():
    """连 MyTest 浏览器，从 localStorage 读登录 token。"""
    from framework.browser import connect  # 延迟导入，避免无浏览器场景下的循环依赖

    with connect() as page:
        return page.evaluate(
            "() => { try { const v = JSON.parse(localStorage.getItem('pro__Access-Token'));"
            " return v && v.value; } catch (e) { return null; } }"
        )


def _token_from_cache():
    try:
        return TOKEN_CACHE.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return None


def _save_token(token):
    try:
        TOKEN_CACHE.write_text(token, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def extract_message(parsed):
    """jshERP 的提示语分布在 data.message / data 字符串 / 顶层 message 三处。"""
    if not isinstance(parsed, dict):
        return str(parsed)[:200]
    if parsed.get("message"):
        return str(parsed["message"])
    data = parsed.get("data")
    if isinstance(data, dict) and data.get("message"):
        return str(data["message"])
    if isinstance(data, str):
        return data[:200]
    return ""


class ApiClient:
    def __init__(self, token=None, base_url=BASE_URL + API_PREFIX, timeout=DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token = token
        self.calls = []      # 记录本次运行调过的接口，便于失败时回放

    # ---------------- 认证 ----------------
    @property
    def token(self):
        if self._token:
            return self._token
        token = _token_from_cache()
        if token and self._alive(token):
            self._token = token
            return token
        token = _token_from_browser()
        if not token:
            raise ApiError(
                "拿不到登录 token：请先在 MyTest 浏览器里登录 https://cloud.gyjerp.com"
            )
        _save_token(token)
        self._token = token
        return token

    def _alive(self, token):
        """用轻量接口探活，避免拿着过期 token 跑完一整轮才发现。"""
        try:
            status, body = self.raw("GET", "/user/infoWithTenant", token=token)
            return status == 200 and isinstance(body, dict) and body.get("code") == 200
        except Exception:  # noqa: BLE001
            return False

    def refresh_token(self):
        self._token = None
        return self.token

    # ---------------- 传输 ----------------
    def raw(self, method, path, params=None, body=None, token=None):
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += ("&" if "?" in url else "?") + urllib.parse.urlencode(clean, doseq=True)
        data = None
        headers = {"x-access-token": token or self.token, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json;charset=UTF-8"
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_text = resp.read().decode("utf-8", "replace")
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw_text = exc.read().decode("utf-8", "replace")
            status = exc.code
        except urllib.error.URLError as exc:
            raise ApiError(f"接口不可达 {method} {path}：{exc.reason}") from exc
        try:
            parsed = json.loads(raw_text) if raw_text.strip() else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw_text}
        return status, parsed

    def call(self, method, path, params=None, body=None):
        """发一次请求并记录（失败回放用）。"""
        status, parsed = self.raw(method, path, params, body)
        self.calls.append({
            "method": method.upper(), "path": path,
            "params": params, "body": body, "status": status,
        })
        return status, parsed

    # ---------------- 断言辅助 ----------------
    def ok(self, method, path, params=None, body=None, label=""):
        """期望成功，返回 data。"""
        status, parsed = self.call(method, path, params, body)
        if status != 200:
            raise ApiError(f"{label or path} HTTP {status}：{parsed}")
        if isinstance(parsed, dict) and parsed.get("code") not in (200, None):
            raise ApiError(
                f"{label or path} 业务码 {parsed.get('code')}：{extract_message(parsed) or parsed}"
            )
        return parsed.get("data") if isinstance(parsed, dict) else parsed

    def reject(self, method, path, params=None, body=None, label=""):
        """期望被拒绝，返回 (业务码, 提示语)。HTTP 4xx/5xx 也算拒绝。"""
        status, parsed = self.call(method, path, params, body)
        if status == 200 and isinstance(parsed, dict) and parsed.get("code") in (200, None):
            raise ApiError(f"{label or path} 本应被拒绝，实际成功：{parsed}")
        if isinstance(parsed, dict):
            return parsed.get("code"), extract_message(parsed)
        return status, str(parsed)

    def probe(self, method, path, params=None, body=None):
        """探路：不判通过与否，返回原始 (status, body)。"""
        return self.call(method, path, params, body)


def default_client():
    return ApiClient()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    client = ApiClient()
    print("token 长度:", len(client.token))
    data = client.ok("GET", "/unit/getAllList", {"currentPage": 1, "pageSize": 5})
    print("unit/getAllList 前 1 条:", json.dumps(data[0], ensure_ascii=False) if data else data)
