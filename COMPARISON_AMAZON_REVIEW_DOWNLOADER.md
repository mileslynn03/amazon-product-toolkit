# Review Studio 与 amazon-review-downloader 源码对比

检查日期：2026-10-21（Asia/Shanghai）。

结论：两个项目的基础用途高度重合，但实现重心不同。对方在自动扩展采集范围、结构化评论字段、命令行和安装分发方面更完整；本项目在评论阅读、多市场组合、登录验证、任务状态与刷新恢复方面有明确优势。不能仅凭对方 README 判断其“采得全、运行更稳定”，本次离线复现发现它的覆盖策略与任务管理仍有缺陷。

## 1. 检查范围与版本

- 本项目：本地当前文件，目录 `D:\AI coding\Amazon Review`。当前目录不是 Git 仓库，使用源码 SHA-256 固定本次检查范围。
- 对方：[mridulgupta369/amazon-review-downloader](https://github.com/mridulgupta369/amazon-review-downloader)，本次克隆的 main 提交为 `259dc7181d241fc5724ec3546f9d5d29a15cbf29`，提交日期为 2026-08-08。下文源码链接均固定至该提交。
- 方法：读取双方核心源码、执行各自已有离线测试，再做针对性离线复现。没有使用真实 Amazon 账号登录，没有对两者做新的线上抓取成功率或吞吐量比较。
- 本次没有修改业务代码、登录态或已有评论结果。新增的是本报告及 `data/comparison_audit_20261021/` 下的复现脚本和结果。
- 对方具有 v1.0.0 Release，API 返回一个 `AmazonReviewDownloader.exe` 资产，大小 55,903,019 字节；本次只验证资产存在，没有下载或运行。该 Release 与审查的 main 提交不是同一版本标识，不能把源码检查等同于安装包验收。[Release](https://github.com/mridulgupta369/amazon-review-downloader/releases/tag/v1.0.0)

需要更新此前判断：本项目最新版已经支持多国家、多星级组合、独立站点浏览器上下文，以及最近一轮完成结果的持久化。它已不再是早期的单站点、纯内存版本。

## 2. 功能设计对比

下表中的“支持”指源码已实现，不能替代真实站点验收。

| 维度 | 本项目：Review Studio | amazon-review-downloader | 实际差异 |
| --- | --- | --- | --- |
| 产品流程 | 配置采集、维护会话、阅读与筛选评论、导出 | 输入商品、自动等待登录、下载结果文件 | 本项目更接近评论研究工作台，对方更接近下载器 |
| 输入 | ASIN；支持空格、换行、中英文逗号/分号分隔 | ASIN 与商品链接，自动提取 ASIN | 对方更便于直接粘贴商品链接 |
| 多商品 | 最多 100 个 ASIN；最多展开 500 个组合 | 多 ASIN 顺序采集，接口未设置同类数量上限 | 本项目有明确任务规模约束 |
| 市场 | 20 个站点配置，可同时复选 | UI 提供 10 个市场，选择一个，或逐 ASIN 自动探测首个匹配市场 | 本项目能明确要求同一 ASIN 在多个市场采集；对方主要为每个 ASIN 选择一个市场 |
| 自动识别市场 | 无 | 有，按预设域名顺序探测 | 对方减少配置步骤，但探测只检查 HTTP 200 和部分错误文案，不能保证判断正确 |
| 快速模式 | 商品详情页内嵌评论；不要求先保存会话 | fast 是少量筛选组合；Web 仍先进入登录检查 | 两个“快速”不是相同含义 |
| 星级 | 具体星级、好评、差评可复选，“全部”独占；每个组合有自己的任务状态 | 1–5 星复选与好评/差评快捷选择，转化为采集计划 | 本项目更显式，对方更自动化 |
| 采集范围 | 对每个所选星级翻页；每组合上限 1–10000 | 星级、排序、已购、变体、关键词等组合后合并去重 | 对方在拓展可访问评论集合方面策略更丰富 |
| 采集上限 | 用户可指定每组合条数 | fast/standard/max 策略；浏览器每 segment 默认最多 50 批 | 对方没有与本项目相同的最终条数上限控件 |
| 分页 | 追加“加载更多”与传统下一页均有实现和测试 | 浏览器引擎实际只点击“加载更多” | 对方的解析器识别传统下一页，但浏览器执行器未接上 |
| 登录交互 | 用户完成后点“验证并保存”，验证目标商品评论页可读 | 根据站点认证 cookie 自动判断，完成后自动继续 | 对方步骤少；本项目验证依据更接近实际任务目标 |
| 人工验证 | 检测到拦截后报告失败，用户完成认证后重新启动 | 有界面时等待人工完成 CAPTCHA，并尝试继续 | 对方操作连续性更好；两者均不是自动解决验证码 |
| 阅读评论 | 商品标题/图/品牌、评分分布、正文、关键词搜索、市场/评分筛选、排序、分页 | 显示采集进度、日志、结果统计、文件下载 | 本项目的主要产品差异在这里 |
| 进度 | 已完成组合数、当前页与条数；没有 ETA | 批次、segment、耗时、估算百分比和 ETA | 对方信息更多，但估算受采集策略与未知总量影响 |
| 状态恢复 | 页面初始化与 SSE 重连恢复完整快照；重启恢复最近一轮完成结果 | 有 status 接口，但前端没有初始化调用；SSE 无初始快照 | 本项目恢复流程更完整 |
| 输出 | 一个 Excel：组合总览、按 ASIN 与市场去重的明细、状态原因 | 每商品和合并文件；CSV/JSON/JSONL/XLSX，Web 固定前三类 | 对方更便于后续程序分析；本项目更便于核对各组合结果 |
| 命令行 | 没有独立用户 CLI | 有浏览器/HTTP 引擎、cookie、代理、限速等参数 | 对方适合脚本与自动化使用 |
| 安装与分发 | 手工安装 Python 依赖、Playwright Chromium，再启动服务 | Windows/macOS/Linux 启动脚本、环境检查、浏览器自动选择、PyInstaller 打包与 exe Release | 对方对非开发者更友好 |
| 公网多人服务 | 无用户认证与租户隔离 | 同样没有；全局单任务 | 两者目前都按本地个人工具设计 |

功能核对入口：本地 [server.py](</D:/AI coding/Amazon Review/server.py:61>)、[static/app.js](</D:/AI coding/Amazon Review/static/app.js:344>)；对方 [Web 服务](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/webapp/server.py#L147)、[页面配置](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/webapp/templates/index.html#L31)、[采集计划](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/segments.py#L131)。

## 3. 架构与代码组织

| 层次 | 本项目 | 对方 | 评价 |
| --- | --- | --- | --- |
| Web | FastAPI + Pydantic；输入参数有类型、范围和组合数校验 | Flask，直接解析 JSON、手动处理字符串与数组 | 本项目接口约束更明确；不能据框架名称推断爬取速度 |
| 浏览器执行 | 全局单线程执行器；登录和采集都提交给同一线程 | 每轮任务新建线程；在该线程的上下文管理器中创建、使用、关闭浏览器 | 两者正常顺序流程均考虑了 Playwright 同步 API 的线程归属 |
| 会话生命周期 | 一个浏览器进程、按市场缓存 BrowserContext；storage_state 文件按站点隔离 | 一个持久浏览器 profile；在一轮中 retarget 不同产品/域名 | 本项目更强调市场环境隔离；对方保留的浏览器状态更完整 |
| 解析 | Playwright Locator 逐字段读取，返回 dict | page.content 获取 HTML，再由 BeautifulSoup/lxml 解析为 dataclass | 对方解析层更容易脱离浏览器单测和复用；本项目不需要额外 HTML 解析依赖 |
| 采集编排 | server 展开组合，crawler 负责一个组合 | segments 生成计划，scraper 执行，store 聚合 | 对方已有独立策略层；本项目更容易逐组合展示原因 |
| 状态 | TaskManager、RLock、阶段、run_id、instance_id、revision | 全局 Job dataclass，线程直接写属性 | 本项目状态一致性处理更细 |
| 导出 | pandas + openpyxl，一次生成工作簿 | csv/json 标准库 + openpyxl，每格式独立导出 | 对方依赖更轻、单格式失败不影响其他格式；本项目组合总览更直观 |

本地对应：[执行器](</D:/AI coding/Amazon Review/server.py:29>)、[会话缓存](</D:/AI coding/Amazon Review/scraper/browser.py:87>)、[状态管理](</D:/AI coding/Amazon Review/task_manager.py:12>)。对方对应：[BrowserScraper](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/browser_scraper.py#L113)、[Review 数据模型](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/models.py#L13)、[ReviewStore](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/store.py#L43)。

### 3.1 采集策略：对方覆盖范围设计更丰富，但最大模式有执行缺陷

本项目 `reviews_url()` 主要设置星级参数；`crawl()` 对该页面持续点击翻页。选择多个星级会运行多个组合，再按商品和市场去重。它没有自动切换最近/最有帮助、仅已购、当前变体、关键词来扩展集合。因此，把 cap 设为 10000 只代表本地允许的最大收集条数，并不能让站点提供 10000 条评论。[本地 URL 与星级](</D:/AI coding/Amazon Review/marketplaces.py:55>)、[本地翻页循环](</D:/AI coding/Amazon Review/scraper/crawler.py:169>)。

对方将请求拆成 core、rerank、keyword 三阶段；默认 max/all-stars 生成 292 个 segment，standard 生成 22 个，fast 只取前 4 个。它把单组合达到 100 条作为可能被截断的信号，并对被标记的星级运行关键词。这个 100 条阈值来自该仓库的代码假设，本次没有重新在线验证为所有市场通用规则。[对方计划实现](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/segments.py#L30)。

但浏览器 `run()` 在任一阶段连续 6 个 segment 无新增时直接跳出整个循环，和“前一阶段不应阻止后续关键词阶段”的注释矛盾。离线模拟 core 有新增、rerank 连续重复，结果只执行 18/292 个 segment，keyword 执行 0 个。HTTP 引擎对应停止判断限定了 keyword 阶段，没有这个完全相同的条件缺陷。[浏览器停止条件](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/browser_scraper.py#L545)。

建议借鉴“独立采集策略层”，保留本项目的失败分类，并对阶段切换、重复、达到预算、没有新增等停止条件建立测试；不要直接复制对方的循环。

### 3.2 分页：本项目兼容性更完整

本项目 `_next_button()` 同时寻找 show-more 与传统下一页链接，等待评论 ID/文本签名变化，而不是只等待节点数增加；已有离线 Chromium 测试覆盖追加与整页替换。

对方 `_has_next_page()` 虽能识别传统下一页，但 BrowserScraper 实际调用的 `_click_show_more()` 只查 show-more。复现时，解析器返回有下一页，执行器却只保留第一页。点击异常和等待后节点不增长也会直接结束，不能充分区分“到末页”和“翻页失败”。[本地分页](</D:/AI coding/Amazon Review/scraper/crawler.py:65>)、[对方执行器](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/browser_scraper.py#L369)。

### 3.3 登录：对方更省操作，本项目验证更严格

本项目保存前会在独立标签页验证对应 ASIN 的评论可读取，识别登录重定向、HTTP 错误和人工验证；失败时可保留认证页面供重试。保存后维持同一个浏览器上下文。`saved` 与 `verified` 区分文件存在和已在线验证，但 deep 接口仍允许用 saved 会话尝试，并不保证每次任务都成功。[本地验证](</D:/AI coding/Amazon Review/scraper/login.py:78>)、[会话状态](</D:/AI coding/Amazon Review/scraper/browser.py:32>)。

对方使用 `launch_persistent_context` 保存完整浏览器 profile，自动选择 Chrome、Edge 或 Chromium；检测指定域名下存在认证 cookie 就继续，用户无需手动点保存。这个判断没有验证目标评论页可读；后续列表页被要求登录时，才记录 login_blocked。它更便捷，但不能据此认为其登录成功率更高。[对方自动登录判断](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/browser_scraper.py#L270)。

合理的改进方向是“自动检测认证完成，再执行目标评论页验证”，兼顾便捷与可靠；保留人工重试和取消入口。

### 3.4 数据模型：对方字段丰富，本项目市场归属更清楚

本项目字段包括评论 ID、ASIN、采集市场、评分、标题、正文、作者、原始日期、已购、原始帮助数文案、采集页码；聚合后另有 matched_filters 和 task_ids。对方另有 author_id、Vine、变体、评论图片、评论原链接、首次发现 segment，并把可解析日期和帮助数转为结构化值。[本地 parser](</D:/AI coding/Amazon Review/scraper/parser.py:60>)、[对方 parser](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/parser.py#L273)。

注意双方 country 字段语义不同：本项目是采集市场，例如 in；对方来自评论日期中的来源国家，例如 India、Egypt。使用同一份对方仓库 HTML 样本时，两者均解析 9 条，其中对方识别出 1 条来源国不为 India，本项目则将 9 条都标记为采集市场 in。这不是同一字段的准确率竞赛，而是两个维度，应分别保存 marketplace 与 review_country。

另一个明确缺口是新布局的帮助数：对方识别 helpfulVoteWidget，本项目只读取 helpful-vote-statement。合成 DOM 复现中，对方得到 12，本项目为空。当前前端“有帮助最多”又从原始字符串取第一个数字，对英文单数、不同千位分隔符等不够稳健。[本地排序](</D:/AI coding/Amazon Review/static/app.js:344>)、[对方帮助数解析](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/parser.py#L206)。

ID 处理也有取舍：对方规范化常见 ID 前缀并尝试 permalink，但没有 ID 就丢弃该节点；本项目对无 ID 的有效内容使用指纹保留，但没有统一规范化所有 ID 前缀。本项目去重包含 ASIN、市场，对方 store 的合并键是 ASIN、review_id，不含采集市场。[本地去重](</D:/AI coding/Amazon Review/results.py:20>)、[对方 ID 提取](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/parser.py#L259)。

通过 store API 模拟同一 ASIN、同一评论在两个市场采集，对方单商品文件路径相同、合并后只有 1 行，本项目保留 2 行。此复现说明其存储模型不适合本项目的跨市场需求；对方 UI 本身会去重 ASIN，也不能显式要求这种同 ASIN 双市场采集，不能把该模型限制描述成其普通 UI 流程必然丢数据。

### 3.5 SSE 与启动互斥：本项目更稳健

本项目给每个订阅者独立队列，首次连接发送快照，前端先读取 status，并用 instance_id/revision 防止过期事件覆盖当前状态。`start_run()` 在锁内设置 running，再提交工作线程。[本地广播](</D:/AI coding/Amazon Review/task_manager.py:91>)、[前端版本检查](</D:/AI coding/Amazon Review/static/app.js:118>)。

对方所有 SSE 连接共享同一个 Job.events；两个消费者会取走不同事件，多个标签页看到的进度可能不一致。它虽有 status 接口，前端 app.js 没有调用该接口来恢复，服务器也没有连接时快照。[对方事件流](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/webapp/server.py#L508)。

它的 running 在工作线程进入 `_run_batch()` 后才置真。模拟线程尚未被调度时，连续两次 start 都返回 200；若启用自动市场探测，进入 `_run_batch()` 前还会先执行网络探测，扩大这个窗口。该缺陷不是正常操作一定发生，但有明确的并发入口。[对方启动接口](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/webapp/server.py#L410)。

### 3.6 持久化：两者都不能直接视为完整断点续采

本项目 `_persist()` 采用临时文件替换，完成后重启能恢复最近一轮评论、任务和商品信息，且不会恢复成已验证登录。但 `add_result()` 不落盘，通常整轮 `mark_complete()` 才写入。已复现完成一个组合、尚未调用 mark_complete 时磁盘没有新结果。进程中途崩溃仍可能丢失本轮已取得的数据，也没有恢复到页面游标继续执行的逻辑。[本地持久化](</D:/AI coding/Amazon Review/task_manager.py:49>)、[完成写入](</D:/AI coding/Amazon Review/task_manager.py:153>)。

对方按 segment 写 checkpoint，CLI 会 load_checkpoint，属于更细的恢复粒度；Web 入口创建新 store，却没有调用 load_checkpoint，因此不能把 CLI 的恢复能力算作 Web 已支持。checkpoint 没有保存 capped_segments，续跑可能损失关键词阶段所依赖的截断判断；文件名也只按 ASIN 区分。即便有 checkpoint，当前 segment 中途退出的数据也可能尚未保存。[对方 checkpoint](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/store.py#L153)、[CLI 恢复入口](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/cli.py#L205)。

建议本项目先做到“每组合落盘、保留多轮历史、异常退出标记”，再做“每页检查点与断点续采”。

### 3.7 错误与完成状态：本项目更显式，对方仍可能过早宣告完成

本项目 CrawlError 携带错误类型与部分评论；server 将失败、空结果、取消分别写入 outcomes。页面无法识别不会自动算作无评论。遇到 cap 时则正常返回 success；这意味着完成用户给定任务，不意味着全部评论都采集完了。建议额外记录 stop_reason，区分达到上限、页面自然结束等情况。[本地错误](</D:/AI coding/Amazon Review/scraper/errors.py:4>)、[本地任务结果](</D:/AI coding/Amazon Review/server.py:179>)。

对方对 login/notfound 会明确失败，但一般 segment 异常被转换为 0 新增，外层仍把该 segment 标记为 completed。离线复现让首个 segment 超时，程序没有向调用者抛错，保留 1 条详情页种子并记录 1 个 completed segment。Web 的成功判断只检查非空数据和 error；在这种路径下会误把部分种子结果当作成功。该库的丰富策略不等于准确的完成判定。[对方 segment 异常处理](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/browser_scraper.py#L387)、[Web 结果判断](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/webapp/server.py#L286)。

### 3.8 导出：对方格式更多，本项目保留组合审计与文本防护

本项目 Excel 总览保留每个组合的状态和原因，明细按商品与市场合并去重，并写入匹配筛选。对方提供多种格式，每格式独立捕获异常，适合程序消费；导出失败后仍应在界面体现，而不是仅记日志。

本项目 `_safe_text()` 会将以公式前缀开始的字符串作为文本导出；对方 XLSX 直接 append 原始字段。离线使用标题 `=1+1`，本项目单元格类型是字符串 s，对方是公式 f。这里没有执行 Excel 公式，只检查生成的工作簿类型。[本地文本处理](</D:/AI coding/Amazon Review/exporter.py:16>)、[对方 XLSX 写入](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/store.py#L255)。

### 3.9 对方 CLI 有一个可复现的参数绑定缺陷

`build_plan` 的第二个参数是 stars，第三个才是 keywords；CLI 以两个位置参数调用，把关键词列表放进 stars。捕获 `--keywords battery,quality` 对应调用，结果是 positional 为 standard 与关键词数组，keyword 参数为空。因此自定义关键词没有按设计传入，Web 的星级调用则使用命名参数，没有这个同样的绑定错误。[对方 CLI 调用](https://github.com/mridulgupta369/amazon-review-downloader/blob/259dc7181d241fc5724ec3546f9d5d29a15cbf29/amazon_reviews/cli.py#L217)。

## 4. 测试与验证结果

| 验证项 | 结果 | 可以说明什么 |
| --- | --- | --- |
| 本项目 `python -m unittest discover -s tests -v` | 50 项全部通过，46.087 秒 | API 校验与互斥、登录验证与重试、两种分页、部分结果、SSE、前端筛选/分页、组合去重、结果恢复、线程与市场上下文都有覆盖 |
| 对方 `python tests/test_parser.py` | 30 个 test 函数全部通过 | 真实 HTML 样本解析、字段、总量、星级计划、导出、ASIN 提取、cookie 域与去重有覆盖 |
| 同一份对方 HTML 样本 | 双方均解析到 9 条 | 本项目能读取这个样本的基础评论，但不证明字段同样丰富，也不能证明在线成功率相等 |
| 合成新布局 | 对方帮助数为 12、Vine 为真；本项目帮助数字段为空、无 Vine 字段 | 本项目确有字段覆盖缺口 |
| 对方关键词阶段模拟 | 18/292 个 segment 后结束，关键词执行 0 | “max 总会进入关键词阶段”不成立 |
| 对方启动调度窗口 | 两次 start 均 200 | running 未原子保留，存在重复启动窗口 |
| 对方双 SSE 消费者 | 消费者分别拿到 sequence 1 与 2 | 同一事件没有广播给全部连接 |
| 公式样式文本导出 | 本项目 s；对方 f | XLSX 对外来文本处理不同 |
| 本项目中途持久化 | 组合完成未落盘；整轮完成后恢复 1 行 | 已支持结果恢复，但没有本轮完整崩溃恢复 |

测试数量不代表代码质量评分。对方有来自真实页面的 HTML fixture，这值得本项目补齐；本项目的状态机和浏览器集成测试覆盖更广，对方现有测试没有覆盖本次暴露的多数运行时问题。

本项目测试启动时有依赖弃用提示，但不影响本次 50 项通过；本次没有变更依赖环境。

## 5. 本项目值得优先改进的地方

### 第一优先：提升数据质量与结果可信度

1. 提取稳定的 Review 模型，区分 marketplace 与 review_country，补齐 helpful_votes、Vine、variant、permalink、images，保留原始字段便于追溯。
2. 补 helpfulVoteWidget 和不同 ID 形式的解析与去重测试；保留无 ID 评论的内容指纹策略。
3. 每个组合结束即持久化；保留不同 run_id 的历史，明确记录异常中断，不要只覆盖 last_results。
4. 加 stop_reason、请求范围、去重后条数、可识别的站点评论总量；无法确定分母时不显示伪精确覆盖率。

### 第二优先：增加策略层，同时控制任务预算

1. 在现有 crawler 外新增独立采集计划，逐步加入最近/最有帮助、已购、变体等策略，不改变已有单组合错误语义。
2. 明确 quick 是详情页抽样；为深度模式配置请求/时间/评论总预算，避免把 500 组合与每组合 10000 条当作可稳定达到的能力。
3. 跨筛选去重时保留所有来源组合，而不是只保留首次来源；本项目 matched_filters/task_ids 已有基础。
4. 优先验证一个站点与一组商品的真实多页链路，再逐站标明验证时间与限制。

### 第三优先：改善开源项目的使用门槛

1. 接受商品链接并提取 ASIN；可以解析链接中的市场作为建议值，避免不必要的多站探测。
2. 增加启动脚本、依赖检查、端口占用提示；支持优先使用已安装 Chrome/Edge，并保留 Chromium 回退。
3. 补 CSV/JSON 导出和清晰的 CLI，再考虑 exe 打包；exe 的安装体验要独立验收。
4. 增加 LICENSE、CI 和脱敏 HTML fixtures，整理英文/中文 README、截图、验证范围与示例数据。当前双方根目录均未发现 LICENSE，不能把“公开仓库”当作已完善的开源发行。

## 6. 规模与部署方面的共同边界

两者均是单用户本地工具。FastAPI、Flask 或 SSE 不会自动提供用户隔离、排队配额或多进程一致性。当前架构不能仅靠提高 worker 数扩展。

本项目另外有几个需要在扩大数据量前验证的点：

- 追加式页面每轮会重新读取此前所有评论；通过 Locator 多次往返获取字段，可能比一次取 HTML 后本地解析更慢。这是源码推断，没有做同环境性能基准，不能给出倍数结论。
- 完整快照同时携带 results 和去重 reviews，且会重复合并、复制数据；前端虽每页只显示 12 条，但仍在内存加载、过滤全部结果。
- live progress 主要更新计数与文字，评论集合要等一个组合结束才 add_result；“实时条数”不等于逐条评论实时落盘、实时可读。
- 20 个站点是配置范围；无评论文案、本地化字段和真实页面结构尚未逐站验收。

## 7. 最适合的项目定位

建议定位为“支持多市场组合采集与结果核对的本地 Amazon 评论研究工作台”。主打中文阅读与筛选、严格状态、可恢复结果和可复现测试。采集覆盖策略、结构化字段与安装体验是下一阶段补强重点。

就本次证据而言，没有理由放弃当前项目、整体改用对方源码。对方的策略层、数据模型、轻量导出和分发方式值得参考；本项目已有的线程管理、登录验证、组合身份、错误分类和 SSE 恢复值得保留。

## 8. 复现产物

- [离线复现结果](</D:/AI coding/Amazon Review/data/comparison_audit_20261021/probe_results.json>)：包含具体结果、对方提交及本地源码 SHA-256；不含账号 cookie 或评论正文。
- [离线复现脚本](</D:/AI coding/Amazon Review/data/comparison_audit_20261021/probe_comparison.py>)：仅使用临时 store、Mock、本地 Chromium 和仓库已有 HTML；不会运行对方启动/打包脚本。

```powershell
python data/comparison_audit_20261021/probe_comparison.py --reference "对方仓库的本地路径" --project "D:\AI coding\Amazon Review"
```

复现前应把对方仓库切换到本报告记录的提交。运行需要双方源码已有依赖；所有采集 store 和测试导出均放在临时目录。脚本导入本项目会读取正常的结果快照用于模块初始化，但不会输出其内容或修改它；不会读取真实登录 cookie。
