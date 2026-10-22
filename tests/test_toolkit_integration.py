"""Verify the independent source artifact and the toolkit compatibility boundary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "amazon-review-scraper"
spec = importlib.util.spec_from_file_location("review_release_builder", PROJECT / "build_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ToolkitIntegrationTests(unittest.TestCase):
    def launch(self, project, expected_id, expected_tasks=0):
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("AMAZON_REVIEW_")}
        process = subprocess.Popen(
            [sys.executable, str(project / "launcher.py"), "--run-server", "--lang", "en", "--no-open", "--port", str(port)],
            cwd=project.parent, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        opener = build_opener(ProxyHandler({}))
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    with opener.open(base + "/api/health", timeout=1) as response:
                        health = json.load(response)
                    break
                except OSError:
                    if process.poll() is not None:
                        self.fail(process.stdout.read().decode("utf-8", "replace"))
                    time.sleep(0.2)
            else:
                self.fail("Independent entry point did not become ready")
            self.assertEqual(health["app"], expected_id)
            self.assertEqual(health["project_id"], hashlib.sha256(
                os.path.normcase(str(project.resolve())).encode()).hexdigest()[:16])
            with opener.open(base + "/api/status", timeout=5) as response:
                state = json.load(response)
            self.assertEqual(len(state["tasks"]), expected_tasks)
            with opener.open(base + "/", timeout=5) as response:
                self.assertIn("Amazon Review Scraper GUI", response.read().decode("utf-8"))
            with opener.open(base + "/static/i18n.js", timeout=5) as response:
                self.assertEqual(response.status, 200)
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()

    def test_source_archive_excludes_private_files_and_runs_without_toolkit(self):
        with tempfile.TemporaryDirectory(prefix="review standalone ") as folder:
            folder = Path(folder)
            source = folder / "source"
            shutil.copytree(PROJECT, source, ignore=shutil.ignore_patterns(
                "data", "storage", ".venv", "dist", "__pycache__"))
            for name in ("data/reviews.json", "storage/login_state_us.json", ".venv/private.txt", ".env", "debug.log"):
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("private fixture: must not be distributed", encoding="utf-8")
            archive = builder.build(source, folder / "release")
            with ZipFile(archive) as bundle:
                names = bundle.namelist()
                prefix = json.loads((source / "project.json").read_text(encoding="utf-8"))
                prefix = f"{prefix['id']}-{prefix['version']}"
                self.assertTrue(all(name.startswith(prefix + "/") for name in names))
                self.assertFalse(any(part in {"data", "storage", ".venv", ".env", "debug.log"}
                                     for name in names for part in Path(name).parts))
                manifest = json.loads(bundle.read(prefix + "/RELEASE_MANIFEST.json"))
                for name, digest in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(bundle.read(prefix + "/" + name)).hexdigest(), digest)
                self.assertEqual((bundle.getinfo(prefix + "/start_macos.command").external_attr >> 16) & 0o777, 0o755)
                bundle.extractall(folder / "extracted")
            self.assertTrue(archive.with_suffix(".zip.sha256").exists())
            self.launch(folder / "extracted" / prefix, "amazon-review-scraper-gui")

    def test_toolkit_entry_preserves_original_data_and_session_locations(self):
        with tempfile.TemporaryDirectory(prefix="toolkit compatibility ") as folder:
            root = Path(folder)
            for name in ("launcher.py", "server.py", "_review_project.py"):
                shutil.copy2(ROOT / name, root / name)
            shutil.copytree(PROJECT, root / "projects" / "amazon-review-scraper",
                            ignore=shutil.ignore_patterns("data", "storage", ".venv", "dist", "__pycache__"))
            (root / "data").mkdir()
            (root / "storage").mkdir()
            cache = root / "data" / "last_results.json"
            cache.write_text(json.dumps({"tasks": [{"id": "preserved", "asin": "B0G92M6VFM", "country": "us"}],
                                         "results": {}, "outcomes": {}, "phase": "completed"}), encoding="utf-8")
            session = root / "storage" / "login_state_us.json"
            session.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
            before = (cache.read_bytes(), session.read_bytes())
            self.launch(root, "amazon-product-toolkit", expected_tasks=1)
            self.assertEqual((cache.read_bytes(), session.read_bytes()), before)
            self.assertFalse((root / "projects" / "amazon-review-scraper" / "data").exists())
