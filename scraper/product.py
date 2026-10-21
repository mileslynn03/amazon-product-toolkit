"""从商品详情页或评论页读取真实商品信息，不猜测图片地址。"""
from __future__ import annotations
import json
from urllib.parse import urlsplit
from marketplaces import detail_url


def safe_image(url):
    if not isinstance(url, str):
        return ""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return url if parsed.scheme == "https" and (
        host == "m.media-amazon.com" or host.endswith(".media-amazon.com")
        or host.endswith(".images-amazon.com") or host.endswith(".ssl-images-amazon.com")
    ) else ""


def extract_product(page, asin, country):
    item = {"asin": asin, "country": country, "url": detail_url(asin, country),
            "title": "", "image": "", "brand": ""}
    for selector in ("#productTitle", '[data-hook="product-link"]',
                     "#cm_cr-product_info .product-title", "#cm_cr-product_info a.a-text-bold"):
        locator = page.locator(selector).first
        if locator.count():
            title = (locator.inner_text() or "").strip()
            if title:
                item["title"] = title
                break
    for selector in ("#landingImage", "#imgBlkFront", '[data-hook="cr-product-image"]',
                     "#cm_cr-product_info img", '[data-hook="product-image"] img'):
        locator = page.locator(selector).first
        if locator.count():
            for attribute in ("data-old-hires", "src"):
                image = safe_image(locator.get_attribute(attribute) or "")
                if image:
                    item["image"] = image
                    break
        if item["image"]:
            break
    for field, prop in (("title", "og:title"), ("image", "og:image")):
        if not item[field]:
            locator = page.locator(f'meta[property="{prop}"]').first
            if locator.count():
                value = locator.get_attribute("content") or ""
                item[field] = safe_image(value) if field == "image" else value
    for text in page.locator('script[type="application/ld+json"]').all_text_contents():
        try:
            data = json.loads(text)
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if "@graph" in candidate:
                    candidates.extend(candidate["@graph"])
                if candidate.get("@type") != "Product":
                    continue
                item["title"] = item["title"] or candidate.get("name", "")
                image = candidate.get("image", "")
                if isinstance(image, list):
                    image = image[0] if image else ""
                if isinstance(image, dict):
                    image = image.get("url", "")
                item["image"] = item["image"] or safe_image(image)
                brand = candidate.get("brand", "")
                item["brand"] = brand.get("name", "") if isinstance(brand, dict) else str(brand)
        except (ValueError, TypeError, AttributeError):
            continue
    brand = page.locator("#bylineInfo").first
    if not item["brand"] and brand.count():
        item["brand"] = (brand.inner_text() or "").strip()
    return item
