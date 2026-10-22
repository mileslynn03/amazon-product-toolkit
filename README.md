# Amazon Product Toolkit

**English** | [简体中文](README.zh-CN.md)

By [mileslynn03](https://github.com/mileslynn03) · [User guide](projects/amazon-review-scraper/docs/USER_GUIDE.en.md) · [GitHub](https://github.com/mileslynn03/amazon-product-toolkit) · [MIT License](LICENSE)

## Amazon Review Scraper GUI

**An open-source Amazon review scraper with a local web UI for authenticated pagination, batch ASINs and Excel export.** Sign in to your own Amazon account, collect reviews across multiple pages by market and star rating, optionally translate them with an LLM, and export the original and translated text side by side.

The review scraper is an **[independently runnable subproject](projects/amazon-review-scraper/README.md)** of Amazon Product Toolkit, with its own implementation, launchers, tests, guides and source release builder. Copy the complete subproject directory or build its source ZIP to run it separately. The toolkit's existing root launchers remain compatible and retain their original data/session paths.

Quick scan reads a product-page sample; deep collection follows the accessible review-list pagination. Each product × market × rating combination has its own optional cap. A finished task does not guarantee complete review coverage.

Dedicated product-information and keyword-based product collection are planned. The current title, brand and product-image lookup is supporting metadata, rather than a complete product / SKU collection module.

**[Current verification status](docs/VERIFICATION.en.md)** separates live collection evidence, historical data recovery and automated checks. Previous audits and repair notes are indexed in the [history archive](docs/history/README.md).

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

Complete instructions, launcher options and troubleshooting: [English guide](projects/amazon-review-scraper/docs/USER_GUIDE.en.md) · [中文教程](projects/amazon-review-scraper/docs/USER_GUIDE.zh-CN.md). The in-app **“?”** button also opens a guide.

## Frequently asked questions

### How do I scrape Amazon reviews beyond the first page?

Choose **Deep collection**, authenticate for the target market on the review list, then select ASINs, markets and rating filters. The tool follows available next-page or load-more controls, removes duplicates within a collection and saves after each page. It records whether a task reached its cap, had no usable next page, was stopped or failed. Amazon access restrictions and the pages served still limit what can be collected.

### Why does a quick scan return only a few reviews?

Quick scan reads the reviews currently embedded in the product detail page and does not paginate the full review list. For deeper collection, use Deep collection with a valid review-page session. Check the stop reason, selected market, rating, region filter and cap when counts are lower than expected.

### Can I batch download Amazon reviews to Excel?

Yes. Enter multiple ASINs and select markets and ratings. Export Excel includes task outcomes, original review titles and bodies, stated regions, and optional translations. Overlapping rating filters are merged within each product and collection market; records from different collection markets remain separate. Collected counts and rating distributions describe the selected sample, not the product's overall review distribution.

### Does the scraper need an API key? Can it translate reviews?

Review collection uses Playwright and your Amazon browser session; it does not require a paid scraping-service API key. LLM translation is optional and separately requires your own endpoint, model and API key. OpenAI-compatible Chat Completions and native Anthropic Messages are supported. Your provider's usage charges may apply; originals remain available alongside translations.

### Is there a Windows or macOS interface? Do I need to write code?

Both systems have launch scripts and a local browser interface. Install Python first, run the matching script and use the forms; you do not need to write collection code. This is a source distribution with automatic dependency setup, not a standalone EXE or APP. See the [environment](#environment) and [startup instructions](#one-click-start).

### What has actually been verified?

See the [current verification status](docs/VERIFICATION.en.md) for recorded live collection, maintainer feedback, historical recovery checks and fixed CI evidence. Twenty markets are configured; live acceptance has not been completed for every market. Verification records distinguish offline Chromium tests from live Amazon access and real LLM calls.

## Data and collection limits

- Results, sign-in sessions and the virtual environment live in `data/`, `storage/` and `.venv/`; Git excludes them. Session files contain sensitive cookies.
- The LLM API key remains in the current page and request memory and must be re-entered after a refresh. Review titles and bodies go to your configured endpoint.
- A retry reads from page one and merges without duplicates. It preserves existing results but does not resume at an exact page.
- A quick scan, review cap or missing next-page link does not establish complete Amazon review coverage. Authentication, restrictions and markup changes are reported as errors.
- Twenty markets are configured; live collection has not been validated on every market. Use reasonable request rates and follow site rules.

## License

This project is licensed under the [MIT License](LICENSE), Copyright (c) 2026 mileslynn03. Commercial use, modification, copying and redistribution are permitted, including use in proprietary projects. Copies or substantial portions of the software must retain the copyright and permission notices. The software is provided "AS IS", without warranty; see LICENSE for the complete terms.

The license covers the code, documentation and original assets provided by the project's author in this repository. Third-party dependencies and browser components retain their own licenses. Collected Amazon reviews, product images and other third-party content, as well as related trademarks, are not relicensed under this project's MIT License. Use of third-party services remains subject to their applicable terms.

## Project collaboration

[Contributors · Full contributor list](CONTRIBUTORS.md)

- **Author and project lead: [mileslynn03](https://github.com/mileslynn03)** — Requirements, product direction, real-world testing and acceptance.
- **AI development collaboration: [OpenAI Codex (@codex)](https://github.com/codex)** — Assistance with implementation, interface design, debugging, tests, documentation and launch scripts.

## Development and verification

See [development notes](docs/DEVELOPMENT.md) for manual setup, source layout and tests. Windows / macOS setup and regression checks run in [GitHub Actions](https://github.com/mileslynn03/amazon-product-toolkit/actions); consult the checks for the relevant commit.
