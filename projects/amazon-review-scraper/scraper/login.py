"""手动登录支持取消、超时和独立标签页验证。"""
from __future__ import annotations
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from . import browser
from .crawler import check_page, _explicitly_empty
from .errors import CrawlError
from marketplaces import homepage_url, get_domain, reviews_url


class LoginChallenge(CrawlError):
    def __init__(self, message, page):
        super().__init__("review_auth_required", message)
        self.page = page


def _check_window(page, cancel_event):
    if cancel_event.is_set():
        raise RuntimeError("登录已取消")
    if page.is_closed():
        raise RuntimeError("登录窗口已关闭，请重新打开")


def _navigation_interrupted(exc):
    message = str(exc).lower()
    return any(marker in message for marker in (
        "interrupted by another navigation", "err_aborted",
        "execution context was destroyed", "because of a navigation"))


def _wait_stable(page, cancel_event, timeout=15, quiet_seconds=.8):
    """等待最终文档稳定，不依赖可能被前端跳转中断的旧导航事件。"""
    deadline = time.monotonic() + timeout
    previous = None
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        _check_window(page, cancel_event)
        try:
            current = page.evaluate("({url: location.href, ready: document.readyState})")
            if current["url"] != previous or current["ready"] == "loading":
                previous = current["url"]
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= quiet_seconds:
                return
        except PlaywrightError as exc:
            if not _navigation_interrupted(exc):
                raise
            previous = None
            stable_since = time.monotonic()
        page.wait_for_timeout(100)
    raise RuntimeError("登录页面仍在跳转或加载，请等页面稳定后再次点击保存")


def _navigate(page, url, cancel_event):
    latest = []

    def record(response):
        if response.request.is_navigation_request() and response.frame == page.main_frame:
            latest[:] = [response]

    page.on("response", record)
    try:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightError as exc:
            if not _navigation_interrupted(exc):
                raise
            # 登录成功后的前端跳转可以取消 goto；验证实际到达的最终页面。
        _wait_stable(page, cancel_event)
        return latest[-1] if latest and latest[-1].url == page.url else None
    finally:
        page.remove_listener("response", record)


def _verify_login(page, code, cancel_event, asin=None):
    _wait_stable(page, cancel_event)
    verification = page.context.new_page()
    try:
        target = reviews_url(asin, code) if asin else f"https://{get_domain(code)}/gp/css/homepage.html"
        response = _navigate(verification, target, cancel_event)
        if urlparse(verification.url).hostname != get_domain(code):
            raise RuntimeError("登录验证跳转到了其他站点，请确认当前国家站点后再保存")
        check_page(verification, code, response, invalidate_session=False)
        if asin:
            verification.locator('[data-hook="review"], [data-hook="no-reviews-message"], #cm_cr-review_list').first.wait_for(state="attached", timeout=10000)
            if not verification.locator('[data-hook="review"]').count() and not _explicitly_empty(verification):
                raise RuntimeError("尚未确认评论列表页可读取，请在此页面完成认证后再次保存")
        else:
            signed_in = verification.locator('a[href*="sign-out"], #nav-item-signout').count()
            if not signed_in or verification.locator('a[data-nav-role="signin"]').count():
                raise RuntimeError("账户首页可访问，但尚未确认账号登录；请先输入商品 ASIN，再验证对应评论页")
        _check_window(page, cancel_event)
    except Exception as exc:
        if cancel_event.is_set() or page.is_closed():
            if not verification.is_closed():
                verification.close()
            raise
        verification.bring_to_front()
        message = ("评论列表页还要求再次认证，请在此页面完成登录或验证，再回到工具点击保存"
                   if asin and isinstance(exc, CrawlError) and exc.status == "login_required"
                   else _retry_message(exc))
        raise LoginChallenge(message, verification) from exc
    else:
        if not verification.is_closed():
            verification.close()
        if not page.is_closed():
            page.bring_to_front()


def _retry_message(exc):
    if isinstance(exc, PlaywrightError):
        if _navigation_interrupted(exc):
            return "登录页面仍在跳转，请等浏览器页面稳定后再次点击保存"
        return "登录验证页面加载失败，请检查浏览器页面和网络后再次点击保存"
    return str(exc)


def run_login(code, ready_event, done_event, on_ready=None, cancel_event=None,
              timeout=600, on_retry=None, verification_asin=None, keep_browser=False):
    cancel_event = cancel_event or threading.Event()
    saved = False
    try:
        page = browser.launch(country=code)
        if browser.is_logged_in(code):
            page = browser.load_storage_state(code)
        target = reviews_url(verification_asin, code) if verification_asin else homepage_url(code)
        _navigate(page, target, cancel_event)
        ready_event.set()
        if on_ready:
            on_ready()
        deadline = time.monotonic() + timeout
        while True:
            while not done_event.is_set():
                _check_window(page, cancel_event)
                if time.monotonic() >= deadline:
                    raise RuntimeError("登录等待超时（10 分钟），请重新打开登录窗口")
                # 泵送 Playwright 事件，及时处理用户登录后的导航与关闭窗口。
                page.wait_for_timeout(100)
            done_event.clear()
            _check_window(page, cancel_event)
            try:
                _verify_login(page, code, cancel_event, verification_asin)
                _check_window(page, cancel_event)
                browser.save_storage_state(code)
                saved = True
                return
            except (PlaywrightError, RuntimeError) as exc:
                if isinstance(exc, LoginChallenge) and on_retry is not None:
                    previous = page
                    page = exc.page
                    browser.set_current_page(page)
                    if not previous.is_closed():
                        previous.close()
                _check_window(page, cancel_event)
                if on_retry is None:
                    raise
                on_retry(_retry_message(exc))
    finally:
        ready_event.set()
        if not saved or not keep_browser:
            browser.close()
