"""线程安全的任务状态和 SSE 快照；登录与抓取互斥。"""
from __future__ import annotations
import copy
import threading
import uuid
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from results import task_key, product_key, unique_reviews
from translation import source_key
from capture import COMPLETE_STATUSES, ACTIVE_STATUSES, empty_stats, merge_reviews, capture_summary
from _runtime import DATA_HOME


class TaskManager:
    def __init__(self, persistence_path=None):
        self._lock = threading.RLock()
        self.running = False
        self.phase = "idle"
        self.status = ""
        self.done = self.total = 0
        self.results = {}
        self.outcomes = {}
        self.products = {}
        self.translation = {"phase":"idle","done":0,"total":0,"succeeded":0,"failed":0}
        self.active_task = None
        self.tasks = []
        self.run_id = None
        self.instance_id = uuid.uuid4().hex
        self.revision = 0
        self.last_saved_at = None
        self.persistence_error = ""
        self.cancel_event = threading.Event()
        self.worker = None
        self.login_code = None
        self.login_phase = None
        self.login_error = ""
        self.login_ready = threading.Event()
        self.login_done = threading.Event()
        self.login_cancel = threading.Event()
        self._subscribers = {}
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._restore()

    def _restore(self):
        if self.persistence_path and self.persistence_path.exists():
            try:
                state = json.loads(self.persistence_path.read_text(encoding="utf-8"))
                for name in ("results", "outcomes", "products", "tasks", "run_id", "phase", "status", "done", "total", "translation", "last_saved_at"):
                    if name in state:
                        setattr(self, name, state[name])
                if self.translation.get("phase") == "running":
                    self.translation["phase"] = "interrupted"
                    self.phase = self.translation.get("return_phase", "completed")
                    self.status = self.translation.get("return_status", "")
                if self.phase == "running":
                    interrupted = False
                    for task in self.tasks:
                        key = task_key(task)
                        old = self.outcomes.get(key,{})
                        if old.get("status","pending") in ACTIVE_STATUSES:
                            self.outcomes[key] = {**old,"status":"interrupted","stop_reason":"interrupted",
                                "count":len(self.results.get(key,[])),"message":"上次采集意外中断，已恢复已保存评论，可重试此组合"}
                            interrupted = True
                    self.phase = "interrupted" if interrupted else ("partial" if any(o.get("status") not in COMPLETE_STATUSES for o in self.outcomes.values()) else "completed")
                    self.status = "采集曾中断，已恢复保存结果，可重试未完成组合"
                    self._update_done()
            except (OSError, ValueError, TypeError):
                logging.getLogger(__name__).warning("上次结果未能恢复", exc_info=True)

    def _persist(self):
        if self.persistence_path:
            try:
                self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.persistence_path.with_suffix(".tmp")
                saved_at = datetime.now(timezone.utc).isoformat()
                payload = {name: getattr(self, name) for name in ("results", "outcomes", "products", "tasks", "run_id", "phase", "status", "done", "total", "translation")}
                payload["last_saved_at"] = saved_at
                with temporary.open("w",encoding="utf-8") as file:
                    json.dump(payload,file,ensure_ascii=False)
                    file.flush()
                    os.fsync(file.fileno())
                temporary.replace(self.persistence_path)
                self.last_saved_at, self.persistence_error = saved_at, ""
            except OSError:
                self.persistence_error = "本地结果保存失败，请检查磁盘空间和目录权限，并及时导出当前结果"
                logging.getLogger(__name__).warning("结果缓存写入失败", exc_info=True)
                return False
        return True

    def update_product(self, asin, country, metadata):
        with self._lock:
            key = product_key(asin, country)
            existing = self.products.get(key, {})
            self.products[key] = {**existing, **{k: v for k, v in metadata.items() if v}, "asin": asin, "country": country}
            if not self.running:
                self._persist()
            self._publish()

    def has_product(self, asin, country):
        with self._lock:
            item = self.products.get(product_key(asin, country), {})
            return bool(item.get("title") and item.get("image"))

    @property
    def login_busy(self):
        return self.login_phase in {"opening", "waiting", "saving"}

    def snapshot(self):
        with self._lock:
            reviews = unique_reviews(self.tasks,self.results)
            return copy.deepcopy({
                "run_id": self.run_id, "revision": self.revision, "instance_id": self.instance_id,
                "running": self.running, "phase": self.phase, "status": self.status,
                "done": self.done, "total": self.total, "results": self.results,
                "outcomes": self.outcomes, "tasks": self.tasks,
                "products": self.products, "reviews": reviews,
                "capture_summary":capture_summary(self.outcomes,reviews),
                "last_saved_at":self.last_saved_at,"persistence_error":self.persistence_error,
                "translation": self.translation,
                "active_task": self.active_task,
                "login_phase": self.login_phase, "login_code": self.login_code,
                "login_error": self.login_error,
            })

    def subscribe(self, queue, loop):
        with self._lock:
            self._subscribers[queue] = loop
            queue.put_nowait({"type": "snapshot", **self.snapshot()})

    def unsubscribe(self, queue):
        with self._lock:
            self._subscribers.pop(queue, None)

    def _publish(self, progress=False):
        """调用者持锁；版本号用于过滤重连后的过期事件。"""
        self.revision += 1
        if progress:
            event = {"type": "progress", "revision": self.revision, "instance_id": self.instance_id,
                     "run_id": self.run_id, "status": self.status,
                     "active_task": self.active_task,
                     "done": self.done, "total": self.total}
        else:
            event = {"type": "snapshot", **self.snapshot()}
        for queue, loop in list(self._subscribers.items()):
            if not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                except RuntimeError:
                    pass

    def start_run(self, tasks):
        with self._lock:
            if self.running or self.login_busy:
                raise ValueError("浏览器正在抓取或登录，请先结束当前操作")
            self.run_id = uuid.uuid4().hex
            self.tasks = [{**task, "id": task_key(task)} for task in tasks]
            self.results = {}
            self.outcomes = {}
            self.translation = {"phase":"idle","done":0,"total":0,"succeeded":0,"failed":0}
            self.active_task = None
            self.done, self.total = 0, len(tasks)
            self.cancel_event = threading.Event()
            self.running = True
            self.phase = "running"
            self.status = "任务已启动…"
            self._persist()
            self._publish()

    def emit_progress(self, asin, page, count, msg, task_id=None):
        with self._lock:
            self.active_task = task_id
            self.status = f"ASIN {asin} | 第 {page} 页 | 已抓 {count} 条 | {msg}"
            self._publish(progress=True)

    def add_result(self, asin, reviews, status="success", message=""):
        with self._lock:
            # 上限由采集器约束新增条目；合并时始终保留历史结果，不截断旧缓存。
            self.results[asin] = merge_reviews(self.results.get(asin,[]),reviews)
            old = self.outcomes.get(asin,{})
            reason = old.get("stop_reason") or (status if status not in {"success","empty","failed"} else "unexpected_error" if status=="failed" else "unknown")
            stats = {**old.get("stats",empty_stats()),"kept":len(self.results[asin])}
            self.outcomes[asin] = {**old,"status": status, "message": message, "count": len(self.results[asin]),
                                  "stop_reason":reason,"stats":stats,"attempted":True}
            self._update_done()
            self._persist()
            self._publish()

    def _update_done(self):
        self.done = sum(o.get("status") not in ACTIVE_STATUSES|{"interrupted"} and o.get("attempted",True) for o in self.outcomes.values())

    def start_task(self, key):
        with self._lock:
            old = self.outcomes.get(key,{})
            self.active_task = key
            self.outcomes[key] = {**old,"status":"running","attempted":True,"attempt":old.get("attempt",1),
                                  "count":len(self.results.get(key,[])),"message":"正在读取页面…"}
            self._update_done()
            self._persist()
            self._publish()

    def checkpoint(self, key, reviews, report):
        with self._lock:
            self.results[key] = merge_reviews(self.results.get(key,[]),reviews)
            old = self.outcomes.get(key,{})
            self.outcomes[key] = {**old,"status":"running","attempted":True,"count":len(self.results[key]),
                "stats":{**report["stats"],"kept":len(self.results[key])},"stats_known":True,
                "stop_reason":report.get("stop_reason","")}
            self._persist()
            self._publish()

    def retry_candidates(self, task_ids=None, run_id=None):
        with self._lock:
            if self.running or self.login_busy:
                raise ValueError("请先结束当前采集、翻译或登录操作")
            if run_id is not None and run_id != self.run_id:
                raise ValueError("任务已变化，请刷新后重试")
            keys = {task_key(t) for t in self.tasks}
            if task_ids and not set(task_ids)<=keys:
                raise ValueError("重试列表包含未知组合")
            selected = [t for t in self.tasks if (not task_ids or task_key(t) in task_ids) and self.outcomes.get(task_key(t),{}).get("status") not in COMPLETE_STATUSES]
            if not selected:
                raise ValueError("没有需要重试的组合")
            return copy.deepcopy(selected)

    def start_retry(self, task_ids=None, run_id=None):
        with self._lock:
            selected = self.retry_candidates(task_ids,run_id)
            for task in selected:
                key = task_key(task)
                old = self.outcomes.get(key,{})
                self.outcomes[key] = {"status":"pending","attempted":False,"attempt":old.get("attempt",1)+1,
                    "count":len(self.results.get(key,[])),"stats":empty_stats(len(self.results.get(key,[]))),
                    "stats_known":False,"stop_reason":"","message":"等待重试，已保留上次评论"}
            self.cancel_event = threading.Event()
            self.running, self.phase, self.active_task = True,"running",None
            self.status = "正在重试未完成的采集组合…"
            self._update_done()
            self._persist()
            self._publish()
            return selected

    def stop(self):
        with self._lock:
            if self.running:
                self.cancel_event.set()
                self.status = "正在停止翻译，保留原文与已有译文…" if self.phase == "translating" else "正在停止，保留已抓取的评论…"
                self._publish(progress=True)

    def mark_complete(self):
        with self._lock:
            for task in self.tasks:
                key = task_key(task)
                old = self.outcomes.get(key,{})
                if old.get("status","pending") in ACTIVE_STATUSES:
                    cancelled = self.cancel_event.is_set()
                    self.outcomes[key] = {**old,"status":"cancelled" if cancelled else "interrupted",
                        "stop_reason":"cancelled" if old.get("attempted") and cancelled else "not_started" if cancelled else "interrupted",
                        "attempted":old.get("attempted",False),"count":len(self.results.get(key,[])),
                        "message":("用户已停止，已保留结果" if old.get("attempted") else "已停止，未执行") if cancelled else "组合未完成，可重试"}
            failed = sum(v["status"] not in COMPLETE_STATUSES
                         for v in self.outcomes.values())
            if self.cancel_event.is_set():
                self.phase, self.status = "cancelled", "任务已停止，已保留部分结果"
                for task in self.tasks:
                    self.outcomes.setdefault(task_key(task), {
                        "status": "cancelled", "message": "已停止，未执行", "count": 0})
            elif failed:
                self.phase = "partial" if any(self.results.values()) else "failed"
                self.status = f"任务结束：{failed} 个商品未完成，请查看失败原因"
            else:
                self.phase = "completed"
                self.status = "抓取完成" if any(self.results.values()) else (
                    "任务结束：没有符合条件的评论" if any(t.get("local_only") for t in self.tasks) else "任务结束：商品暂无评论")
            self.running = False
            self.active_task = None
            self._update_done()
            self._persist()
            self._publish()

    def start_translation(self, settings):
        with self._lock:
            if self.running or self.login_busy:
                raise ValueError("请先结束当前采集、翻译或登录操作")
            total = len(unique_reviews(self.tasks,self.results))
            if not total:
                raise ValueError("尚无可翻译的评论")
            self.translation = {"phase":"running","done":0,"total":total,"succeeded":0,"failed":0,
                                "target_language":settings.target_language,"model":settings.model,"provider":settings.provider,"error":"",
                                "return_phase":self.phase,"return_status":self.status}
            self.cancel_event = threading.Event()
            self.running = True
            self.phase, self.status = "translating", "正在翻译评论…"
            self._publish()

    def apply_translations(self, updates, done, succeeded, failed):
        with self._lock:
            for reviews in self.results.values():
                for review in reviews:
                    key = source_key(review)
                    if key in updates:
                        review["translation"] = copy.deepcopy(updates[key])
            self.translation["done"] += done
            self.translation["succeeded"] += succeeded
            self.translation["failed"] += failed
            self._persist()
            self._publish()

    def translation_failed(self, message):
        with self._lock:
            self.translation["error"] = message

    def finish_translation(self):
        with self._lock:
            info = self.translation
            info["phase"] = "cancelled" if self.cancel_event.is_set() else (
                "failed" if info.get("error") or info["failed"] == info["total"] else
                "partial" if info["failed"] else "completed")
            self.phase = info.get("return_phase", "completed")
            self.status = info.get("return_status", "")
            self.running = False
            self._persist()
            self._publish()

    def start_login(self, code):
        with self._lock:
            if self.running or self.login_busy:
                raise ValueError("浏览器正在抓取或登录，请先结束当前操作")
            self.login_code = code
            self.login_phase = "opening"
            self.login_error = ""
            self.login_ready = threading.Event()
            self.login_done = threading.Event()
            self.login_cancel = threading.Event()
            self._publish()

    def on_login_ready(self, code):
        with self._lock:
            if not self.login_cancel.is_set():
                self.login_phase = "waiting"
                self._publish()

    def on_login_saved(self, code):
        with self._lock:
            self.login_phase = "saved"
            self._publish()

    def on_login_retry(self, code, message):
        with self._lock:
            if not self.login_cancel.is_set():
                self.login_phase = "waiting"
                self.login_error = message
                self._publish()

    def on_login_error(self, code, message):
        with self._lock:
            self.login_phase = "cancelled" if self.login_cancel.is_set() else "error"
            self.login_error = message
            self._publish()

    def finish_login(self):
        with self._lock:
            if self.login_phase != "waiting" or self.login_cancel.is_set():
                raise ValueError("当前没有等待保存的登录窗口")
            self.login_phase = "saving"
            self.login_error = ""
            self.login_done.set()
            self._publish()

    def cancel_login(self):
        with self._lock:
            if self.login_busy:
                self.login_cancel.set()
                self.login_done.set()


manager = TaskManager(DATA_HOME / "data" / "last_results.json")
