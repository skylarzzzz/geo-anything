# GEO Anything · 让 AI 看见你的任何东西

**GEO Anything 是一个给创作者、个人和中小企业用的开源 AI skill，用来让你的网站、账号内容、商品、GitHub 项目或品牌被豆包、DeepSeek、元宝、Kimi、ChatGPT、Perplexity 等 AI 读懂、引用和推荐。**

**EN:** GEO Anything is an open-source AI skill and zero-dependency toolkit that audits, rewrites, simulates and monitors anything you own — websites, social posts, products, GitHub repos, personal or company brands — so AI answer engines can understand, cite and recommend it. Chinese AI platforms first, global platforms supported.

作者：Yun ｜ 更新：2026-11-04 ｜ 协议：MIT

## 它能做什么？

| 命令 | 作用 |
|---|---|
| `/geo 档案` | 建立 GEO 档案（名称、定义、目标用户、竞品） |
| `/geo 速查 <链接>` | 60 秒快检 |
| `/geo 体检 <链接>` | 六维度 0–100 分审计 + 快赢清单（可并行 5 个子 agent） |
| `/geo 性能 <网址>` | Core Web Vitals（LCP / CLS / INP）与加载速度 |
| `/geo 问题池` | 生成用户真实会问 AI 的问题 |
| `/geo 搜索数据` | 从 Search Console / 百度搜索资源平台导出的数据中挖 GEO 机会 |
| `/geo 改写` | 把内容改成 AI 爱引用的结构 |
| `/geo 模拟` | 上线前预演：原文和改写稿谁更容易被 AI 引用 |
| `/geo 文件` | 生成 llms.txt、JSON-LD、FAQ、robots.txt、README |
| `/geo 实体` | 统一个人/品牌在所有平台的介绍 |
| `/geo 布点` | 规划在哪些 AI 常引用的来源被提及 |
| `/geo 监测` / `/geo 复盘` | 用 API 分平台记录可见度，自动对比变化 |
| `/geo 报告` | HTML / PDF 图表报告，可白标交付给客户 |
| `/geo 客户` | 线索管线、自动提案、月度报告（给接 GEO 单的人） |

覆盖 8 类场景：网站工具、GitHub 开源、社媒内容、个人品牌、电商出海、本地商家、B2B 制造业、知识课程。

## 30 秒上手

**只有手机 / 只用对话**：把 `SKILL.md` 发给 Claude、豆包、DeepSeek 或 ChatGPT，说「按这个 skill，`/geo 档案`，我要优化的是 <链接>」。体检需要该 AI 开启联网。

**Claude（网页 / App）**：把 `geo-anything` 文件夹打包成 zip，在设置的 Skills 里上传。

**Claude Code / Codex**：
```bash
git clone https://github.com/skylarzzzz/geo-anything.git
cp -r geo-anything ~/.claude/skills/geo-anything
cp geo-anything/agents/*.md ~/.claude/agents/      # 可选：启用并行子 agent
```

**直接用脚本**（Python 3.9+，无需安装任何依赖）：
```bash
python3 scripts/geo_check.py https://你的网站 --psi              # 体检 + Core Web Vitals
python3 scripts/geo_check.py https://github.com/你/你的项目        # 体检 GitHub 仓库
python3 scripts/geo_check.py https://你的网站 --json > audit.json
python3 scripts/geo_report.py --audit audit.json --out report.html # 图表报告
```

## 工具箱

| 脚本 | 作用 | 需要 |
|---|---|---|
| `geo_check.py` | 可复现的体检：可引用性、实体与 E-E-A-T、技术可读性、结构化数据、性能；`--min-score` 用于 CI | 无 |
| `geo_monitor.py` | 用 API 跑问题池：DeepSeek、Kimi、通义千问（联网）、豆包、Perplexity（联网）、OpenAI；分平台记分、对比上次 | 对应平台的 API Key |
| `geo_simulate.py` | 模拟生成式引擎（参考 GEO 论文的可见度指标），比较原文与改写稿；`--rewrite` 自动改写且不编造事实 | 一个平台的 API Key |
| `geo_report.py` | 自包含 HTML 报告（仪表盘、柱状图，支持深色模式），可选 PDF；品牌名、颜色、logo 白标 | PDF 需 `pip install reportlab` |
| `geo_gsc.py` | 分析搜索平台导出的查询 CSV：问题型查询、高曝光低点击、潜力词，并生成问题池 | 无 |
| `geo_clients.py` | 客户管线、基于体检结果自动生成三档提案、月度对比报告 | 无 |

**GitHub Action**：在你自己的仓库里加一个工作流，每次改 README 自动体检：
```yaml
- uses: actions/checkout@v4
- uses: skylarzzzz/geo-anything@v1
  with:
    target: "."
    min-score: "60"
```
定时监测并把结果提交回仓库的完整示例见 `examples/workflows/geo-monitor.yml`。

## 和同类项目有什么区别？

| | GEO Anything | 常见海外 GEO skill |
|---|---|---|
| AI 平台 | 中文 AI 优先（豆包、DeepSeek、元宝、Kimi、千问），兼顾海外 | 主要针对 ChatGPT / Google |
| 能优化的对象 | 网站、社媒内容、商品、仓库、个人、企业、门店 | 主要是网站 |
| 运行环境 | 手机对话可用；脚本零依赖 | 多数需要命令行 + 安装 Python 依赖 |
| 监测 | API 自动监测中文平台，分平台记分，区分联网 / 模型记忆 | 多为单次审计，或只接海外 API |
| 上线前验证 | 本地模拟引用份额，比较改写前后 | 少见 |
| 搜索数据 | 支持 Search Console 和百度搜索资源平台导出 | 多为仅 Search Console |

## 真实案例

> 正在进行：以开源项目 motion-atlas 为对象，记录优化前后在各 AI 平台的可见度变化，结果会更新在这里。

## 底线

不编造数据和评价、不刷帖、不藏隐藏指令、不承诺「保证被 AI 推荐」。GEO 提高的是概率。
评分为启发式规则，用于稳定对比前后变化，不代表任何 AI 平台的官方算法。

## 致谢

方法参考了 GEO 论文（Aggarwal et al., *GEO: Generative Engine Optimization*）、AutoGEO，以及 geo-seo-claude、ultimate-seo-geo、SEO-GEO-AEO-Skill、OranGEO 等开源项目。

## 作者

Yun · [GitHub @skylarzzzz](https://github.com/skylarzzzz)
