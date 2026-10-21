# Amazon Product Toolkit · 亚马逊商品工具箱

**简体中文** | [English](README.en.md)

作者：[mileslynn03](https://github.com/mileslynn03) · [完整教程](docs/USER_GUIDE.zh-CN.md) · [项目仓库](https://github.com/mileslynn03/amazon-product-toolkit)

面向亚马逊商品研究的本地工具箱。当前提供**评论采集**模块：按商品、市场和星级获取评论，筛选评价来源地区，可选调用 LLM 翻译，并将原文、译文和任务说明导出到 Excel。通过本机浏览器操作，无需部署云服务。

后续计划增加独立的商品信息采集和关键词商品采集模块；当前辅助读取商品标题、品牌、头图，不等同于完整商品 / SKU 信息采集。

## 当前功能

| 功能 | 说明 |
| --- | --- |
| 快速扫描 / 深度抓取 | 详情页样本或评论列表翻页，支持多 ASIN |
| 多市场、多星级 | 复选框选择；每个商品 × 市场 × 星级独立执行 |
| 评价地区筛选 | 可剔除其他地区及无法识别来源地区的评价 |
| 登录与认证 | 按站点保存会话，支持评论页人工认证 |
| 保存与重试 | 逐页保存，只补跑未完成组合，与已有结果去重合并 |
| 数量与结束原因 | 区分重复、地区剔除、上限与读取错误，不误报全量完成 |
| LLM 翻译 | OpenAI 兼容 / Anthropic 原生协议，原译文对照、失败重试 |
| 阅读和导出 | 搜索、筛选、分页、商品图、Excel 原译文对照 |
| 中英文界面 | 顶部语言切换与“？”使用教程 |

## 运行环境

| 项目 | 首版要求 / 建议 |
| --- | --- |
| Windows | Windows 11，64 位 Python；一键入口 `start_windows.bat` |
| macOS | macOS 14 Sonoma 或更新版本，Apple Silicon / Intel；一键入口 `start_macos.command` |
| Python | 最低 3.10，推荐 64 位 3.11 / 3.12；需先自行安装 |
| 网络 | 首次下载 Python 依赖与 Chromium，以及访问所选亚马逊站点；LLM 翻译还需访问所填接口 |
| 磁盘与权限 | 项目目录可写；建议至少预留 2 GB 安装空间（本项目的预留建议） |
| 其他 | 本地图形桌面和现代浏览器；无需额外安装 Node.js、Docker 或数据库 |

操作系统基线依照当前 [Playwright 官方系统要求](https://playwright.dev/python/docs/intro#system-requirements)；各系统、架构的自动化验证状态见 [Actions](https://github.com/mileslynn03/amazon-product-toolkit/actions)。自动化验证不等于所有亚马逊站点均已通过真实采集验收。

## 一键运行

### 1. 下载项目和安装 Python

从仓库页面选择 **Code → Download ZIP**，完整解压到自己的可写目录；或使用 Git：

```bash
git clone https://github.com/mileslynn03/amazon-product-toolkit.git
```

先从 [Python 官网](https://www.python.org/downloads/)安装 64 位 Python 3.11 / 3.12。Windows 安装时保留 Python 启动器；安装器提供时勾选 Add Python to PATH。**这是一键准备依赖并启动的源码版，需要先安装 Python；尚非免安装的 EXE / APP。**

### 2. 双击对应脚本

- **Windows：**双击 `start_windows.bat`。
- **macOS：**双击 `start_macos.command`；若 ZIP 解压后执行权限缺失，在项目目录终端运行 `chmod +x start_macos.command`，之后双击；也可运行 `bash start_macos.command`。

选择终端提示语言：`1` 中文 / `2` English，回车默认中文。首次会自动创建 `.venv`、安装依赖与 Playwright Chromium；后续复用。页面就绪后会打开默认浏览器，默认地址为 **http://127.0.0.1:8000/**。

保留启动终端，退出时按 **Ctrl+C**。网页语言在顶部菜单独立选择。

## 五分钟上手

1. **添加商品：**输入一个或多个 10 位 ASIN，选择市场；想预览先用快速扫描。
2. **深度采集：**打开“站点会话”，登录对应市场，在评论列表页完成认证，回到工具点“验证并保存”。
3. **设置条件：**选择多个星级、每组合上限，可选“仅保留本站国家/地区的评价”。
4. **可选翻译：**填写 LLM 协议、地址、模型、API Key 和目标语言，可先测试连接。
5. **采集和查看：**开始后按页保存；失败或停止时保留部分结果，可重试未完成组合。
6. **导出结果：**点击“导出 Excel”，保留评论原文、译文、地区、任务结束原因和数量统计。

完整步骤、启动参数、环境修复和常见问题：[中文教程](docs/USER_GUIDE.zh-CN.md) · [English guide](docs/USER_GUIDE.en.md)。程序内顶部 **“？”** 也可随时查看教程。

## 数据与能力边界

- 结果和登录态分别保存在 `data/`、`storage/`；虚拟环境保存在 `.venv/`，均不会提交到 GitHub。登录会话含敏感 cookie，请自行妥善保管。
- LLM API Key 只在当前页面和请求内存中使用，刷新后需重填；评论标题与正文会发送到你配置的接口。
- 重试从第一页重新读取并合并去重，保留已有结果；不提供精确页码续传。
- 快速扫描、达到上限或没有下一页入口均不保证取得全部评论。站点可能要求认证、限流或变更页面，程序会明确记录失败原因。
- 20 个站点有配置，尚未逐站完成真实采集验收。请合理控制访问频率并遵守站点规则。

## 项目协作

- **作者与项目主导：[mileslynn03](https://github.com/mileslynn03)** — 提出需求、确定产品方向、进行真实场景测试与验收。
- **AI 开发协作：OpenAI Codex** — 协助代码实现、界面设计、问题排查、测试、文档和启动脚本编写。

## 开发与验证

手动安装、源码说明及测试命令见[开发说明](docs/DEVELOPMENT.md)。Windows / macOS 一键环境准备与回归测试在 [GitHub Actions](https://github.com/mileslynn03/amazon-product-toolkit/actions) 中运行，具体结果以对应提交的检查为准。
