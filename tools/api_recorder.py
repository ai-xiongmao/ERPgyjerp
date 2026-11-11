"""接口抓取器：在 MyTest 浏览器里监听 XHR/fetch，把三个页面的接口落盘。

只做只读动作（页面加载 / 查询 / 翻页 / 打开新增弹窗后取消），
不保存任何业务数据，不点删除。

用法：
    ./.venv/Scripts/python.exe tools/api_recorder.py            # 默认三个页面全抓
    ./.venv/Scripts/python.exe tools/api_recorder.py unit       # 只抓多单位

输出：
    tools/api_dump/dump_<时间戳>.json    全量请求/响应（含 headers，注意脱敏）
    tools/api_dump/dump_<时间戳>.md      按接口去重的清单
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from config import BASE_URL  # noqa: E402
from framework.browser import connect  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "api_dump"

PAGES = {
    "unit": ("/system/unit", "多单位"),
    "product": ("/material/material", "商品信息"),
    "depot": ("/system/depot", "仓库信息"),
}

# 静态资源不记
SKIP_TYPES = {"image", "font", "stylesheet", "media", "script"}

# 业务接口前缀（jshERP 后端统一挂在 /jshERP-boot 下）
API_PREFIX = "/jshERP-boot/"

# 敏感头脱敏
SENSITIVE = ("authorization", "cookie", "token", "x-token", "x-access-token")


class Recorder:
    def __init__(self, page):
        self.page = page
        self.items = []
        self._pending = {}
        page.on("request", self._on_request)
        page.on("response", self._on_response)

    def _on_request(self, req):
        if API_PREFIX not in req.url:
            return
        self._pending[req] = {
            "method": req.method,
            "url": req.url,
            "resource_type": req.resource_type,
            "headers": {k.lower(): v for k, v in req.headers.items()},
            "post_data": req.post_data,
            "ts": time.time(),
        }

    def _on_response(self, resp):
        req = resp.request
        item = self._pending.pop(req, None)
        if item is None:
            return
        item["status"] = resp.status
        item["content_type"] = (resp.headers or {}).get("content-type", "")
        item["resp_headers"] = dict(resp.headers or {})
        # JSON 接口才取 body；binary / 静态资源跳过
        if "json" in item["content_type"] or item["url"].split("?")[0].endswith((".json",)):
            try:
                item["resp_body"] = resp.text()
            except Exception as exc:  # noqa: BLE001
                item["resp_body"] = None
                item["resp_error"] = str(exc)
        self.items.append(item)

    def drain(self):
        """把拿到的请求交出去并按接口聚合。"""
        return self.items


def mask(headers):
    out = {}
    for k, v in headers.items():
        out[k] = ("<masked len=%d>" % len(v)) if k.lower() in SENSITIVE else v
    return out


def norm_key(item):
    """接口主键：method + 去掉 query 的 path。"""
    path = item["url"].split("?")[0].replace(BASE_URL, "")
    return f"{item['method']} {path}"


def brief_body(text, limit=1200):
    if not text:
        return ""
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + f"…(共{len(text)}字)"
    return text


def summarize(items, dump_path):
    """按接口去重生成 markdown。"""
    groups = {}
    for it in items:
        if "status" not in it:
            continue
        key = norm_key(it)
        groups.setdefault(key, []).append(it)

    lines = [f"# 接口抓取清单（{datetime.now():%Y-%m-%d %H:%M}）", "",
             f"原始数据：`{dump_path.name}`　共 {len(items)} 个请求 / {len(groups)} 个接口", ""]
    for key in sorted(groups):
        arr = groups[key]
        first = arr[0]
        lines.append(f"## {key}")
        lines.append("")
        lines.append(f"- 次数：{len(arr)}　状态：{first['status']}　类型：{first['resource_type']}")
        if "?" in first["url"]:
            lines.append(f"- Query：`{first['url'].split('?', 1)[1]}`")
        if first.get("post_data"):
            lines.append(f"- 请求体：`{brief_body(first['post_data'], 600)}`")
        auth = first["headers"].get("authorization") or first["headers"].get("x-token")
        if auth:
            lines.append(f"- 认证头：存在（长度 {len(auth)}，{list(first['headers'].keys())[:6]}）")
        if first.get("resp_body"):
            lines.append(f"- 响应样例：`{brief_body(first['resp_body'])}`")
        lines.append("")
    return "\n".join(lines)


def grab(page, rec, path, name):
    """单页：加载 → 查询 → 翻页，全部只读。"""
    print(f"  打开 {name} {path}")
    page.goto(BASE_URL + path, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # 查询：输入框用 placeholder 兜住，输入一个必然不存在的关键词，不落库只查询
    try:
        box = page.locator("input[placeholder*='请输入']").first
        if box.count():
            box.fill("__接口抓取__")
            page.wait_for_timeout(300)
            btn = page.locator("button:has-text('查')").first
            if btn.count():
                btn.click()
                page.wait_for_timeout(1500)
            print("    已执行查询")
    except Exception as exc:  # noqa: BLE001
        print(f"    查询跳过：{exc}")

    # 重置，恢复列表
    try:
        btn = page.locator("button:has-text('重')").first
        if btn.count():
            btn.click()
            page.wait_for_timeout(1200)
    except Exception:  # noqa: BLE001
        pass

    # 翻页
    try:
        p2 = page.locator(".ant-pagination-item-2").first
        if p2.count():
            p2.click()
            page.wait_for_timeout(1500)
            print("    已翻到第 2 页")
    except Exception as exc:  # noqa: BLE001
        print(f"    翻页跳过：{exc}")

    # 打开新增弹窗 → 直接取消（触发下拉/字典类接口，不落库）
    try:
        add = page.locator(".ant-card:has(.ant-table) button:has-text('新增')").first
        if add.count():
            add.click()
            page.wait_for_timeout(1800)
            cancel = page.locator(".ant-modal:visible button:has-text('取')").first
            if cancel.count():
                cancel.click()
                page.wait_for_timeout(600)
            print("    已打开新增弹窗并取消")
    except Exception as exc:  # noqa: BLE001
        print(f"    新增弹窗跳过：{exc}")


def main():
    only = sys.argv[1:] or list(PAGES)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as page:
        rec = Recorder(page)
        for key in only:
            if key not in PAGES:
                print(f"未知页面：{key}")
                continue
            path, name = PAGES[key]
            grab(page, rec, path, name)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump = OUT_DIR / f"dump_{stamp}.json"
        items = rec.drain()
        for it in items:
            it["headers"] = mask(it["headers"])
        dump.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        md = OUT_DIR / f"dump_{stamp}.md"
        md.write_text(summarize(items, dump), encoding="utf-8")
        print(f"\n捕获 {len(items)} 个请求")
        print(f"原始：{dump}")
        print(f"清单：{md}")


if __name__ == "__main__":
    main()
