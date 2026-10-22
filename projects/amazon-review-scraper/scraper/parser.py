"""评论 HTML 解析：把单条评论节点解析为结构化 dict。

亚马逊评论 DOM 会随站点/时间变化，所有选择器集中在此，便于调整。
解析尽量容错：优先 data-hook 属性，取值失败时回退到更宽泛的选择器。
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator
from .origin import origin_fields


def _text(locator: Locator, selector: str) -> str:
    """安全取文本：找不到或异常时返回空字符串。"""
    try:
        inner = locator.locator(selector).first
        if inner.count() == 0:
            return ""
        return (inner.inner_text() or "").strip()
    except Exception:
        return ""


def _rating_from_text(text: str) -> float:
    """从 "5.0 out of 5 stars" 之类文本提取数值。"""
    text = text or ""
    m = re.search(r"5\s*つ星のうち\s*(\d+(?:[.,]\d+)?)", text)
    if not m:
        m = re.search(r"(\d+(?:[.,]\d+)?)", text)
    rating = float(m.group(1).replace(",", ".")) if m else 0.0
    return rating if 0 <= rating <= 5 else 0.0


def _review_title(review: Locator) -> str:
    """评论标题。

    新版列表页把星级图标（span.a-icon-alt，文本形如 "5.0 out of 5 stars"）也
    放进了 review-title 链接里，直接取第一个 span 会拿到星级文本。这里改为取
    最后一个非空的直接子 span；详情页内嵌评论则回退到 reviewTitle。
    """
    # 列表页：最后一个非空直接子 span（跳过图标/空 span）
    try:
        spans = review.locator('[data-hook="review-title"] > span')
        n = spans.count()
        for i in range(n - 1, -1, -1):
            t = (spans.nth(i).inner_text() or "").strip()
            if t:
                return t
    except Exception:
        pass
    # 兜底：详情页内嵌评论（h5[data-hook="reviewTitle"]）或旧版布局
    for sel in ('[data-hook="reviewTitle"]', 'h5[data-hook="reviewTitle"]', '[data-hook="review-title"]'):
        t = _text(review, sel)
        if t:
            return t
    return ""


def parse_review(review: Locator, asin: str, country: str, page: int) -> dict:
    """解析单条评论节点。

    review: 一个 data-hook="review" 的 Locator
    返回结构化 dict。
    """
    # 标题：列表页用 review-title，详情页内嵌评论用 reviewTitle（在 h5 里）
    title = _review_title(review)

    # 正文：列表页 review-body，详情页 reviewText
    body = (
        _text(review, '[data-hook="review-body"]')
        or _text(review, '[data-hook="reviewText"]')
    )

    # 作者
    author = _text(review, "span.a-profile-name")

    # 日期（不同站点格式不同，保留原文）
    date = _text(review, '[data-hook="review-date"]')

    # 星标：优先 icon-alt 文本，回退到 class 里的 "a-star-4" 之类
    rating_text = (_text(review, '[data-hook="review-star-rating"] .a-icon-alt')
                   or _text(review, '[data-hook="cmps-review-star-rating"] .a-icon-alt')
                   or _text(review, '.a-icon-star .a-icon-alt'))
    rating = _rating_from_text(rating_text)
    if rating == 0.0:
        try:
            icon = review.locator('[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]').first
            cls = (icon.get_attribute("class") or "") if icon.count() else ""
            m = re.search(r"a-star-(\d+)", cls)
            if m:
                rating = float(m.group(1))
        except Exception:
            pass

    # 已购认证（Verified Purchase / 已验证购买）
    verified = False
    try:
        avp = review.locator('[data-hook="avp-badge"]').first
        if avp.count() > 0:
            verified = True
    except Exception:
        pass

    # 有帮助数（如 "1,234 people found this helpful"）
    helpful = _text(review, '[data-hook="helpful-vote-statement"]')

    return {
        "review_id": review.get_attribute("id") or "",
        "asin": asin,
        "country": country,
        "rating": rating,
        "title": title,
        "body": body,
        "author": author,
        "date": date,
        **origin_fields(date),
        "verified": verified,
        "helpful": helpful,
        "page": page,
    }


def parse_page_reviews(page, asin: str, country: str, page_no: int, start: int = 0) -> list[dict]:
    """解析当前评论页上的评论节点。

    start: 起始索引。新版亚马逊「加载更多」是 append 模型——点一次按钮，
    下一页评论被追加到同一个 DOM，节点从头累加。此时传入 start 可只解析
    本批新增节点，避免重复采集已解析过的评论。
    """
    reviews: list[dict] = []
    try:
        nodes = page.locator('[data-hook="review"]')
        count = nodes.count()
    except Exception:
        return reviews

    for i in range(start, count):
        try:
            node = nodes.nth(i)
            item = parse_review(node, asin, country, page_no)
            if item["title"] or item["body"]:
                reviews.append(item)
        except Exception:
            continue
    return reviews
