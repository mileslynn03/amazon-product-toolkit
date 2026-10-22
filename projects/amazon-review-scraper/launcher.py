"""Standard-library bootstrap shared by the Windows and macOS launchers."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
from urllib.request import ProxyHandler, build_opener, getproxies
import venv
import webbrowser
from _runtime import APP_ID, PROJECT_ROOT

ROOT = PROJECT_ROOT
MIN_PYTHON = (3, 10)
MESSAGES = {
    "python": ("需要 64 位 Python 3.10+，推荐 3.11 / 3.12：https://www.python.org/downloads/",
               "64-bit Python 3.10+ is required; 3.11 / 3.12 is recommended: https://www.python.org/downloads/"),
    "creating": ("正在创建项目虚拟环境 .venv…", "Creating the project virtual environment .venv…"),
    "invalid": (".venv 无法使用。请将它重命名为 .venv.backup，再重试；不要从其他电脑复制虚拟环境。",
                ".venv is unusable. Rename it to .venv.backup and retry; do not copy virtual environments between computers."),
    "locked": ("另一个启动器正在准备环境，请等待它完成后重试。", "Another launcher is preparing the environment. Wait for it to finish, then retry."),
    "packages": ("正在安装 / 检查 Python 依赖，首次运行需要联网…", "Installing / checking Python dependencies. Internet access is needed on first run…"),
    "browser": ("正在安装 Playwright Chromium，首次下载可能需要几分钟…", "Installing Playwright Chromium. The first download may take a few minutes…"),
    "ready": ("环境已就绪。", "Environment ready."),
    "missing": ("环境尚未准备好；请正常运行启动脚本，或使用 --setup-only。", "The environment is not ready. Run the launcher normally, or use --setup-only."),
    "occupied": ("端口 {port} 已被其他程序或另一份项目占用。请关闭对应服务，或使用 --port 8001。",
                 "Port {port} is occupied by another program or checkout. Close that service, or use --port 8001."),
    "existing": ("本项目已在运行：{url}", "This project is already running: {url}"),
    "starting": ("正在启动：{url}\n请保留此终端；按 Ctrl+C 正常退出。", "Starting: {url}\nKeep this terminal open. Press Ctrl+C to exit gracefully."),
    "open": ("页面已就绪：{url}", "The page is ready: {url}"),
    "manual": ("无法自动打开浏览器，请手动访问：{url}", "Could not open a browser automatically. Visit: {url}"),
    "timeout": ("服务未能在 45 秒内就绪，请查看上方错误信息。", "The server was not ready within 45 seconds. Check the errors above."),
    "failed": ("启动失败：{error}\n请保留错误信息，查看 docs/USER_GUIDE.zh-CN.md 的故障排查。",
               "Startup failed: {error}\nKeep the error output and see troubleshooting in docs/USER_GUIDE.en.md."),
    "stopped": ("已停止。已有结果保留在本机。", "Stopped. Existing results remain on this computer."),
}


def message(key, lang, **values):
    return MESSAGES[key][1 if lang == "en" else 0].format(**values)


def project_id(root=ROOT):
    return hashlib.sha256(os.path.normcase(str(root.resolve())).encode("utf-8")).hexdigest()[:16]


def environment_python(root=ROOT):
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@contextmanager
def setup_lock(root, lang):
    """OS locks release on process exit, including after an interrupted install."""
    folder = root / "data"
    folder.mkdir(exist_ok=True)
    with (folder / "launcher.lock").open("a+b") as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(message("locked", lang)) from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


PROBE = """
import json, pathlib, struct, sys
result = {'python': list(sys.version_info[:3]), 'bits': struct.calcsize('P') * 8,
          'dependencies': False, 'browser': False}
try:
    import fastapi, pydantic, uvicorn, pandas, openpyxl
    from playwright.sync_api import sync_playwright
    result['dependencies'] = True
    with sync_playwright() as pw:
        result['browser'] = pathlib.Path(pw.chromium.executable_path).is_file()
except Exception:
    pass
print(json.dumps(result))
"""


def probe_environment(python, root=ROOT):
    if not python.is_file():
        return {}
    try:
        result = subprocess.run([str(python), "-c", PROBE], cwd=root,
                                capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def requirements_hash(root):
    """Include nested requirements so toolkit setup notices subproject changes."""
    seen = set()

    def content(path):
        path = path.resolve()
        if path in seen:
            return ""
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        included = []
        for line in text.splitlines():
            line = line.strip()
            for prefix in ("-r ", "--requirement ", "--requirement="):
                if line.startswith(prefix):
                    included.append(content(path.parent / line[len(prefix):].strip()))
                    break
        return text + "".join(included)

    return hashlib.sha256(content(root / "requirements.txt").encode("utf-8")).hexdigest()


def read_marker(root):
    try:
        return json.loads((root / ".venv" / ".toolkit-setup.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_ready(probe):
    return (tuple(probe.get("python", [])) >= MIN_PYTHON and probe.get("bits") == 64
            and probe.get("dependencies") and probe.get("browser"))


def prepare_environment(root, lang):
    python = environment_python(root)
    install_env = os.environ.copy()
    # Node's browser downloader does not read Windows' system proxy settings.
    for scheme in ("http", "https"):
        proxy = getproxies().get(scheme)
        if proxy and not install_env.get(scheme.upper()+"_PROXY"):
            install_env[scheme.upper()+"_PROXY"] = proxy
    with setup_lock(root, lang):
        if not python.is_file():
            if (root / ".venv").exists():
                raise RuntimeError(message("invalid", lang))
            print(message("creating", lang), flush=True)
            venv.EnvBuilder(with_pip=True).create(root / ".venv")
        probe = probe_environment(python, root)
        if not probe or tuple(probe.get("python", [])) < MIN_PYTHON or probe.get("bits") != 64:
            raise RuntimeError(message("invalid", lang))
        fingerprint = requirements_hash(root)
        if not probe.get("dependencies") or read_marker(root).get("requirements") != fingerprint:
            print(message("packages", lang), flush=True)
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                            "-r", str(root / "requirements.txt")], cwd=root, env=install_env, check=True)
            probe = probe_environment(python, root)
        if not probe.get("browser"):
            print(message("browser", lang), flush=True)
            subprocess.run([str(python), "-m", "playwright", "install", "chromium"], cwd=root, env=install_env, check=True)
            probe = probe_environment(python, root)
        if not is_ready(probe):
            raise RuntimeError(message("missing", lang))
        marker = root / ".venv" / ".toolkit-setup.json"
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(json.dumps({"requirements":fingerprint, "python":probe["python"]}), encoding="utf-8")
        temporary.replace(marker)
    print(message("ready", lang), flush=True)
    return python


def server_state(root, port):
    """Do not reuse an unrelated service, and never send localhost traffic to a proxy."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            pass
    except OSError:
        return "free"
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            info = json.loads(response.read(4096))
        if info.get("app") == APP_ID and info.get("project_id") == project_id(root):
            return "ours"
    except (OSError, ValueError):
        pass
    return "occupied"


def open_page(url, lang):
    try:
        opened = webbrowser.open(url)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(message("manual", lang, url=url), flush=True)


def serve(root, lang, port, no_open):
    import uvicorn
    url = f"http://127.0.0.1:{port}/"

    def when_ready():
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            if server_state(root, port) == "ours":
                print(message("open", lang, url=url), flush=True)
                if not no_open:
                    open_page(url, lang)
                return
            time.sleep(0.25)
        print(message("timeout", lang), flush=True)

    print(message("starting", lang, url=url), flush=True)
    threading.Thread(target=when_ready, name="toolkit-page", daemon=True).start()
    # The server owns the console signals and its existing graceful browser cleanup.
    uvicorn.run("server:app", host="127.0.0.1", port=port)
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Amazon Review Scraper GUI | Windows / macOS launcher")
    parser.add_argument("--lang", choices=("zh", "en"), help="Terminal language / 终端语言")
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--setup-only", action="store_true", help="Prepare environment without starting the app")
    group.add_argument("--check", action="store_true", help="Check readiness without installing or starting")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser automatically")
    parser.add_argument("--run-server", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    lang = args.lang
    if lang is None:
        lang = "en" if sys.stdin.isatty() and input("Language / 语言: [1] 简体中文  [2] English (1): ").strip() == "2" else "zh"
    try:
        if sys.version_info < MIN_PYTHON or struct.calcsize("P") != 8:
            raise RuntimeError(message("python", lang))
        os.chdir(ROOT)
        if args.check:
            ready = is_ready(probe_environment(environment_python())) and read_marker(ROOT).get("requirements") == requirements_hash(ROOT)
            print(message("ready" if ready else "missing", lang))
            return 0 if ready else 1
        if not args.setup_only:
            status = server_state(ROOT, args.port)
            if status == "ours":
                url = f"http://127.0.0.1:{args.port}/"
                print(message("existing", lang, url=url))
                if not args.no_open:
                    open_page(url, lang)
                return 0
            if status == "occupied":
                raise RuntimeError(message("occupied", lang, port=args.port))
        if args.run_server:
            return serve(ROOT, lang, args.port, args.no_open)
        python = prepare_environment(ROOT, lang)
        if args.setup_only:
            return 0
        command = [str(python), str(ROOT / "launcher.py"), "--run-server", "--lang", lang, "--port", str(args.port)]
        if args.no_open:
            command.append("--no-open")
        os.execv(str(python), command)
    except KeyboardInterrupt:
        print(message("stopped", lang))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(message("failed", lang, error=str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
