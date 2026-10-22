# Current verification status

[简体中文](VERIFICATION.md) · **English** · [Project overview](../README.md) · [History archive](history/README.md)

Reviewed on 2026-10-21 (Asia/Shanghai). Code and CI baseline: [ca13320](https://github.com/mileslynn03/amazon-product-toolkit/commit/ca133201c7a58fde366e11ffeb9149179611c5df). This update changes documentation only; it does not run live Amazon collection or paid LLM requests.

## Current assessment

The review module implements quick scans, authenticated deep pagination, market/rating combinations, region filtering, page checkpoints, retries, LLM translation and Excel export. The maintainer has reported successful deep collection and translation in actual use. The retained evidence has the following scope:

- **Live collection:** a US quick-scan snapshot contains 13 reviews for `B0G92M6VFM`. The maintainer's deep-collection feedback has not yet been consolidated into a public per-combination record of pages, filters and stop reasons.
- **Recovery and export:** historical iterations recorded preservation of 100 reviews, restoration of 401 reviews / 6 tasks, and later preservation of 37 reviews / 3 tasks. These are separate recovery checks at different times.
- **Automation:** the fixed CI run below passed on Windows, Apple Silicon macOS and Intel macOS. Tests use local pages, mock HTTP services and real Chromium, without Amazon access or paid model calls.

The pre-repair audit's negative delivery assessment is historical. Subsequent repairs are recorded in the [repair timeline](history/REPAIR_NOTES.md); this page distinguishes the available evidence from those original findings.

## Live collection and maintainer feedback

| Date | ASIN | Market | Mode / filters | Pages | Retained reviews | Status / stop reason | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-21 | B0G92M6VFM | US | Quick scan; no rating filter | One detail-page batch; all review page values are 1 | 13 reviews, 13 distinct IDs, all bodies nonempty | `success`; the old snapshot has no `stop_reason` field | Local `data/acceptance_B0G92M6VFM.json`; [initial record](history/REPAIR_NOTES.md#本次结果) |
| 2026-10-21 | Not consolidated | Not consolidated | Authenticated deep collection | Not recorded | No inferred count | Maintainer reports successful use; per-combination evidence remains to be consolidated | Maintainer feedback, not a new live test during this documentation update |
| 2026-10-21 | Not applicable | Not applicable | Live LLM translation | Not applicable | Not a collection count | Maintainer reports successful use; provider/model details were not retained as an acceptance record | Maintainer feedback; no model call during this update |

SHA-256 of the 13-review snapshot: `4C9039B99134759452679CBCED83F603C7D26C984B43A5EA7B49875E3B0F2A2C`. Snapshots and logs remain local; review bodies and sessions are not published.

The deep-collection feedback establishes reported successful use, but missing filters, page counts and stop reasons are not reconstructed from a configured cap multiplied by the number of combinations. The quick-scan snapshot is not a deep-pagination acceptance test.

## Historical recovery and export

| Historical check | Recorded result | What it establishes | Source and limits |
| --- | --- | --- | --- |
| Multi-select UI upgrade | 100 original reviews restored; pagination, search and 100-row Excel export checked | Existing results survived that upgrade and could be read/exported | [UI upgrade record](history/REPAIR_NOTES.md#界面与多选采集升级); the same-named local workbook still has 100 detail rows, so it is not treated as the original 13-review export |
| White UI, browser cleanup and region-filter upgrades | 401 reviews / 6 tasks restored; relevant records report an unchanged cache hash | Those upgrades preserved their existing results | [White UI record](history/REPAIR_NOTES.md#白底界面与中英文支持2026-10-21) and subsequent sections; not proof of 401 newly collected reviews |
| Page checkpoints, retries and guide upgrade | 37 reviews / 3 tasks and 22 successful translations retained; cache hash unchanged across restart/checks | That upgrade preserved the then-current data | [Checkpoint upgrade record](history/REPAIR_NOTES.md#逐页保存未完成组合重试数量说明与教程2026-10-21); not the current dataset size or a fresh translation-quality evaluation |

These counts are not additive, are not cross-market distinct-review totals and do not establish complete product-review coverage. Original local artifacts are not distributed with the repository.

## Automation and operating systems

Fixed evidence: [Windows and macOS · Run 39605796416](https://github.com/mileslynn03/amazon-product-toolkit/actions/runs/39605796416), commit `ca133201c7a58fde366e11ffeb9149179611c5df`. The following results were complete when checked. For later revisions, consult their corresponding [Actions runs](https://github.com/mileslynn03/amazon-product-toolkit/actions).

| Job | Python | Result | Scope |
| --- | --- | --- | --- |
| `windows-latest` | 3.11 | [Passed](https://github.com/mileslynn03/amazon-product-toolkit/actions/runs/39605796416/job/119241525357) | Windows wrapper setup/reuse and the full offline suite |
| `macos-latest` (Apple Silicon) | 3.11 | [Passed](https://github.com/mileslynn03/amazon-product-toolkit/actions/runs/39605796416/job/119241525418) | macOS wrapper setup/reuse and the full offline suite |
| `macos-15-intel` | 3.11 | [Passed](https://github.com/mileslynn03/amazon-product-toolkit/actions/runs/39605796416/job/119241525535) | Intel macOS wrapper setup/reuse and the full offline suite |

The baseline contains 123 `test_` methods: 14 capture/count tests, 13 launcher tests, 69 core regression tests and 27 translation tests. This count was checked from source; the suite was not rerun locally for this documentation update. Execution evidence comes from the linked CI run. Counts such as 26, 50, 69, 96 and 110 in historical notes refer to earlier suites.

Coverage includes replacement/append pagination, deduplication, caps, expired sign-in, region filtering, partial results, checkpoints, retries, interruption recovery, translation protocols/errors, Excel, UI languages and launchers. Chromium exercises local fixtures. These checks do not certify live collection for every product, market or session, or every manual desktop double-click experience.

See [development notes](DEVELOPMENT.md#tests--测试) for test commands and environment setup.

## Recording future acceptance tests

Update this page with per-combination evidence after a live test. Leave missing fields as "not recorded" rather than inferring pages, distinct counts or stop reasons from totals.

| Date / revision | ASIN | Collection market | Mode / rating / region filter | Combination cap | Pages read | Retained reviews | Status / stop reason | Local evidence file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| To be recorded in a future live test | — | — | — | — | — | — | — | — |

Twenty markets are configured; live acceptance has not been completed for every market. This document introduces no collection task or counting/deduplication change. Local caches, fixtures, cookies and API keys are not uploaded with it.
