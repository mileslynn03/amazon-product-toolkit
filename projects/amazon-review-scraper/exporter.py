"""导出组合总览，以及按商品和国家合并去重后的评论明细。"""
from __future__ import annotations
import io
from datetime import datetime
import pandas as pd
from marketplaces import get_domain, get_name
from results import task_key, product_key, unique_reviews
from capture import STOP_REASONS


def _safe_sheet_name(name):
    for ch in r'[]:*?/\\':
        name = name.replace(ch, "_")
    return name[:31]


def _safe_text(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def build_excel(tasks, results, outcomes=None, products=None):
    outcomes, products = outcomes or {}, products or {}
    output = io.BytesIO()
    overview = []
    for task in tasks:
        key = task_key(task)
        reviews = results.get(key, [])
        ratings = [r.get("rating", 0) for r in reviews if r.get("rating", 0) > 0]
        outcome = outcomes.get(key, {})
        product = products.get(product_key(task["asin"], task["country"]), {})
        overview.append({
            "ASIN": task["asin"], "商品名称": product.get("title", ""),
            "国家/地区": get_name(task["country"]), "站点域名": get_domain(task["country"]),
            "模式": "深度抓取" if task.get("mode") == "deep" else "快速扫描",
            "星级筛选": task.get("star_key") or "全部", "抓取条数": len(reviews),
            "评价来源": "仅本站国家/地区" if task.get("local_only") else "全部地区",
            "任务状态": outcome.get("status", "pending"),
            "状态说明": outcome.get("message", "尚未完成"),
            "结束原因": STOP_REASONS.get(outcome.get("stop_reason"),"未记录结束原因"),
            "执行轮次":outcome.get("attempt",1),
            **{label:outcome.get("stats",{}).get(field,0) if outcome.get("stats_known") else None
               for field,label in {"pages":"本轮读取页数","read":"本轮读取条目","duplicates":"本轮重复条目",
                   "foreign":"本轮非本站剔除","unknown":"本轮地区未知剔除","over_limit":"本轮超上限条目",
                   "new":"本轮新增评论","recovered":"本轮沿用评论","kept":"组合保留评论"}.items()},
            "平均星标": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    unique = unique_reviews(tasks, results)
    groups = {}
    for task in tasks:
        groups.setdefault((task["asin"], task["country"]), [])
    for review in unique:
        groups[(review["asin"], review["country"])].append(review)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        writer.book.properties.creator = "Amazon Product Toolkit"
        writer.book.properties.title = "亚马逊商品工具箱 · 评论采集"
        frame = pd.DataFrame(overview).apply(lambda column: column.map(_safe_text))
        frame.to_excel(writer, sheet_name="总览", index=False)
        multiple_markets = len({country for asin, country in groups}) > 1
        for (asin, country), reviews in groups.items():
            rows = [{
                "ASIN": asin, "国家/地区": get_name(country), "评论 ID": r.get("review_id", ""),
                "星级": r.get("rating", 0), "标题": r.get("title", ""),
                "译文标题": (r.get("translation") or {}).get("title", ""),
                "正文": r.get("body", ""), "译文正文": (r.get("translation") or {}).get("body", ""),
                "翻译目标语言": (r.get("translation") or {}).get("target_language", ""),
                "翻译状态": {"success":"已翻译","failed":"翻译失败"}.get((r.get("translation") or {}).get("status"),"未翻译"),
                "翻译说明": (r.get("translation") or {}).get("error", ""),
                "翻译模型": (r.get("translation") or {}).get("model", ""),
                "翻译接口协议": {"openai":"OpenAI Chat Completions","anthropic":"Anthropic Messages"}.get((r.get("translation") or {}).get("provider","openai"),"") if r.get("translation") else "",
                "作者": r.get("author", ""), "日期": r.get("date", ""),
                "评价标注地区": get_name(r["review_country"]) if r.get("review_country") else r.get("review_country_name") or "未识别",
                "评价地区代码": r.get("review_country", ""),
                "已购认证": "是" if r.get("verified") else "否", "有帮助数": r.get("helpful", ""),
                "匹配筛选": "、".join(r.get("matched_filters", [])), "页码": r.get("page", 1),
            } for r in reviews]
            if not rows:
                messages = [outcomes.get(task_key(t), {}).get("message", "尚未完成")
                            for t in tasks if t["asin"] == asin and t["country"] == country]
                rows = [{"ASIN": asin, "国家/地区": get_name(country), "备注": "；".join(dict.fromkeys(messages))}]
            name = f"{asin}_{country}" if multiple_markets else asin
            pd.DataFrame(rows).apply(lambda column: column.map(_safe_text)).to_excel(writer, sheet_name=_safe_sheet_name(name), index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            from openpyxl.styles import Font, PatternFill, Alignment
            for cell in sheet[1]:
                cell.fill = PatternFill("solid", fgColor="183C39")
                cell.font = Font(color="FFFFFF", bold=True)
                cell.alignment = Alignment(vertical="center")
            sheet.row_dimensions[1].height = 26
            for column in sheet.columns:
                width = min(48, max(14, max(len(str(cell.value or "")) for cell in list(column)[:40]) + 2))
                sheet.column_dimensions[column[0].column_letter].width = width
    return output.getvalue()
