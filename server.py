"""Amazon Product Toolkit 本地服务：评论采集、登录、翻译和 Excel 导出。"""
from __future__ import annotations
import asyncio
import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from pydantic import model_validator

from marketplaces import MARKETPLACES, STAR_FILTERS
from scraper import browser as browser_mod
from scraper import login as login_mod
from scraper.crawler import crawl, fetch_product_info
from scraper.errors import CrawlError
from exporter import build_excel
from task_manager import manager
from results import combination_key, task_key, product_key
from capture import STOP_REASONS
from launcher import APP_ID, project_id
from translation import TranslationSettings, TranslationError, translate_batch, translate_results

BROWSER_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="amazon-browser")
TRANSLATION_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="review-translation")


@asynccontextmanager
async def lifespan(app):
    yield
    manager.cancel_event.set()
    manager.cancel_login()
    try:
        await asyncio.wait_for(asyncio.wrap_future(BROWSER_WORKER.submit(browser_mod.close)), timeout=35)
    finally:
        BROWSER_WORKER.shutdown(wait=False, cancel_futures=True)
        TRANSLATION_WORKER.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Amazon Product Toolkit · 亚马逊商品工具箱", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
logger = logging.getLogger(__name__)
PRODUCT_JOBS = set()


class CountryRequest(BaseModel):
    country: str = "us"

    @field_validator("country")
    @classmethod
    def valid_country(cls, value):
        if value not in MARKETPLACES:
            raise ValueError("未知国家站点")
        return value


class StartRequest(CountryRequest):
    asins: list[str] = Field(min_length=1, max_length=100)
    mode: Literal["quick", "deep"] = "quick"
    local_only: bool = Field(default=False, strict=True)
    translation: TranslationSettings | None = None
    star_key: str | None = None
    cap: int | None = Field(default=None, strict=True, ge=1, le=10000)
    countries: list[str] | None = Field(default=None, min_length=1, max_length=20)
    star_keys: list[str] | None = Field(default=None, min_length=1, max_length=8)

    @field_validator("countries")
    @classmethod
    def valid_countries(cls, values):
        if values is not None and any(value not in MARKETPLACES for value in values):
            raise ValueError("国家选项包含未知站点")
        return list(dict.fromkeys(values)) if values is not None else None

    @field_validator("star_keys")
    @classmethod
    def valid_stars(cls, values):
        if values is not None:
            if any(value not in STAR_FILTERS for value in values):
                raise ValueError("星级选项包含未知筛选")
            values = list(dict.fromkeys(values))
            if "全部" in values and len(values) > 1:
                raise ValueError("全部星级不能与其他星级同时选择")
        return values

    @model_validator(mode="after")
    def valid_task_count(self):
        count = len(self.asins) * len(self.countries or [self.country])
        if self.mode == "deep":
            count *= len(self.star_keys or [self.star_key or "全部"])
        if count > 500:
            raise ValueError("单次最多 500 个采集组合，请减少商品、国家或星级")
        return self

    @field_validator("asins")
    @classmethod
    def valid_asins(cls, values):
        import re
        normalized = [value.strip().upper() for value in values]
        if any(not re.fullmatch(r"[A-Z0-9]{10}", value) for value in normalized):
            raise ValueError("ASIN 必须是 10 位英文字母或数字")
        return list(dict.fromkeys(normalized))

    @field_validator("star_key")
    @classmethod
    def valid_star(cls, value):
        if value is not None and value not in STAR_FILTERS:
            raise ValueError("未知星级筛选")
        return value


class LoginRequest(CountryRequest):
    asin: str | None = None

    @field_validator("asin")
    @classmethod
    def valid_asin(cls, value):
        import re
        if value is not None:
            value = value.strip().upper()
            if not re.fullmatch(r"[A-Z0-9]{10}", value):
                raise ValueError("登录验证商品必须是 10 位 ASIN")
        return value


class RetryRequest(BaseModel):
    task_ids: list[str] | None = Field(default=None, min_length=1, max_length=500)
    run_id: str
    translation: TranslationSettings | None = None


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    message = "；".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}"
                       for e in exc.errors()[:4])
    return JSONResponse(status_code=422, content={"ok": False, "message": f"参数无效：{message}"})


def session_states():
    return {code: browser_mod.session_status(code) for code in MARKETPLACES}


def state_snapshot():
    return {**manager.snapshot(), "sessions": session_states()}


@app.get("/")
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/init")
async def api_init():
    return {"marketplaces": list(MARKETPLACES.values()),
            "star_filters": list(STAR_FILTERS), "sessions": session_states(),"stop_reasons":STOP_REASONS}


@app.get("/api/health")
async def api_health():
    return {"app":APP_ID,"status":"ok","project_id":project_id()}


@app.get("/api/status")
async def api_status():
    return state_snapshot()


@app.get("/api/events")
async def events(request: Request):
    queue = asyncio.Queue()
    manager.subscribe(queue, asyncio.get_running_loop())

    async def generate():
        try:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    if event["type"] == "snapshot":
                        event = {**event, "sessions": session_states()}
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            manager.unsubscribe(queue)
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _worker_run(tasks, task_manager, translation_settings=None):
    try:
        for task in tasks:
            if task_manager.cancel_event.is_set():
                break
            asin = task["asin"]
            key = task_key(task)
            task_manager.start_task(key)
            def progress(a, page, count, message):
                task_manager.emit_progress(a, page, count, message, task_id=key)
            def product(metadata):
                task_manager.update_product(asin, task["country"], metadata)
            try:
                reviews = crawl(task, on_progress=progress, cancel_event=task_manager.cancel_event,
                                keep_browser=True, on_product=product,
                                seed_reviews=task_manager.snapshot()["results"].get(key,[]),
                                on_checkpoint=lambda reviews, report: task_manager.checkpoint(key,reviews,report),
                                fetch_product=not task_manager.has_product(asin, task["country"]))
                status = "cancelled" if task_manager.cancel_event.is_set() else (
                    "success" if reviews else "empty")
                message = "用户已停止" if status == "cancelled" else (
                    "抓取成功" if reviews else "没有符合本站地区条件的评论（含地区未识别）" if task.get("local_only") else "页面明确显示暂无评论")
                task_manager.add_result(key, reviews, status, message)
            except CrawlError as exc:
                task_manager.add_result(key, exc.reviews, exc.status, str(exc))
            except Exception as exc:
                logger.exception("ASIN %s 抓取异常", asin)
                task_manager.add_result(key, [], "failed", f"抓取异常：{exc}")
    finally:
        # 同一批组合继续复用认证上下文，整批结束后再关闭；关闭前保持任务互斥。
        try:
            browser_mod.close()
        except Exception:
            logger.exception("采集结束后关闭浏览器失败")
        finally:
            # 在同一个锁内从采集交接到翻译，避免新任务插入；密钥不进入任务和缓存。
            with task_manager._lock:
                task_manager.mark_complete()
                auto_translate = translation_settings is not None and not task_manager.cancel_event.is_set() and bool(task_manager.snapshot()["reviews"])
                if auto_translate:
                    task_manager.start_translation(translation_settings)
            if auto_translate:
                translate_results(task_manager, translation_settings)


@app.post("/api/start")
async def api_start(body: StartRequest):
    countries = body.countries or [body.country]
    stars = (body.star_keys or [body.star_key or "全部"]) if body.mode == "deep" else ["全部"]
    missing = [code for code in countries if not browser_mod.is_logged_in(code)] if body.mode == "deep" else []
    if missing:
        return JSONResponse(status_code=409, content={
            "ok": False, "message": "请先完成这些站点的登录：" + "、".join(MARKETPLACES[c]["name"] for c in missing),
            "missing_countries": missing})
    multi = body.countries is not None or body.star_keys is not None
    tasks = [{"id": combination_key(asin, country, star) if multi else asin,
              "asin": asin, "country": country, "mode": body.mode,
              "local_only": body.local_only,
              "star_key": star, "cap": body.cap if body.mode == "deep" else None}
             for country in countries for asin in body.asins for star in stars]
    try:
        manager.start_run(tasks)
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"ok": False, "message": str(exc)})
    try:
        manager.worker = BROWSER_WORKER.submit(_worker_run, tasks, manager, body.translation)
    except Exception as exc:
        for task in tasks:
            manager.add_result(task_key(task), [], "failed", f"任务线程启动失败：{exc}")
        manager.mark_complete()
        return JSONResponse(status_code=500, content={"ok": False, "message": "任务线程启动失败"})
    return {"ok": True, "total": len(tasks), "run_id": manager.run_id}


@app.post("/api/stop")
async def api_stop():
    manager.stop()
    return {"ok": True}


@app.post("/api/retry")
async def api_retry(body: RetryRequest):
    try:
        tasks = manager.retry_candidates(body.task_ids,body.run_id)
        missing = sorted({t["country"] for t in tasks if t["mode"]=="deep" and not browser_mod.is_logged_in(t["country"])})
        if missing:
            return JSONResponse(status_code=409,content={"ok":False,
                "message":"请先完成这些站点的登录："+"、".join(MARKETPLACES[c]["name"] for c in missing),"missing_countries":missing})
        tasks = manager.start_retry(body.task_ids,body.run_id)
    except ValueError as exc:
        return JSONResponse(status_code=409,content={"ok":False,"message":str(exc)})
    try:
        manager.worker = BROWSER_WORKER.submit(_worker_run,tasks,manager,body.translation)
    except Exception:
        for task in tasks:
            manager.add_result(task_key(task),[],"failed","重试线程启动失败")
        manager.mark_complete()
        return JSONResponse(status_code=500,content={"ok":False,"message":"重试线程启动失败"})
    return {"ok":True,"total":len(tasks),"run_id":manager.run_id}


@app.post("/api/llm/test")
def api_llm_test(body: TranslationSettings):
    try:
        result = translate_batch(body,[{"id":"0","title":"Connection test","body":"The product works well."}],threading.Event())
        return {"ok":True,"title":result["0"]["title"],"body":result["0"]["body"]}
    except TranslationError as exc:
        return JSONResponse(status_code=400,content={"ok":False,"message":str(exc)})


@app.post("/api/translate")
async def api_translate(body: TranslationSettings):
    try:
        manager.start_translation(body)
    except ValueError as exc:
        return JSONResponse(status_code=409,content={"ok":False,"message":str(exc)})
    try:
        manager.worker = TRANSLATION_WORKER.submit(translate_results,manager,body)
    except Exception:
        manager.translation_failed("翻译任务启动失败，请重试")
        manager.finish_translation()
        return JSONResponse(status_code=500,content={"ok":False,"message":"翻译任务启动失败，请重试"})
    return {"ok":True,"total":manager.translation["total"]}


def _login_thread(code, task_manager, asin=None):
    try:
        login_mod.run_login(code, task_manager.login_ready, task_manager.login_done,
                            on_ready=lambda: task_manager.on_login_ready(code),
                            on_retry=lambda message: task_manager.on_login_retry(code, message),
                            cancel_event=task_manager.login_cancel, verification_asin=asin,
                            keep_browser=True)
        task_manager.on_login_saved(code)
    except Exception as exc:
        task_manager.on_login_error(code, str(exc))


@app.post("/api/login")
async def api_login(body: LoginRequest):
    try:
        manager.start_login(body.country)
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"ok": False, "message": str(exc)})
    try:
        asin = body.asin or next((t["asin"] for t in manager.snapshot()["tasks"]
                                  if t["country"] == body.country), None)
        BROWSER_WORKER.submit(_login_thread, body.country, manager, asin)
    except Exception as exc:
        manager.on_login_error(body.country, str(exc))
        return JSONResponse(status_code=500, content={"ok": False, "message": "登录线程启动失败"})
    return {"ok": True}


@app.post("/api/login/save")
async def api_login_save():
    try:
        manager.finish_login()
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"ok": False, "message": str(exc)})
    return {"ok": True}


@app.post("/api/login/cancel")
async def api_login_cancel():
    manager.cancel_login()
    return {"ok": True}


@app.post("/api/products/refresh")
async def api_product_refresh(body: LoginRequest):
    if not body.asin:
        return JSONResponse(status_code=422, content={"ok": False, "message": "请指定商品 ASIN"})
    key = product_key(body.asin, body.country)
    with manager._lock:
        if manager.running or manager.login_busy:
            return JSONResponse(status_code=409, content={"ok": False, "message": "当前浏览器正在采集或登录"})
        if key in PRODUCT_JOBS or manager.has_product(body.asin, body.country):
            return {"ok": True}
        PRODUCT_JOBS.add(key)
    def fetch():
        try:
            manager.update_product(body.asin, body.country, fetch_product_info(body.asin, body.country))
        except Exception:
            logger.info("商品 %s 的辅助信息暂不可读", body.asin)
        finally:
            with manager._lock:
                PRODUCT_JOBS.discard(key)
    BROWSER_WORKER.submit(fetch)
    return {"ok": True}


@app.get("/api/export")
def api_export():
    state = manager.snapshot()
    if not state["tasks"]:
        return Response(status_code=400, content="暂无任务结果")
    data = build_excel(state["tasks"], state["results"], state["outcomes"], state.get("products"))
    filename = f"amazon_product_toolkit_reviews_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
