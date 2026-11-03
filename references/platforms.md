# AI 平台与来源偏好（经验参考，使用前请联网核实最新情况）

> 各平台的检索与引用策略变化很快。下表是行业经验汇总，不是官方规则。给结论前先搜索最新信息。

## 国内

| 平台 | 常见引用来源生态（经验） | 优化侧重 |
|---|---|---|
| 豆包 | 抖音、今日头条、西瓜等字节系内容，以及公开网页 | 抖音/头条内容的标题与文字描述、账号简介 |
| DeepSeek（联网） | 公开网页、知乎、CSDN、技术博客、百科类 | 结构清晰的长文、技术文档、GitHub |
| 腾讯元宝 | 微信公众号、视频号及公开网页 | 公众号文章、视频号描述 |
| Kimi | 公开网页、长文、文档 | 深度长文、PDF/白皮书 |
| 通义千问 / 文心 | 公开网页、百科、行业站点 | 百科词条、行业媒体、官网 |

## 海外

| 平台 | 常见引用来源生态（经验） | 优化侧重 |
|---|---|---|
| ChatGPT Search | 公开网页、Wikipedia、评测站、Reddit 等 | 权威第三方提及、清晰定义页 |
| Perplexity | 实时网页，偏好新鲜、来源透明、有原始数据的页面 | 更新频率、作者/日期、数据 |
| Google AI Overviews / Gemini | Google 索引页面 | 传统 SEO 基础 + 问答结构 |
| Claude（联网） | 公开网页 | 清晰结构、可核验事实 |

## 按对象类型选平台

| 类型 | 核心平台 | 扩展平台 |
|---|---|---|
| 国内消费 / 内容 / 个人品牌 | 豆包、DeepSeek | 元宝、Kimi、千问 |
| 开发者 / 开源 | DeepSeek、ChatGPT | Perplexity、Kimi |
| 出海 | ChatGPT、Perplexity、Google AIO | Gemini、Claude |
| B2B 工业 | DeepSeek、文心 | 豆包、Kimi |

## AI 爬虫名单（robots.txt 常见）

- 搜索/实时抓取类：OAI-SearchBot、ChatGPT-User、PerplexityBot、Perplexity-User、Claude-SearchBot、Claude-User
- 训练类：GPTBot、ClaudeBot、Google-Extended、CCBot、Applebot-Extended、Bytespider
- 想被 AI 搜索引用，至少不要挡搜索类爬虫；是否允许训练类由使用者自行决定。
