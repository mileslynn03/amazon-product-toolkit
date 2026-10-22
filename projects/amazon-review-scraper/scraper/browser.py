"""浏览器按线程隔离；会话文件和已验证登录分别记录。"""
from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from marketplaces import MARKETPLACES
from _runtime import DATA_HOME

BASE_DIR = DATA_HOME
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
_local = threading.local()
_session_lock = threading.Lock()
_session_marks = {}


def _storage_path(code):
    if code not in MARKETPLACES:
        raise ValueError("未知国家站点")
    return STORAGE_DIR / f"login_state_{code}.json"


def _auth_cookies(cookies):
    now = time.time()
    return [c for c in cookies if
            c.get("name", "").startswith(("at-", "sess-at-"))
            and c.get("value") and (c.get("expires", -1) <= 0 or c["expires"] > now)]


def session_status(code):
    path = _storage_path(code)
    try:
        stamp = path.stat().st_mtime_ns
        data = json.loads(path.read_text(encoding="utf-8"))
        cookies = data["cookies"]
        if not isinstance(cookies, list) or not _auth_cookies(cookies):
            return "expired"
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "invalid"
    with _session_lock:
        mark = _session_marks.get(code)
        return mark[1] if mark and mark[0] == stamp else "saved"


def mark_session(code, status):
    try:
        stamp = _storage_path(code).stat().st_mtime_ns
    except OSError:
        return
    with _session_lock:
        _session_marks[code] = (stamp, status)


def is_logged_in(code):
    """表示存在可尝试使用的会话，不保证服务端认可。"""
    return session_status(code) in {"saved", "verified"}


def launch(headless=None, country=None):
    if getattr(_local, "browser", None) is not None and not _local.browser.is_connected():
        try:
            close()
        except Exception:
            pass
    if getattr(_local, "browser", None) is None:
        if headless is None:
            headless = os.environ.get("AMAZON_REVIEW_HEADLESS", "0") == "1"
        try:
            _local.pw = sync_playwright().start()
            _local.browser = _local.pw.chromium.launch(headless=headless)
            _local.context = _local.browser.new_context(
                viewport={"width": 1366, "height": 768}, locale="en-US")
            _local.page = _local.context.new_page()
            _local.contexts = {}
        except Exception:
            close()
            raise
    elif _local.page.is_closed():
        _local.page = _local.context.new_page()
    return load_storage_state(country) if country else _local.page


def load_storage_state(code):
    path = _storage_path(code)
    stamp = path.stat().st_mtime_ns if path.exists() else None
    cache = _local.contexts
    saved = cache.get(code)
    if saved and saved["stamp"] == stamp:
        _local.context, _local.page = saved["context"], saved["page"]
        if _local.page.is_closed():
            _local.page = _local.context.new_page()
            saved["page"] = _local.page
    else:
        options = {"storage_state": str(path)} if path.exists() else {}
        context = _local.browser.new_context(viewport={"width": 1366, "height": 768}, locale="en-US", **options)
        old_context = saved["context"] if saved else None
        if not cache and getattr(_local, "country", None) is None:
            old_context = _local.context
        _local.context, _local.page = context, context.new_page()
        cache[code] = {"context": context, "page": _local.page, "stamp": stamp}
        if old_context is not None:
            old_context.close()
    _local.country, _local.storage_stamp = code, stamp
    return current_page()


def save_storage_state(code):
    context = current_context()
    if context is None or not _auth_cookies(context.cookies()):
        raise RuntimeError("未检测到有效的账号登录，请完成登录后重试")
    path = _storage_path(code)
    temp = path.with_suffix(".tmp")
    try:
        context.storage_state(path=str(temp))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    mark_session(code, "verified")
    _local.country = code
    _local.storage_stamp = path.stat().st_mtime_ns
    _local.contexts[code] = {"context": context, "page": _local.page, "stamp": _local.storage_stamp}


def close():
    try:
        if getattr(_local, "browser", None):
            _local.browser.close()
    finally:
        try:
            if getattr(_local, "pw", None):
                _local.pw.stop()
        finally:
            _local.browser = _local.context = _local.page = _local.pw = None
            _local.country = _local.storage_stamp = None
            _local.contexts = {}


def current_page():
    return getattr(_local, "page", None)


def is_running():
    instance = getattr(_local, "browser", None)
    return instance is not None and instance.is_connected()


def current_context():
    return getattr(_local, "context", None)


def set_current_page(page):
    if page.context != current_context():
        raise RuntimeError("登录页面不属于当前浏览器会话")
    _local.page = page
    code = getattr(_local, "country", None)
    if code in getattr(_local, "contexts", {}):
        _local.contexts[code]["page"] = page
