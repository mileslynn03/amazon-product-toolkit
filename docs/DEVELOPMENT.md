# Development / 开发说明

[中文介绍](../README.md) · [English overview](../README.en.md)

The user launchers require only Python's standard library before setup. They install project dependencies inside `.venv`, without changing global packages. `launcher.py` shares environment preparation and service identification across both operating systems. It does not download/install system Python or delete existing virtual environments, results or sessions.

## Manual installation / 手动安装

Windows PowerShell (calling the environment interpreter avoids execution-policy changes):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe server.py
```

macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python server.py
```

Visit http://127.0.0.1:8000/ . Manual `server.py` starts the same application, without opening the default browser. Use `.venv`'s Python for subsequent commands. No separately installed Node.js is required: Playwright supplies its driver runtime.

## Tests / 测试

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

Run these commands with the environment interpreter (or activate the environment first). Fixtures use local HTTP servers and Chromium, without real Amazon collection or paid LLM requests. Tests cover pagination, origin filtering, partial results, retries, cancellation, cache recovery, authentication, translation formats, exports, UI languages and launcher failure/recovery paths.

The GitHub Actions matrix prepares a fresh environment using each OS wrapper, checks that it can be reused, and runs tests using that environment's interpreter. macOS jobs cover Apple Silicon and Intel. Check the run linked to the current commit for actual results.

## Source map / 文件说明

| File / path | Purpose |
| --- | --- |
| `start_windows.bat`, `start_macos.command` | Select Python, handle double-click startup and leave installation errors visible |
| `launcher.py` | Environment lock, dependency/browser checks, local service detection and browser opening |
| `server.py` | Local FastAPI endpoints, SSE and worker orchestration |
| `task_manager.py`, `capture.py` | Thread-safe task state, checkpoints, merging, retry selection and counts |
| `scraper/browser.py`, `scraper/login.py` | Market sessions, manual verification and browser ownership |
| `scraper/crawler.py`, `scraper/parser.py`, `scraper/origin.py` | Pagination, parsing and review-region matching |
| `scraper/product.py`, `results.py`, `marketplaces.py` | Product metadata, deduplication and market configuration |
| `translation.py`, `exporter.py` | LLM protocols, caching and original/translated Excel export |
| `static/` | UI, Chinese/English messages and icons |
| `tests/` | Offline tests and browser fixtures |

`/api/health` reports only application identity and a hash of the checkout location, without review data, credentials or local paths. The launcher reuses a service only when both identities match. A busy port is never cleared automatically.

The installation marker is `.venv/.toolkit-setup.json`; it records the requirements fingerprint and Python version. It is written only after dependency imports and the matching Chromium executable are available. A changed requirements file or missing browser triggers setup; normal launches do not perform unconditional package upgrades.

Historical local repair/audit notes remain in `REPAIR_NOTES.md`, `PROJECT_REVIEW.md` and `COMPARISON_AMAZON_REVIEW_DOWNLOADER.md`. They describe their original dates and are not a current compatibility matrix.
