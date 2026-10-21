# User guide · Amazon Product Toolkit

[简体中文](USER_GUIDE.zh-CN.md) | **English** · [Project overview](../README.en.md)

By [mileslynn03](https://github.com/mileslynn03)

AI development collaboration: OpenAI Codex

## Start and stop

Install 64-bit Python first; 3.11 / 3.12 is recommended. Fully extract the project into a writable folder. See the [environment table](../README.en.md#environment).

Double-click `start_windows.bat` on Windows or `start_macos.command` on macOS. Choose `1` for Chinese terminal messages or `2` for English; Enter defaults to Chinese. This terminal choice is separate from the interface language in the top bar and the LLM target language.

The launcher creates `.venv`, installs project dependencies and Playwright Chromium, and opens your browser after the local server becomes ready. Initial downloads need internet access and can take several minutes. Later runs reuse the environment; changed requirements or a missing Chromium installation trigger setup again. The scripts do not install system Python. No separate Node.js, Docker or database installation is needed.

The service listens only on your computer, normally at http://127.0.0.1:8000/ . Keep the terminal open. To exit, stop active collection or translation, wait for results to save, then press **Ctrl+C** in the terminal. Closing the terminal abruptly may leave only the most recent successful checkpoint. Closing the browser tab does not stop the service. Launching again reuses a running service from the same project folder.

### Launcher options

Open a terminal in the project folder. Use `start_windows.bat` on Windows and `bash start_macos.command` on macOS.

| Option | Meaning |
| --- | --- |
| `--lang zh` / `--lang en` | Select terminal messages without the language prompt |
| `--setup-only` | Prepare dependencies without starting the service or opening the browser |
| `--check` | Check readiness without installing or starting |
| `--no-open` | Start without opening the default browser |
| `--port 8001` | Use another port and visit http://127.0.0.1:8001/ |

```bat
start_windows.bat --lang en
start_windows.bat --lang en --setup-only
start_windows.bat --lang en --port 8001
```

```bash
bash start_macos.command --lang en
bash start_macos.command --lang en --check
bash start_macos.command --lang en --port 8001
```

## 1. Products and markets

Enter 10-character ASINs, such as `B0G92M6VFM`, separated by new lines, spaces or commas. Choose one or more markets using checkboxes. The tool expands product × market × rating selections into independent tasks, with a maximum of 500 combinations per run.

The top navigation opens Collection settings, Results or Market sessions. Settings collapse when existing results are shown; click Collection settings to expand them. Choose Chinese or English in the top bar. Filters, pagination and expanded review text are retained when switching languages; product and review text stay in the original language unless translated.

## 2. Quick scan or deep collection

**Quick scan** reads reviews already displayed on a product detail page. Use it for a preview. It attempts to reuse a saved session when available, but the sample does not represent every review.

**Deep collection** opens the review list and follows supported next-page or load-more controls. Choose several rating filters; All is mutually exclusive with specific ratings. Each product × market × rating combination has its own limit of 1–10000 retained reviews.

## 3. Sign in and verify the review page

Enter an ASIN first, open Market sessions and click Sign in or Verify for each target market. Complete any sign-in and verification in the browser's review list, return to the tool, then click **Verify & save**. Reaching the account home page alone does not establish review-list access. An unsuccessful verification keeps the page open so you can complete authentication and try saving again.

Saved, awaiting verification means a local session is available to try. Verified means the tool completed an online check. Sessions are separate per market, and Amazon can require authentication again.

Keep the authentication browser open until collection ends; it is reused for collection. After the entire batch finishes, fails or stops, the task browser closes automatically. Login can be cancelled and times out after ten minutes. Login, collection and translation are mutually exclusive.

## 4. Filter by the review's stated region

**Keep only reviews from this market** is off by default. When enabled, the tool matches the review's date/region text against the selected market. For the UK, `Reviewed in the United Kingdom on ...` is retained; `Reviewed in Australia on ...` is excluded. Unrecognized regions are also excluded. Multiple markets each use their own region.

The collection market and the review's stated region are displayed separately. Hover over the date to see the original text. The rule uses the review's stated location, rather than inferring citizenship or residence.

The deep-collection limit applies after filtering. A page with only excluded reviews can still be followed by another page. Changing the setting affects a new collection and does not retroactively delete existing results.

## 5. Optional LLM translation

Enable LLM translation and fill in:

| Field | How to use it |
| --- | --- |
| Protocol | OpenAI-compatible Chat Completions or native Anthropic Messages |
| Endpoint | OpenAI: a Base URL such as `https://your-provider.example/v1` or a full `/chat/completions` URL. Anthropic: a root URL, a `/v1` Base URL or a full `/v1/messages` URL |
| Model / API key | Your provider's exact model ID and key; the key can be empty for a local endpoint without authentication |
| Target language | Independent of the interface language; Chinese, English, Japanese, German, French, Spanish, Italian, Portuguese or Korean options |
| Batch / timeout | 1–20 reviews and 5–180 seconds; defaults: 5 reviews and 90 seconds |
| Anthropic output limit | 128–65536 tokens, default 4096; also respect the chosen model's own limits |

Native Anthropic requests use `x-api-key`, `anthropic-version: 2023-06-01`, top-level `system` and required `max_tokens`. Only text blocks are parsed as translations; thinking blocks are ignored. Switching protocols clears the current key and connection-test state. Check the endpoint and model when using a custom gateway.

**Test translation connection** sends a short sample request. With automatic translation enabled, the task browser closes first, then review titles and bodies are translated. **Translate current results / retry failed** translates the existing batch without collecting again.

Originals remain intact when translation fails. Successful translations are reused for matching protocol, endpoint, model, target language and source text. Temporary errors receive up to three attempts; global authentication errors stop further requests. Stopping translation takes effect after the in-flight HTTP request returns or times out. Completed translations remain saved.

The key is used in page/request memory and is excluded from browser drafts, snapshots, local result files, logs and Excel. Re-enter it after a refresh. Review titles and bodies are sent to your endpoint; author names, dates and Amazon cookies are not included in translation requests. Endpoint configuration should not contain keys or other credentials in its URL.

## 6. Progress, checkpoints and retries

Each page is saved to `data/last_results.json` using a flushed temporary file and atomic replacement. Refreshing the page or reconnecting restores the current server state. After a service interruption, the most recent successful checkpoint is restored and unfinished combinations are marked interrupted. A save failure is shown explicitly; export current results and check disk space and folder permissions.

Retry all unfinished combinations from the summary, or one combination in Task details. Successful and explicitly empty combinations are skipped. Retries use the original market, rating, region rule and limit, keeping existing reviews and product metadata. A retry starts reading at page one and merges by review ID or source fingerprint. It does not resume at an exact page. If source text changes, its old translation is cleared to prevent mismatched text.

## 7. Counts and stop reasons

Counts describe each combination's latest attempt:

`Read entries = duplicates + other-market exclusions + unknown-region exclusions + entries beyond the cap + new reviews`

Reused reviews were retained before this attempt. Retained-in-combination counts include reused and new reviews. Reviews are also deduplicated across rating filters, so the sum of combination counts can exceed the unique review total. Older tasks with no recorded statistics show them as unrecorded; Excel leaves unknown counts empty.

Task details and Excel distinguish review-limit reached, no usable next page, detail-page scan complete, explicit no reviews, manual stop, not started, interruption and errors. A cap or unavailable next page does not prove that all Amazon reviews were collected.

## 8. Read and export

Results group reviews by product and market, with product titles/images when available and a sample rating distribution. Search titles, bodies or authors; translated text is searchable too. Filter by market or rating, sort, paginate and expand long text.

**Export Excel** contains a combination overview and review sheets deduplicated per product and market. Originals and translations are adjacent, alongside region/date, translation state, target language, model, protocol and stop/count details. Cross-market records stay separate. Missing product images use a placeholder.

The in-app **“?”** guide is available anytime and follows the interface language. Close it with Esc, the close button or the backdrop.

## Troubleshooting

### Python is missing or too old

Install 64-bit Python from [python.org](https://www.python.org/downloads/); 3.11 / 3.12 is recommended. On Windows, keep the Python launcher and select Add Python to PATH when available. Reopen the terminal after installation. Downloading only the Python source archive is insufficient.

### macOS cannot execute the file

Fully extract the project, open Terminal in its folder, and run:

```bash
chmod +x start_macos.command
./start_macos.command
```

Alternatively use `bash start_macos.command`. If macOS blocks the downloaded script, verify its source and use the system's own allow/open instructions for that file. There is no need to disable system security settings.

### Dependency or Chromium downloads fail

Keep the terminal error and check access to PyPI and Playwright's download services. Re-run when connectivity is restored; failed setup is not marked complete. Installer subprocesses inherit proxy environment variables and, on Windows, available system HTTP / HTTPS proxy settings. These are not written into project configuration. Follow your administrator's proxy/certificate setup when needed; do not disable TLS verification.

### Port 8000 is occupied

A running service from the same project folder is reused. Another program, checkout or older manually started service is left running. Close the relevant service yourself, or use `--port 8001` and the new URL shown in the terminal.

### A copied or damaged virtual environment fails

Virtual environments should not be copied between computers. Stop the service, rename `.venv` to `.venv.backup`, then re-run the launcher. Preserve `data/` and `storage/`; deleting collected reviews or sessions is unnecessary for an environment repair.

### Python certificate errors on macOS

Users of the python.org installer can use `Install Certificates.command` from that Python installation, following the [official macOS Python instructions](https://docs.python.org/3/using/mac.html), then run the launcher again.

### Authentication, collection or translation errors

Read Task details and the “?” guide. Complete review-page authentication for the relevant market, save and retry unfinished combinations. For LLM failures, check the protocol, endpoint, model, key and output limit. Failures do not delete the original text. Do not paste keys, session files or screenshots with personal information into public Issues.

## Updates and local files

For a Git checkout, stop the service, run `git pull`, then launch again. Changed dependencies trigger setup. For a ZIP download, extract the new version into a new folder and, with the service stopped, migrate `data/` and `storage/` if desired. Do not migrate `.venv`.

`data/last_results.json` stores the latest batch. `data/launcher.lock` is the setup lock file and can stay in place. `storage/login_state_<code>.json` contains market sessions. `.venv` stores local dependencies. Git excludes these directories.
