# GEO Anything · 让 AI 看见你的任何东西

**GEO Anything 是一个给创作者、个人和中小企业用的开源 AI skill，用来让你的网站、账号内容、商品、GitHub 项目或品牌被豆包、DeepSeek、元宝、Kimi、ChatGPT、Perplexity 等 AI 读懂、引用和推荐。**

**EN:** GEO Anything is an open-source AI skill that audits, rewrites and monitors anything you own — websites, social posts, products, GitHub repos, personal or company brands — so AI answer engines can understand, cite and recommend it. Chinese AI platforms first, global platforms supported.

## 它能做什么？

| 命令 | 作用 |
|---|---|
| `/geo 档案` | 建立你的 GEO 档案（名称、定义、目标用户、竞品） |
| `/geo 速查 <链接>` | 60 秒快检 |
| `/geo 体检 <链接>` | 六维度 0–100 分审计 + 快赢清单 |
| `/geo 问题池` | 生成用户真实会问 AI 的问题 |
| `/geo 改写` | 把内容改成 AI 爱引用的结构 |
| `/geo 文件` | 生成 llms.txt、JSON-LD、FAQ、robots.txt、README |
| `/geo 实体` | 统一个人/品牌在所有平台的介绍 |
| `/geo 布点` | 规划在哪些 AI 常引用的来源被提及 |
| `/geo 监测` / `/geo 复盘` | 分平台记录可见度并对比变化 |
| `/geo 报告` | 生成可交付给老板/客户的报告 |

覆盖 8 类场景：网站工具、GitHub 开源、社媒内容、个人品牌、电商出海、本地商家、B2B 制造业、知识课程。

## 怎么用？

**Claude（网页/App）**：把整个 `geo-anything` 文件夹打包为 zip，在设置的 Skills 中上传；或在对话里直接附上 SKILL.md 说「按这个 skill 帮我做 GEO」。

**Claude Code / Codex**：
```bash
git clone https://github.com/<你的用户名>/geo-anything.git
cp -r geo-anything ~/.claude/skills/
```

**其他 AI（豆包、DeepSeek、ChatGPT 等）**：把 SKILL.md 内容粘贴进对话作为指令即可，体检需要该 AI 开启联网。

然后说：「`/geo 档案`，我要优化的是 <链接>」。

## 和同类项目有什么区别？

| | GEO Anything | 常见海外 GEO skill |
|---|---|---|
| 平台 | 中文 AI 优先，兼顾海外 | 主要针对 ChatGPT / Google |
| 对象 | 网站、社媒、商品、仓库、个人、企业 | 主要是网站 |
| 运行环境 | 手机对话即可，无需终端 | 多数需要命令行和 Python |
| 监测 | 分平台记分，避免平均值掩盖下降 | 多为单次审计 |

## 底线

不编造数据和评价、不刷帖、不藏隐藏指令、不承诺「保证被 AI 推荐」。GEO 提高的是概率。

## 致谢

方法参考了 GEO 论文（Aggarwal et al.）与 geo-seo-claude、ultimate-seo-geo、SEO-GEO-AEO-Skill、OranGEO 等开源项目。

## 作者

Yun · [GitHub @skylarzzzz](https://github.com/skylarzzzz)

License: MIT
