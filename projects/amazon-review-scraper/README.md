# Amazon Review Scraper GUI

**English** | [简体中文](README.zh-CN.md)

An independently runnable Amazon review scraper with a local web UI. Authenticate in your own browser, paginate accessible review lists, collect multiple ASINs by market and rating, optionally translate with an LLM, and export originals and translations to Excel.

This is the review subproject of [Amazon Product Toolkit](https://github.com/mileslynn03/amazon-product-toolkit). Its implementation, assets, tests, launchers and documentation are contained in this directory. You can copy this entire directory or use its source ZIP without the toolkit's root files.

Author: [mileslynn03](https://github.com/mileslynn03) · AI development collaboration: [OpenAI Codex](https://github.com/codex) · [MIT License](LICENSE) · [Project identity / version](project.json)

## Environment

- Windows 11 or macOS 14+, with a graphical desktop.
- 64-bit Python 3.10+; 3.11 / 3.12 recommended. Install Python first.
- Internet access for dependency/Chromium setup, the selected Amazon site and your optional LLM endpoint.
- A writable project folder and at least 2 GB installation headroom. No Node.js, Docker or database service required.

## Start independently

1. Copy this entire `amazon-review-scraper` directory to a writable location, or extract the subproject source ZIP.
2. Double-click `start_windows.bat` on Windows or `start_macos.command` on macOS. On macOS, `bash start_macos.command` also works.
3. Select terminal language. Setup creates this subproject's `.venv`, installs dependencies and Chromium, then opens `http://127.0.0.1:8000/`.
4. Keep the terminal open. Use **Ctrl+C** to exit. Choose Chinese or English separately in the web interface.

Alternatively, from this directory:

```bash
python launcher.py --lang en
```

Use `python3` on macOS if needed. `--setup-only`, `--check`, `--no-open` and `--port 8001` are supported. This is a Python source distribution, not a standalone EXE / APP.

## Collect reviews

1. Enter one or more ASINs, then choose markets. **Quick scan** reads the detail-page sample.
2. For **Deep collection**, use Market sessions to sign in and authenticate on the review list, then Verify & save.
3. Choose rating filters, an optional per-combination cap and an optional local-review-region filter.
4. Start collection. Results save after each page; failed or stopped combinations can be retried with deduplication.
5. Optionally translate using your own OpenAI-compatible or native Anthropic endpoint, model and API key.
6. Export Excel for task outcomes, original reviews and available translations. The task browser closes at the end of collection.

[Full English guide](docs/USER_GUIDE.en.md) · [中文教程](docs/USER_GUIDE.zh-CN.md) · [Development and tests](docs/DEVELOPMENT.md)

## Local data and toolkit compatibility

An independent launch uses this directory's `data/` for results and `storage/` for sessions. The toolkit's root launch scripts delegate to this same implementation while preserving the toolkit root's existing `.venv`, `data/` and `storage/` locations. Data is not automatically copied between the two launch modes.

If both modes run at once, use different ports. An occupied port belonging to a different project identity is reported, not terminated. Advanced users can explicitly set `AMAZON_REVIEW_HOME` to a writable data/session directory; keep it private.

Review collection does not require a paid scraping API. Optional translation requires your own model service and may incur its charges. API keys are not persisted; review titles/bodies go to the configured translation endpoint.

## Limits and verification

Deep pagination follows the pages Amazon makes accessible; it does not guarantee all reviews. Caps apply per ASIN × market × rating. Overlapping filters are deduplicated within each collection market; market records remain separate. Collected rating distributions describe the selected sample.

Twenty markets are configured, with live acceptance still incomplete across markets. Missing fields and failed access are reported. See the toolkit's [verification record](https://github.com/mileslynn03/amazon-product-toolkit/blob/main/docs/VERIFICATION.en.md) for the distinction between live collection, recovery checks and offline tests.

## Test and build a source release

From this directory, using an interpreter with the dependencies installed:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
python build_release.py
```

The builder writes a versioned source ZIP, SHA-256 checksum and an in-archive file manifest under `dist/`. It includes source, UI, tests, guides, launchers and MIT text. Its explicit source allowlist excludes local results, sessions, virtual environments and logs. Building creates local artifacts only; it does not create a GitHub release or a separate repository.
