"""评论抓取：识别阻塞原因、保留部分结果，兼容追加和替换分页。"""
from __future__ import annotations
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from . import browser
from .errors import CrawlError
from .parser import parse_page_reviews
from .product import extract_product
from marketplaces import reviews_url, detail_url
from capture import review_key, merge_reviews, empty_stats

REVIEW_SELECTOR = '[data-hook="review"]'


def _cancelled(event):
    return event is not None and event.is_set()


def check_page(page, country, response=None, invalidate_session=True):
    """验证错误页；HTTP 200 的验证页仍应视为失败。"""
    path = urlparse(page.url).path.lower()
    if "signin" in path or page.locator('form[name="signIn"], #ap_email').count():
        if invalidate_session:
            browser.mark_session(country, "expired")
        raise CrawlError("login_required", "登录已失效或站点要求登录，请重新登录并保存会话")
    captcha = page.locator('form[action*="validateCaptcha"], #captchacharacters').count()
    title = (page.title() or "").lower()
    if captcha or "robot check" in title or "captcha" in title:
        raise CrawlError("blocked", "亚马逊要求人工验证，请通过左侧登录窗口完成验证和登录后重试")
    status = response.status if response is not None else None
    if status in {403, 429, 503}:
        raise CrawlError("blocked", f"亚马逊暂时限制访问（HTTP {status}），请稍后重试")
    if status is not None and status >= 400:
        raise CrawlError("http_error", f"商品页面访问失败（HTTP {status}），请确认 ASIN 和国家站点")


def _check_cancel(event, results=None):
    if _cancelled(event):
        raise CrawlError("cancelled", "用户已停止，已保留抓取结果", results)


def _wait_reviews(page, country, cancel_event, timeout=12, invalidate_session=True):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _check_cancel(cancel_event)
        check_page(page, country, invalidate_session=invalidate_session)
        if page.locator(REVIEW_SELECTOR).count():
            return True
        page.wait_for_timeout(200)
    return False


def _explicitly_empty(page):
    # 只有亚马逊明确的无评论文案，才能认定为空，不能将选择器缺失视为空。
    text = page.locator('[data-hook="no-reviews-message"], #noReviews, #cm_cr-review_list').all_inner_texts()
    messages = ("no customer reviews", "no reviews yet", "no reviews match",
                "there are no reviews", "no customer reviews match",
                "まだカスタマーレビューはありません", "尚无评论", "暂无评论")
    return any(message in " ".join(text).lower() for message in messages)


def _next_button(page):
    for selector in ('[data-hook="show-more-button"]', 'li.a-last:not(.a-disabled) a'):
        for button in page.locator(selector).all():
            if button.is_visible() and button.is_enabled() and button.get_attribute("aria-disabled") != "true":
                return button
    return None


def _signature(page):
    return page.locator(REVIEW_SELECTOR).evaluate_all(
        "(nodes) => nodes.map(n => [n.id, n.innerText])")


def _wait_page_change(page, before, country, cancel_event, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _check_cancel(cancel_event)
        check_page(page, country, invalidate_session=False)
        current = _signature(page)
        if current and current != before:
            return True
        page.wait_for_timeout(200)
    return False


def _review_key(review):
    return review_key(review)


def _goto(page, url, country, invalidate_session=True):
    response = page.goto(url, wait_until="commit", timeout=30000)
    if response is not None and response.status >= 400:
        check_page(page, country, response, invalidate_session=invalidate_session)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        # 个别资源延迟不妨碍已渲染的评论读取，后续仍检查节点与错误页。
        pass
    check_page(page, country, response, invalidate_session=invalidate_session)


def _prepare_reviews(page, task, cancel_event):
    if page.locator(REVIEW_SELECTOR).count():
        return
    if task["mode"] == "quick":
        for selector in ('#cm-cr-dp-review-list', '#reviewsMedley', '#customerReviews'):
            locator = page.locator(selector).first
            if locator.count():
                locator.scroll_into_view_if_needed(timeout=3000)
                break
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    if not _wait_reviews(page, task["country"], cancel_event,
                         invalidate_session=task["mode"] != "deep"):
        if _explicitly_empty(page):
            return
        raise CrawlError("parse_error", "页面未找到评论，可能加载不完整或页面结构变化；未将其判为抓取成功")


def crawl(task, on_progress=None, cancel_event: threading.Event | None = None, keep_browser=False,
          on_product=None, fetch_product=True, on_checkpoint=None, seed_reviews=None):
    seen = set()
    local_only = task.get("local_only", False)
    country, asin = task["country"], task["asin"]
    deep = task["mode"] == "deep"
    cap = task.get("cap") if deep else None
    results = merge_reviews([], seed_reviews or [])
    retained = {_review_key(r) for r in results}
    stats = empty_stats(len(results))
    stop_reason = ""
    page_no = 0
    accessing_reviews = False

    def progress(message):
        if on_progress:
            on_progress(asin, page_no, len(results), message)

    def checkpoint():
        if on_checkpoint:
            on_checkpoint(list(results), {"stats":{**stats,"pages":page_no,"kept":len(results)},
                                          "stop_reason":stop_reason})

    try:
        _check_cancel(cancel_event)
        if cap is not None and len(results) >= cap:
            stop_reason = "limit_reached"
            return results
        if deep and not browser.is_logged_in(country):
            raise CrawlError("login_required", "当前站点没有可用会话，请先登录并保存")
        progress("正在打开商品页面…")
        page = browser.launch(country=country)
        # 快速模式也复用已保存会话，便于登录后访问详情页。
        if browser.is_logged_in(country):
            page = browser.load_storage_state(country)
        if deep and on_product is not None and fetch_product:
            info_page = page.context.new_page()
            try:
                _goto(info_page, detail_url(asin, country), country, invalidate_session=False)
                on_product(extract_product(info_page, asin, country))
            except Exception:
                pass  # 商品信息不可读不影响评论任务。
            finally:
                info_page.close()
        url = reviews_url(asin, country, task.get("star_key")) if deep else detail_url(asin, country)
        accessing_reviews = deep
        _goto(page, url, country, invalidate_session=not deep)
        _check_cancel(cancel_event)
        _prepare_reviews(page, task, cancel_event)
        if on_product is not None:
            on_product(extract_product(page, asin, country))
        if not page.locator(REVIEW_SELECTOR).count():
            stop_reason = "no_reviews"
            return results
        while True:
            _check_cancel(cancel_event, results)
            check_page(page, country, invalidate_session=not deep)
            page_no += 1
            items = parse_page_reviews(page, asin, country, page_no)
            stats["read"] += len(items)
            added = new_items = 0
            for review in items:
                key = _review_key(review)
                if key in seen:
                    stats["duplicates"] += 1
                    continue
                seen.add(key)
                new_items += 1
                if local_only and review.get("review_country") != country:
                    stats["foreign" if review.get("review_country") else "unknown"] += 1
                    continue
                if key in retained:
                    stats["duplicates"] += 1
                    results = merge_reviews(results,[review])
                    continue
                if cap is not None and len(results) >= cap:
                    stats["over_limit"] += 1
                    continue
                results.append(review)
                retained.add(key)
                stats["new"] += 1
                added += 1
            if not items:
                raise CrawlError("parse_error", "评论节点存在，但无法读取有效评论内容", results)
            excluded = stats["foreign"] + stats["unknown"]
            progress(f"第 {page_no} 批新增 {added} 条，累计剔除 {excluded} 条非本站或地区未知的评论" if local_only else f"第 {page_no} 批新增 {added} 条")
            checkpoint()
            if deep:
                browser.mark_session(country, "verified")
            if cap is not None and len(results) >= cap:
                stop_reason = "limit_reached"
                progress(f"已达到上限 {cap} 条")
                break
            if not deep:
                stop_reason = "quick_sample"
                break
            button = _next_button(page)
            if button is None:
                stop_reason = "no_next_page"
                break
            if not new_items:
                raise CrawlError("pagination_error", "翻页后只有重复评论，已停止并保留结果", results)
            before = _signature(page)
            button.scroll_into_view_if_needed(timeout=5000)
            button.click(timeout=10000)
            if not _wait_page_change(page, before, country, cancel_event):
                raise CrawlError("pagination_error", "翻页后未检测到新评论，请稍后重试；已保留结果", results)
            # 限速，同时让停止信号可以及时生效。
            if cancel_event is not None:
                if cancel_event.wait(1):
                    _check_cancel(cancel_event, results)
            else:
                page.wait_for_timeout(1000)
        return results
    except CrawlError as exc:
        stop_reason = exc.status
        if accessing_reviews and exc.status == "login_required":
            stop_reason = "review_auth_required"
            raise CrawlError("review_auth_required", "评论列表页要求再次认证；请在站点会话中登录，在评论页完成认证后再次保存", results or exc.reviews) from exc
        if results and not exc.reviews:
            exc.reviews = list(results)
        raise
    except Exception as exc:
        stop_reason = "network_error"
        raise CrawlError("network_error", f"浏览器或页面请求失败：{exc}", results) from exc
    finally:
        try:
            checkpoint()
        finally:
            if not keep_browser:
                try:
                    browser.close()
                except Exception:
                    pass


def fetch_product_info(asin, country):
    # 补读资料自行启动的浏览器必须回收；已有登录窗口留给后续采集复用。
    owns_browser = not browser.is_running()
    info_page = None
    try:
        page = browser.launch(country=country)
        info_page = page.context.new_page()
        _goto(info_page, detail_url(asin, country), country, invalidate_session=False)
        try:
            info_page.locator('#productTitle, #landingImage, #imgBlkFront').first.wait_for(state="attached", timeout=8000)
        except PlaywrightTimeoutError:
            pass
        return extract_product(info_page, asin, country)
    finally:
        try:
            if info_page is not None:
                info_page.close()
        finally:
            if owns_browser:
                browser.close()
