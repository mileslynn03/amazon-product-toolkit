# Amazon Product Toolkit

[简体中文](README.md) | **English**

By [mileslynn03](https://github.com/mileslynn03) · [User guide](docs/USER_GUIDE.en.md) · [GitHub](https://github.com/mileslynn03/amazon-product-toolkit)

A local toolkit for Amazon product research. The current **Review Collection** module collects reviews by product, market and rating, optionally filters the review's stated region, translates titles and bodies with an LLM, and exports originals, translations and task details to Excel. It runs on your computer without deploying a cloud service.

Dedicated product-information and keyword-based product collection are planned. The current title, brand and product-image lookup is supporting metadata, rather than a complete product / SKU collection module.

## Features

| Feature | What it does |
| --- | --- |
| Quick scan / deep collection | Read a detail-page sample or paginate the review list; multiple ASINs |
| Multiple markets and ratings | Checkbox selection; one task per product × market × rating |
| Review-region filter | Optionally exclude reviews from other or unrecognized regions |
| Sign-in and verification | Separate sessions per market and manual review-page authentication |
| Saving and retries | Save after each page and retry unfinished combinations without losing existing results |
| Counts and stop reasons | Separate duplicates, regional exclusions, caps and errors |
| LLM translation | OpenAI-compatible / native Anthropic protocols, side-by-side text and retries |
| Reading and export | Search, filters, pagination, product images and Excel comparisons |
| Chinese / English | Interface language selector and an in-app “?” guide |

## Environment

| Component | First-edition requirements / recommendations |
| --- | --- |
| Windows | Windows 11 and 64-bit Python; entry point: `start_windows.bat` |
| macOS | macOS 14 Sonoma or newer, Apple Silicon / Intel; entry point: `start_macos.command` |
| Python | At least 3.10; 64-bit 3.11 / 3.12 recommended; install Python first |
| Network | Initial dependency and Chromium downloads, access to selected Amazon sites, and your LLM endpoint if enabled |
| Disk / permissions | A writable project folder; allow at least 2 GB for installation (a project recommendation) |
| Other | A graphical desktop and modern browser; no separate Node.js, Docker or database installation |

OS baselines follow [Playwright's current system requirements](https://playwright.dev/python/docs/intro#system-requirements). See [Actions](https://github.com/mileslynn03/amazon-product-toolkit/actions) for automated results on each system and architecture. Automation does not certify live collection on every Amazon market.

## One-click start

### 1. Download and install Python

Choose **Code → Download ZIP** on GitHub and fully extract it into a writable folder, or clone:

```bash
git clone https://github.com/mileslynn03/amazon-product-toolkit.git
```

Install 64-bit Python 3.11 / 3.12 from [python.org](https://www.python.org/downloads/). On Windows, keep the Python launcher and enable Add Python to PATH if the installer offers it. **This is a source distribution with automatic dependency setup. Python must already be installed; this is not a standalone EXE / APP.**

### 2. Double-click the launcher

- **Windows:** double-click `start_windows.bat`.
- **macOS:** double-click `start_macos.command`. If a ZIP download has lost the executable permission, run `chmod +x start_macos.command` once from the project folder. Alternatively, run `bash start_macos.command`.

Select terminal messages: `1` for Chinese, `2` for English; Enter defaults to Chinese. The first run creates `.venv` and installs dependencies and Playwright Chromium. Later runs reuse them. Your default browser opens once the local service is ready, normally at **http://127.0.0.1:8000/**.

Keep the terminal open and use **Ctrl+C** to exit. Choose the web interface language separately in the top bar.

## Your first collection

1. **Add products:** enter one or more 10-character ASINs and choose markets. Use Quick scan for a preview.
2. **Authenticate for deep collection:** open Market sessions, sign in and complete verification on the review list, then return and click Verify & save.
3. **Set filters:** choose rating checkboxes and the per-combination limit; optionally keep only the local market's review region.
4. **Optional translation:** enter the protocol, endpoint, model, API key and target language; test the connection first if needed.
5. **Collect and read:** results save after each page. Failed or stopped tasks retain partial results and can be retried.
6. **Export:** Export Excel includes originals, translations, regions, task stop reasons and counts.

Complete instructions, launcher options and troubleshooting: [English guide](docs/USER_GUIDE.en.md) · [中文教程](docs/USER_GUIDE.zh-CN.md). The in-app **“?”** button also opens a guide.

## Data and collection limits

- Results, sign-in sessions and the virtual environment live in `data/`, `storage/` and `.venv/`; Git excludes them. Session files contain sensitive cookies.
- The LLM API key remains in the current page and request memory and must be re-entered after a refresh. Review titles and bodies go to your configured endpoint.
- A retry reads from page one and merges without duplicates. It preserves existing results but does not resume at an exact page.
- A quick scan, review cap or missing next-page link does not establish complete Amazon review coverage. Authentication, restrictions and markup changes are reported as errors.
- Twenty markets are configured; live collection has not been validated on every market. Use reasonable request rates and follow site rules.

## Development and verification

See [development notes](docs/DEVELOPMENT.md) for manual setup, source layout and tests. Windows / macOS setup and regression checks run in [GitHub Actions](https://github.com/mileslynn03/amazon-product-toolkit/actions); consult the checks for the relevant commit.
