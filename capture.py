"""采集结果合并、数量摘要和结束原因；统计按组合及最近一次尝试计算。"""
from __future__ import annotations
import copy
import hashlib
import json

COMPLETE_STATUSES = {"success", "empty"}
ACTIVE_STATUSES = {"pending", "running"}
STAT_FIELDS = ("pages", "read", "duplicates", "foreign", "unknown", "over_limit", "new", "recovered", "kept")
STOP_REASONS = {
    "limit_reached":"达到采集上限", "no_next_page":"页面未提供下一页",
    "quick_sample":"详情页扫描完成", "no_reviews":"页面明确无评论",
    "cancelled":"手动停止", "not_started":"未执行", "interrupted":"意外中断",
    "blocked":"访问受限", "login_required":"站点要求登录", "review_auth_required":"评论页需再次认证",
    "http_error":"页面请求异常", "network_error":"网络请求异常", "parse_error":"评论解析失败",
    "pagination_error":"翻页未完成", "unexpected_error":"任务执行异常", "unknown":"未记录结束原因",
}


def review_key(review):
    return review.get("review_id") or hashlib.sha256(json.dumps(
        [review.get(k,"") for k in ("title","body","author","date","rating")],
        ensure_ascii=False).encode()).hexdigest()


def merge_reviews(existing, incoming, cap=None):
    merged = {}
    for review in [*existing,*incoming]:
        key = review_key(review)
        old = merged.get(key,{})
        item = {**old, **copy.deepcopy(review)}
        if old and (old.get("title",""),old.get("body","")) != (review.get("title",""),review.get("body","")):
            item.pop("translation",None)
        merged[key] = item
    values = list(merged.values())
    return values[:cap] if cap is not None else values


def empty_stats(recovered=0):
    return {**dict.fromkeys(STAT_FIELDS,0),"recovered":recovered,"kept":recovered}


def capture_summary(outcomes, reviews):
    recorded = [o for o in outcomes.values() if o.get("stats_known")]
    totals = {field:sum(o.get("stats",{}).get(field,0) for o in recorded) for field in STAT_FIELDS}
    return {**totals,"recorded_tasks":len(recorded),"unique_reviews":len(reviews)}
