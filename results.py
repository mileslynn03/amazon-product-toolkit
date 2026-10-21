"""采集组合的标识与评论去重；站点数据始终独立。"""
from __future__ import annotations
import hashlib
import json
from scraper.origin import origin_fields


def task_key(task):
    return task.get("id") or task["asin"]


def product_key(asin, country):
    return f"{asin}:{country}"


def combination_key(asin, country, star_key):
    from marketplaces import STAR_FILTERS
    return f"{asin}:{country}:{STAR_FILTERS.get(star_key, 'all_stars')}"


def unique_reviews(tasks, results):
    merged = {}
    for task in tasks:
        key = task_key(task)
        for raw in results.get(key, []):
            review = {**raw, **origin_fields(raw.get("date", "")), "asin": task["asin"], "country": task["country"]}
            fingerprint = review.get("review_id") or hashlib.sha256(
                json.dumps([review.get(field, "") for field in
                            ("title", "body", "author", "date", "rating")],
                           ensure_ascii=False).encode("utf-8")).hexdigest()
            identity = (review["asin"], review["country"], fingerprint)
            if identity not in merged:
                merged[identity] = {**review, "matched_filters": [], "task_ids": []}
            item = merged[identity]
            star = task.get("star_key") or "全部"
            if star not in item["matched_filters"]:
                item["matched_filters"].append(star)
            if key not in item["task_ids"]:
                item["task_ids"].append(key)
    return list(merged.values())
