"""逐页持久化、增量重试、数量核算及帮助教程的离线回归。"""
import copy
import io
import json
import re
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook

import server
import test_regressions as old
from capture import STOP_REASONS, empty_stats, merge_reviews
from scraper import browser, crawler
from scraper.errors import CrawlError
from task_manager import TaskManager

TASK={**old.TASK,"id":"failed","cap":10,"star_key":"全部"}
DONE={**TASK,"id":"done","star_key":"5 星"}
SAMPLE={"review_id":"R1","title":"Title R1","body":"source","rating":4,
        "translation":{"status":"success","title":"译文","body":"原有译文"}}


def seeded(manager):
    manager.start_run([TASK,DONE])
    manager.add_result("done",[SAMPLE])
    manager.add_result("failed",[SAMPLE],"pagination_error","failed page")
    manager.mark_complete()


class CaptureStateTests(unittest.TestCase):
    def test_checkpoint_survives_restart_and_only_unfinished_tasks_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"results.json"
            manager=TaskManager(path);manager.start_run([TASK,DONE]);manager.add_result("done",[SAMPLE])
            manager.start_task("failed")
            manager.checkpoint("failed",[SAMPLE],{"stats":{**empty_stats(),"read":1,"new":1,"pages":1}})
            original=path.read_bytes()
            restored=TaskManager(path)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(restored.phase,"interrupted")
            self.assertEqual(restored.outcomes["failed"]["stop_reason"],"interrupted")
            self.assertEqual(restored.results["failed"],[SAMPLE])
            self.assertTrue(restored.last_saved_at)
            run=restored.run_id;done=copy.deepcopy(restored.outcomes["done"])
            self.assertEqual([t["id"] for t in restored.start_retry(run_id=run)],["failed"])
            self.assertEqual(restored.run_id,run)
            self.assertEqual(restored.outcomes["done"],done)
            restored.start_task("failed")
            restored.checkpoint("failed",[SAMPLE,{"review_id":"R2","body":"new"}],{
                "stats":{**empty_stats(1),"read":2,"duplicates":1,"new":1,"pages":1},"stop_reason":"no_next_page"})
            restored.add_result("failed",[{"review_id":"R1","title":"Title R1","body":"source","rating":4},{"review_id":"R2","body":"new"}])
            restored.mark_complete()
            self.assertEqual(restored.phase,"completed")
            self.assertEqual(len(restored.results["failed"]),2)
            self.assertEqual(restored.results["failed"][0]["translation"],SAMPLE["translation"])
            self.assertEqual(restored.snapshot()["capture_summary"]["unique_reviews"],2)
            self.assertEqual(restored.outcomes["failed"]["attempt"],2)

    def test_save_failure_keeps_last_good_file_and_exposes_error_until_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"results.json";manager=TaskManager(path);manager.start_run([TASK])
            saved=path.read_bytes()
            with patch.object(Path,"replace",side_effect=OSError("disk full")),self.assertLogs("task_manager",level="WARNING"):
                manager.checkpoint("failed",[SAMPLE],{"stats":empty_stats()})
            self.assertEqual(path.read_bytes(),saved)
            self.assertTrue(manager.snapshot()["persistence_error"])
            self.assertEqual(manager.snapshot()["reviews"][0]["body"],"source")
            manager.add_result("failed",[SAMPLE])
            self.assertFalse(manager.snapshot()["persistence_error"])
            self.assertEqual(TaskManager(path).results["failed"],[SAMPLE])

    def test_retry_rejects_busy_stale_unknown_and_success_only(self):
        manager=TaskManager();seeded(manager)
        for ids,run in [(["done"],manager.run_id),(["unknown"],manager.run_id),(None,"stale")]:
            with self.assertRaises(ValueError):manager.start_retry(ids,run)
        manager.start_login("us")
        with self.assertRaises(ValueError):manager.start_retry()
        manager.on_login_error("us","fixture");manager.start_retry()
        with self.assertRaises(ValueError):manager.start_retry()

    def test_retry_one_does_not_mark_other_cancelled_combination_complete(self):
        manager=TaskManager();manager.start_run([TASK,DONE]);manager.stop();manager.mark_complete()
        manager.start_retry(["failed"]);manager.add_result("failed",[SAMPLE]);manager.mark_complete()
        self.assertEqual(manager.phase,"partial")
        self.assertEqual(manager.outcomes["done"]["stop_reason"],"not_started")
        self.assertEqual([t["id"] for t in manager.retry_candidates()],["done"])

    def test_changed_source_invalidates_translation_and_duplicate_ids_merge(self):
        self.assertIn("translation",merge_reviews([SAMPLE],[{k:v for k,v in SAMPLE.items() if k!="translation"}])[0])
        changed=merge_reviews([SAMPLE],[{**SAMPLE,"body":"edited source"}])
        self.assertEqual(len(changed),1)
        self.assertNotIn("translation",changed[0])

    def test_retry_api_preserves_completed_and_preflights_selected_markets(self):
        manager=TaskManager();seeded(manager)
        before=copy.deepcopy(manager.outcomes["done"])
        client=TestClient(server.app)
        self.addCleanup(client.close)
        with patch.object(server,"manager",manager),patch.object(browser,"close"),patch.object(browser,"is_logged_in",return_value=False):
            # Only UK is selected for retry; US completed task is never checked.
            manager.tasks[0]["country"]="uk"
            response=client.post('/api/retry',json={"run_id":manager.run_id})
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()["missing_countries"],["uk"])
            self.assertEqual(manager.outcomes["done"],before)
            self.assertFalse(manager.running)
            with patch.object(browser,"is_logged_in",return_value=True),patch.object(server,"crawl",return_value=[{"review_id":"R2","body":"new"}]) as crawl:
                self.assertEqual(client.post('/api/retry',json={"run_id":manager.run_id}).status_code,200)
                manager.worker.result(timeout=5)
                crawl.assert_called_once()
                self.assertEqual(crawl.call_args.kwargs['seed_reviews'],[SAMPLE])
            self.assertEqual(manager.outcomes["done"],before)
            self.assertEqual(len(manager.results["failed"]),2)
            self.assertEqual(client.post('/api/retry',json={"run_id":"stale"}).status_code,409)

    def test_export_records_stats_reasons_and_legacy_unknown(self):
        manager=TaskManager();seeded(manager)
        manager.outcomes["failed"].update(stats_known=True,stats={**empty_stats(1),"read":5,"new":1,"duplicates":2,"foreign":1,"unknown":1,"kept":2},stop_reason="pagination_error")
        book=load_workbook(io.BytesIO(server.build_excel(manager.tasks,manager.results,manager.outcomes)))
        rows=list(book['总览'].values);failed=dict(zip(rows[0],rows[1]));done=dict(zip(rows[0],rows[2]))
        self.assertEqual(failed['本轮读取条目'],5)
        self.assertEqual(failed['结束原因'],'翻页未完成')
        self.assertIsNone(done['本轮读取条目'])
        self.assertEqual(done['结束原因'],'未记录结束原因')


class CaptureBrowserTests(unittest.TestCase):
    setUpClass=classmethod(old.BrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(old.BrowserTests.tearDownClass.__func__)
    setUp=old.BrowserTests.setUp
    tearDown=old.BrowserTests.tearDown
    load_frontend=old.BrowserTests.load_frontend

    def collect(self,html,task=None,handler=None,seed=None):
        reports=[]
        self.page.route('https://www.amazon.*/**',handler or (lambda route:route.fulfill(content_type='text/html',body=html)))
        self.reports=reports
        with ExitStack() as stack:
            for name,value in [("launch",self.page),("is_logged_in",True),("load_storage_state",self.page),("close",None),("mark_session",None)]:
                stack.enter_context(patch.object(browser,name,return_value=value))
            return crawler.crawl(task or TASK,cancel_event=threading.Event(),seed_reviews=seed,
                on_checkpoint=lambda reviews,report:reports.append((copy.deepcopy(reviews),copy.deepcopy(report))))

    def assert_accounted(self,report):
        stats=report['stats']
        self.assertEqual(stats['read'],sum(stats[k] for k in ['duplicates','foreign','unknown','over_limit','new']))
        self.assertEqual(stats['kept'],stats['recovered']+stats['new'])

    def test_append_counts_duplicate_and_cap_after_origin_filter(self):
        first=old.dated_review('AU','Reviewed in Australia on 7 April 2026')+old.review('UNKNOWN','unknown')+old.dated_review('UK1','Reviewed in the United Kingdom on 7 April 2026')
        extra=json.dumps(old.dated_review('UK2','Reviewed in the United Kingdom on 8 April 2026')+old.dated_review('UK3','Reviewed in the United Kingdom on 9 April 2026'))
        html='<div id="list">'+first+'</div>'+f'<button data-hook="show-more-button" onclick=\'document.getElementById("list").insertAdjacentHTML("beforeend",{extra});this.remove()\'>More</button>'
        result=self.collect(html,{**TASK,'country':'uk','local_only':True,'cap':2})
        self.assertEqual([r['review_id'] for r in result],['UK1','UK2'])
        report=self.reports[-1][1];self.assertEqual(report['stop_reason'],'limit_reached')
        self.assertEqual({k:report['stats'][k] for k in ['pages','read','duplicates','foreign','unknown','over_limit','new']},{'pages':2,'read':8,'duplicates':3,'foreign':1,'unknown':1,'over_limit':1,'new':2})
        self.assert_accounted(report)

    def test_seed_only_first_page_continues_and_keeps_translation(self):
        first=old.review('R1','source')+'<li class="a-last"><a href="/second">Next</a></li>'
        second=old.review('R2','new')
        # Match the parser output exactly so a valid original translation remains valid.
        source={**SAMPLE,'body':'sourcesecond paragraph','rating':4.5}
        result=self.collect(first,handler=lambda route:route.fulfill(content_type='text/html',body=second if route.request.url.endswith('/second') else first),seed=[source])
        self.assertEqual([r['review_id'] for r in result],['R1','R2'])
        self.assertIn('translation',result[0])
        report=self.reports[-1][1]
        self.assertEqual(report['stop_reason'],'no_next_page')
        self.assertEqual((report['stats']['read'],report['stats']['duplicates'],report['stats']['recovered'],report['stats']['new']),(2,1,1,1))
        self.assert_accounted(report)

    def test_late_failure_saves_page_before_failure(self):
        html=old.review('R1','source')+'<button data-hook="show-more-button">More</button>'
        with patch.object(crawler,'_wait_page_change',return_value=False),self.assertRaises(CrawlError):self.collect(html)
        self.assertGreaterEqual(len(self.reports),2)
        self.assertEqual(self.reports[0][0][0]['review_id'],'R1')
        self.assertEqual(self.reports[-1][1]['stop_reason'],'pagination_error')
        self.assert_accounted(self.reports[-1][1])

    def test_quick_and_empty_reasons_are_explicit(self):
        self.collect(old.review('R1','sample'),{**TASK,'mode':'quick'})
        self.assertEqual(self.reports[-1][1]['stop_reason'],'quick_sample')
        self.page.unroute('https://www.amazon.*/**')
        with patch.object(crawler,'_wait_reviews',return_value=False):
            self.collect('<div data-hook="no-reviews-message">No customer reviews</div>')
        self.assertEqual(self.reports[-1][1]['stop_reason'],'no_reviews')

    def test_legacy_summary_and_bilingual_help_keyboard_and_mobile(self):
        self.load_frontend();manager=TaskManager();seeded(manager)
        self.page.evaluate('s=>applySnapshot(s)',manager.snapshot())
        self.assertIn('未记录数量明细',self.page.locator('#captureNumbers').inner_text())
        self.page.locator('#helpBtn').click()
        self.assertTrue(self.page.locator('#helpDialog').is_visible())
        self.assertEqual(self.page.locator('.guide-section').count(),6)
        self.assertIn('Anthropic',self.page.locator('#helpDialog').inner_text())
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.locator('#helpDialog').is_visible())
        self.assertEqual(self.page.evaluate('document.activeElement.id'),'helpBtn')
        self.page.locator('#languageSelect').select_option('en');self.page.locator('#helpBtn').click()
        self.assertFalse(re.search(r'[\u3400-\u9fff]',self.page.locator('#helpDialog').inner_text()))
        self.assertIn('page one',self.page.locator('#helpDialog').inner_text())
        self.page.locator('#helpCloseBtn').click()
        for width in [360,390,760,1440]:
            self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
            self.page.locator('#helpBtn').click()
            self.assertLessEqual(self.page.locator('#helpDialog').bounding_box()['width'],width)
            self.assertLessEqual(self.page.locator('#helpDialog').evaluate('(el)=>el.scrollWidth-el.clientWidth'),1)
            self.page.locator('#helpCloseBtn').click()

    def test_retry_buttons_use_saved_run_and_do_not_change_setup_conditions(self):
        self.load_frontend();manager=TaskManager();seeded(manager)
        self.page.evaluate('s=>applySnapshot(s)',manager.snapshot())
        self.page.locator('#asins').fill('B012345678')
        self.page.evaluate("""() => {window.fetch=async(url,options)=>{
            if(url==='/api/retry') window.sent=JSON.parse(options.body);
            return {ok:true,json:async()=>url==='/api/status'?{...state,revision:999}:{ok:true}};
        }}""")
        self.page.locator('#tasksTab').click()
        self.assertEqual(self.page.locator('#outcomeBody [data-retry]').count(),1)
        self.page.locator('#outcomeBody [data-retry]').click()
        self.page.wait_for_function('window.sent!==undefined')
        self.assertEqual(self.page.evaluate('window.sent.task_ids'),['failed'])
        self.assertEqual(self.page.evaluate('window.sent.run_id'),manager.run_id)
        self.assertEqual(self.page.locator('#asins').input_value(),'B012345678')
        self.assertEqual(self.page.locator('#outcomeBody tr').count(),2)
        self.page.evaluate('window.sent=undefined')
        self.page.locator('#retryAllBtn').click();self.page.wait_for_function('window.sent!==undefined')
        self.assertIsNone(self.page.evaluate('window.sent.task_ids'))

    def test_live_counts_save_error_and_stop_remain_visible_when_setup_collapsed(self):
        self.load_frontend();manager=TaskManager();manager.start_run([TASK]);manager.start_task('failed')
        manager.checkpoint('failed',[SAMPLE],{'stats':{**empty_stats(),'read':2,'new':1,'duplicates':1,'pages':1}})
        snapshot=manager.snapshot();snapshot['persistence_error']='本地结果保存失败，请检查磁盘空间和目录权限，并及时导出当前结果'
        self.page.evaluate('s=>{applySnapshot(s);setSetup(false)}',snapshot)
        self.assertTrue(self.page.locator('#captureStopBtn').is_visible())
        self.assertFalse(self.page.locator('#retryAllBtn').is_visible())
        self.assertIn('2',self.page.locator('#captureNumbers').inner_text())
        self.assertTrue(self.page.locator('#persistenceError').is_visible())
        self.page.locator('#languageSelect').select_option('en')
        self.assertIn('failed',self.page.locator('#persistenceError').inner_text())
        self.assertIn('Read entries',self.page.locator('#captureNumbers').inner_text())
