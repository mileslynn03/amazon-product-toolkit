# Amazon Review Scraper GUI · 亚马逊评论深度抓取与翻译工具

[English](README.md) | **简体中文**

带本地网页界面的独立评论抓取子项目：使用自己的浏览器会话认证，按 ASIN、市场与星级深度翻页，可选 LLM 翻译并导出 Excel 原译文对照。

本项目属于 [Amazon Product Toolkit](https://github.com/mileslynn03/amazon-product-toolkit)。实现、界面资源、测试、启动脚本与教程均在当前目录，可完整复制此目录或使用专属源码 ZIP 独立运行，无需工具箱根目录文件。

作者：[mileslynn03](https://github.com/mileslynn03) · AI 开发协作：[OpenAI Codex](https://github.com/codex) · [MIT 许可证](LICENSE) · [项目标识与版本](project.json)

## 运行环境

- Windows 11 或 macOS 14+，本地图形桌面。
- 64 位 Python 3.10+，推荐 3.11 / 3.12，需先自行安装。
- 首次安装依赖与 Chromium、访问目标站点需要网络；可选翻译还需访问模型接口。
- 项目目录可写，建议至少预留 2 GB 安装空间；无需 Node.js、Docker 或数据库服务。

## 一键运行

1. 完整复制当前 `amazon-review-scraper` 目录到可写位置，或解压子项目专属源码 ZIP。
2. Windows 双击 `start_windows.bat`；macOS 双击 `start_macos.command`，也可执行 `bash start_macos.command`。
3. 选择终端提示语言。首次在子项目目录创建 `.venv`，安装依赖及 Chromium，完成后打开 `http://127.0.0.1:8000/`。
4. 保留终端，按 **Ctrl+C** 正常退出；网页中英文在顶部另行选择。

也可在当前目录执行：

```bash
python launcher.py --lang zh
```

macOS 可使用 `python3`。支持 `--setup-only`、`--check`、`--no-open` 和 `--port 8001`。这是 Python 源码版，尚非免安装 EXE / APP。

## 使用流程

1. 输入一个或多个 ASIN，选择市场；快速扫描用于读取详情页样本。
2. 深度抓取前，在站点会话中完成对应市场的登录与评论列表认证，再点击验证并保存。
3. 选择星级、可选的每组合上限与评价来源地区限制。
4. 开始采集，逐页保存；失败或停止后可重试未完成组合，与已有结果去重合并。
5. 可选填写自己的 OpenAI 兼容或 Anthropic 原生接口、模型、API Key 与目标语言进行翻译。
6. 导出 Excel，保留任务结果、评论原文和可用译文。采集结束后自动关闭任务浏览器。

[完整中文教程](docs/USER_GUIDE.zh-CN.md) · [English guide](docs/USER_GUIDE.en.md) · [开发与测试](docs/DEVELOPMENT.md)

## 数据与原入口兼容

独立启动时，结果在当前目录的 `data/`，会话在 `storage/`。原工具箱根目录的启动脚本调用同一份实现，继续使用工具箱根目录原有的 `.venv`、`data/` 和 `storage/`。两种启动模式之间不自动复制数据。

同时运行时使用不同端口。其他项目身份占用端口时会提示，不会强行结束进程。高级用户可显式设置 `AMAZON_REVIEW_HOME` 指定可写的数据与会话目录，请妥善保管。

采集不需要付费抓取服务 API；可选 LLM 翻译使用自己的模型服务，可能收费。API Key 不持久保存，评论标题和正文会发送至所配置接口。

## 能力边界与验收

深度翻页读取站点实际提供且可访问的页面，不保证全部评论。上限按 ASIN × 市场 × 星级分别计算；重叠星级在同采集市场内去重，不同市场分别保留。采集样本的星级分布不代表商品总体评价分布。

20 个站点属于配置范围，尚未逐站完成真实采集验收。字段缺失与访问失败会明确记录。真实采集、缓存恢复和离线测试的证据范围见工具箱的[验收记录](https://github.com/mileslynn03/amazon-product-toolkit/blob/main/docs/VERIFICATION.md)。

## 测试与源码打包

在当前目录使用已安装依赖的解释器执行：

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
python build_release.py
```

打包脚本将带版本的源码 ZIP、SHA-256 校验文件写入 `dist/`，ZIP 内附文件清单。只打包明确允许的源码、界面、测试、教程、启动脚本与许可证，不包含结果、会话、虚拟环境和日志。打包只创建本地产物，不会自动新建仓库或发布 GitHub Release。
