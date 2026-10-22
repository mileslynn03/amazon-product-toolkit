"""Launcher checks use temporary folders and local servers, without downloading packages."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import launcher
import server

READY = {"python":[3,11,9], "bits":64, "dependencies":True, "browser":True}


class LauncherTests(unittest.TestCase):
    def test_nested_requirements_change_invalidates_toolkit_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'requirements.txt').write_text('-r review/requirements.txt\n',encoding='utf-8')
            (root/'review').mkdir()
            nested=root/'review'/'requirements.txt'
            nested.write_text('fastapi>=0.110.0\n',encoding='utf-8')
            before=launcher.requirements_hash(root)
            nested.write_text('fastapi>=0.120.0\n',encoding='utf-8')
            self.assertNotEqual(before,launcher.requirements_hash(root))

    def root(self, folder):
        root=Path(folder)/"folder with spaces 中文"
        root.mkdir()
        (root/"requirements.txt").write_text("fastapi>=0.110.0\n",encoding="utf-8")
        python=launcher.environment_python(root);python.parent.mkdir(parents=True)
        python.touch()
        return root

    def test_cached_setup_does_not_install_again_and_changed_requirements_do(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            marker=root/".venv"/".toolkit-setup.json"
            marker.write_text(json.dumps({"requirements":launcher.requirements_hash(root)}))
            with patch.object(launcher,"probe_environment",return_value=READY),patch.object(launcher.subprocess,"run") as run,redirect_stdout(io.StringIO()):
                launcher.prepare_environment(root,"en")
                run.assert_not_called()
                (root/"requirements.txt").write_text("fastapi>=0.120.0\n")
                launcher.prepare_environment(root,"en")
                self.assertEqual(run.call_count,1)
                self.assertEqual(run.call_args.args[0][-1],str(root/"requirements.txt"))
                self.assertEqual(launcher.read_marker(root)["requirements"],launcher.requirements_hash(root))

    def test_missing_chromium_is_installed_even_when_requirements_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            (root/".venv"/".toolkit-setup.json").write_text(json.dumps({"requirements":launcher.requirements_hash(root)}))
            with patch.object(launcher,"probe_environment",side_effect=[{**READY,"browser":False},READY]),patch.object(launcher.subprocess,"run") as run,redirect_stdout(io.StringIO()):
                launcher.prepare_environment(root,"en")
                self.assertEqual(run.call_args.args[0][1:],["-m","playwright","install","chromium"])

    def test_failed_install_not_marked_complete_and_next_launch_can_recover(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            failure=subprocess.CalledProcessError(1,["pip"])
            with patch.object(launcher,"probe_environment",return_value=READY),patch.object(launcher.subprocess,"run",side_effect=failure),redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.CalledProcessError):launcher.prepare_environment(root,"en")
            self.assertFalse((root/".venv"/".toolkit-setup.json").exists())
            with patch.object(launcher,"probe_environment",return_value=READY),patch.object(launcher.subprocess,"run"),redirect_stdout(io.StringIO()):
                launcher.prepare_environment(root,"en")
            self.assertTrue(launcher.read_marker(root))

    def test_lock_blocks_parallel_setup_and_releases_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            script="import launcher,sys; from pathlib import Path\nwith launcher.setup_lock(Path(sys.argv[1]),'en'): pass"
            with launcher.setup_lock(root,"en"):
                result=subprocess.run([sys.executable,"-c",script,str(root)],cwd=launcher.ROOT,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Another launcher',result.stderr)
            # The lock file remains, but the OS lock is gone.
            with launcher.setup_lock(root,"en"):
                pass

    def test_damaged_environment_is_preserved_and_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/".venv").mkdir();(root/".venv"/"keep.txt").write_text("keep")
            with self.assertRaisesRegex(RuntimeError,'Rename'):
                launcher.prepare_environment(root,"en")
            self.assertEqual((root/".venv"/"keep.txt").read_text(),"keep")

    def test_check_missing_environment_does_not_create_files(self):
        before=Path.cwd()
        with tempfile.TemporaryDirectory() as folder,patch.object(launcher,"ROOT",Path(folder)),patch.object(launcher,"environment_python",return_value=Path(folder)/"missing"),redirect_stdout(io.StringIO()):
            try:
                self.assertEqual(launcher.main(["--lang","en","--check"]),1)
                self.assertEqual(list(Path(folder).iterdir()),[])
            finally:os.chdir(before)

    def test_busy_port_does_not_prepare_or_terminate_other_service(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            port=listener.getsockname()[1]
            with patch.object(launcher,"prepare_environment") as prepare,redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(launcher.main(['--lang','en','--no-open','--port',str(port)]),1)
                prepare.assert_not_called()
            self.assertIn('occupied',errors.getvalue())
            self.assertGreater(listener.fileno(),0)

    def test_project_health_reuses_only_same_checkout(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'app':launcher.APP_ID,'project_id':launcher.project_id()}).encode())
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            port=http.server_port
            self.assertEqual(launcher.server_state(launcher.ROOT,port),'ours')
            with tempfile.TemporaryDirectory() as folder:
                self.assertEqual(launcher.server_state(Path(folder),port),'occupied')
            with patch.object(launcher,"prepare_environment") as prepare,patch.object(launcher,"open_page") as opened,redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(['--lang','en','--port',str(port)]),0)
                prepare.assert_not_called();opened.assert_called_once()
        finally:
            http.shutdown();http.server_close();thread.join(timeout=5)

    def test_health_endpoint_excludes_data_and_paths(self):
        client=TestClient(server.app)
        try:info=client.get('/api/health').json()
        finally:client.close()
        self.assertEqual(info,{'app':launcher.APP_ID,'status':'ok','project_id':launcher.project_id()})
        self.assertNotIn(str(launcher.ROOT),json.dumps(info))

    def test_browser_failure_prints_manual_url(self):
        with patch.object(launcher.webbrowser,'open',return_value=False),redirect_stdout(io.StringIO()) as output:
            launcher.open_page('http://127.0.0.1:8000/','en')
        self.assertIn('Visit: http://127.0.0.1:8000/',output.getvalue())

    def test_actual_runtime_probe_works_from_unicode_path(self):
        with tempfile.TemporaryDirectory(prefix='toolkit 空格 ') as folder:
            info=launcher.probe_environment(Path(sys.executable),Path(folder))
        self.assertTrue(info['dependencies'])
        self.assertTrue(info['browser'])
        self.assertEqual(info['bits'],64)

    def test_documentation_links_and_launcher_line_endings(self):
        import re
        root=launcher.ROOT
        for name in ['README.md','README.en.md','docs/USER_GUIDE.zh-CN.md','docs/USER_GUIDE.en.md','docs/DEVELOPMENT.md']:
            path=root/name
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):continue
                self.assertTrue((path.parent/target.split('#')[0]).exists(),(name,target))
        self.assertNotIn(b'\r', (root/'start_macos.command').read_bytes())

    def test_real_server_starts_from_isolated_checkout_without_user_data(self):
        with tempfile.TemporaryDirectory(prefix='toolkit launch 空格 ') as folder:
            root=Path(folder)
            for path in launcher.ROOT.glob('*.py'):
                shutil.copy2(path,root/path.name)
            for name in ['static','scraper']:
                shutil.copytree(launcher.ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__'))
            with socket.socket() as available:
                available.bind(('127.0.0.1',0));port=available.getsockname()[1]
            process=subprocess.Popen([sys.executable,str(root/'launcher.py'),'--run-server','--lang','en','--no-open','--port',str(port)],
                cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    if launcher.server_state(root,port)=='ours':break
                    if process.poll() is not None:self.fail(process.stdout.read().decode('utf-8','replace'))
                    time.sleep(0.2)
                else:self.fail('Isolated server did not become ready')
                self.assertEqual(launcher.server_state(launcher.ROOT,port),'occupied')
                from urllib.request import ProxyHandler,build_opener
                opener=build_opener(ProxyHandler({}))
                with opener.open(f'http://127.0.0.1:{port}/api/status',timeout=5) as response:
                    state=json.load(response)
                self.assertEqual(state['tasks'],[])
                self.assertEqual(state['reviews'],[])
            finally:
                if process.poll() is None:
                    if os.name=='nt':process.terminate()
                    else:process.send_signal(signal.SIGINT)
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                process.stdout.close()


if __name__=='__main__':unittest.main()
