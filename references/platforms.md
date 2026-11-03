# AI 平台清单与来源偏好（2026 年 11 月整理，使用前请联网核实）

> 各平台的检索与引用策略变化很快。来源偏好一栏是行业经验汇总，不是官方规则；给具体结论前先搜索最新信息。
> 「监测方式」：**API** = 可用 `geo_monitor.py` 自动测；**手动** = 没有公开 API，按本文第三节清单在 App 里抽查。

## 一、用户规模参考

- 国内 AI 原生 App 月活（QuestMobile，2026 年 6 月）：豆包约 3.82 亿，千问约 1.67 亿，DeepSeek 约 1.30 亿，元宝约 0.50 亿，蚂蚁阿福约 0.29 亿，Kimi 约 0.07 亿。不含手机厂商预装助手。
- 全球网页端访问份额（Similarweb，2026 年 6 月，7 个助手之间）：ChatGPT 53.8%，Gemini 28.6%，Claude 9.5%，DeepSeek 3.7%，Grok 2.1%，Perplexity 1.2%，Copilot 1.2%。只统计网页访问，不含 App 和 API。
- 另有大量用户在**超级 App 内嵌的 AI** 里提问（小红书、抖音、微信、淘宝、支付宝、百度、夸克、知乎），这部分没有统一统计，但对国内 GEO 非常重要。

## 二、独立 AI 助手（20+）

| # | 平台 | 地区 | 监测方式 | 常见引用来源生态（经验） | 优化侧重 |
|---|---|---|---|---|---|
| 1 | 豆包 | 国内 | API（模型记忆）+ 手动（App 联网） | 抖音、今日头条、西瓜等字节系内容，以及公开网页 | 抖音视频标题、口播、字幕、描述文字；头条文章 |
| 2 | 通义千问 | 国内 | API（联网） | 公开网页、阿里系内容；小红书「问一问」也接入千问 | 结构清晰的网页与问答；小红书笔记 |
| 3 | DeepSeek | 国内 | API（模型记忆）+ 手动（App 联网） | 公开网页、知乎、CSDN、技术博客、百科 | 长文、技术文档、GitHub |
| 4 | 腾讯元宝 | 国内 | API（混元，联网）+ 手动 | 微信公众号、视频号、腾讯系内容及公开网页 | 公众号文章、视频号描述 |
| 5 | Kimi | 国内 | API（模型记忆）+ 手动 | 公开网页、长文、PDF | 深度长文、白皮书 |
| 6 | 文心一言 / 文小言 | 国内 | API（联网） | 百度搜索索引、百度百科、百家号、知道 | 百度百科词条、百家号、官网 SEO |
| 7 | 智谱清言 | 国内 | API（联网） | 公开网页 | 结构化网页、权威来源 |
| 8 | MiniMax 海螺 | 国内 | API（模型记忆） | 公开网页 | 通用 |
| 9 | 阶跃星辰 跃问 | 国内 | API（模型记忆） | 公开网页 | 通用 |
| 10 | 百川 | 国内 | API（模型记忆） | 公开网页、医疗健康内容 | 专业内容 |
| 11 | 讯飞星火 | 国内 | API（模型记忆） | 公开网页、教育内容 | 教育类内容 |
| 12 | 蚂蚁阿福 | 国内 | 手动 | 金融、医疗健康相关专业内容（经验） | 仅金融、健康类对象需要关注 |
| 13 | 秘塔 AI 搜索 | 国内 | 手动 | 公开网页、学术文献 | 学术与专业内容 |
| 14 | ChatGPT | 海外 | API（模型记忆）+ 手动（App 联网） | 公开网页、Wikipedia、评测站、Reddit | 权威第三方提及、清晰定义页 |
| 15 | Gemini | 海外 | API（Google 搜索联网） | Google 索引 | 传统 SEO 基础 + 问答结构 |
| 16 | Google AI Overviews / AI Mode | 海外 | 手动 | Google 索引 | 同上，传统排名仍是前提 |
| 17 | Claude | 海外 | API（联网） | 公开网页（有研究认为与 Brave 搜索结果相关性较高） | 清晰结构、可核验事实 |
| 18 | Grok | 海外 | API（模型记忆）+ 手动 | X（推特）帖子与公开网页 | X 上的真实讨论 |
| 19 | Perplexity | 海外 | API（联网） | 实时网页，偏好新鲜、来源透明、有原始数据的页面 | 更新频率、作者与日期、数据 |
| 20 | Microsoft Copilot | 海外 | 手动 | 必应索引 | 必应站长工具、传统 SEO |
| 21 | Meta AI | 海外 | 手动 | 公开网页、Meta 系内容 | Instagram、Facebook 内容 |
| 22 | Mistral Le Chat | 海外 | API（模型记忆） | 公开网页 | 欧洲市场 |

## 三、超级 App 内嵌的 AI（国内 GEO 重点）

| 入口 | 所在 App | 监测方式 | 主要来源 | 优化手册 |
|---|---|---|---|---|
| 「问一问」 | 小红书（搜索结果页右上角） | 手动 | 小红书笔记，答案会署名引用的笔记作者；据报道接入千问 | references/xiaohongshu.md |
| 点点 / 问点点 | 小红书（站内入口，另有独立 App、小程序和 PC 端） | 手动 | 小红书笔记为主，也会引用其他平台 | references/xiaohongshu.md |
| @豆包 / 搜索 AI 回答 | 抖音 | 手动 | 抖音视频（标题、口播、字幕、评论） | references/embedded-ai.md |
| 搜一搜 AI / 元宝 | 微信 | 手动 | 公众号文章、视频号、小程序 | references/embedded-ai.md |
| AI 搜索 / 文小言 | 百度 App | 手动 | 百度索引、百科、百家号 | references/embedded-ai.md |
| 夸克 AI 搜索 | 夸克 | 手动 | 公开网页、阿里系内容 | references/embedded-ai.md |
| 知乎直答 | 知乎 | 手动 | 知乎回答与文章 | references/embedded-ai.md |
| 淘宝问问 / 购物助手 | 淘宝 | 手动 | 商品详情、评价、问大家 | references/embedded-ai.md |
| 蚂蚁阿福 | 支付宝 | 手动 | 金融、医疗健康内容 | references/embedded-ai.md |
| WorkBuddy | 腾讯办公 Agent（桌面工作台） | 手动 | 主要处理用户自己的文件和任务；做调研时依赖公开网页 | references/embedded-ai.md |

## 四、按对象类型选平台

| 类型 | 核心平台 | 扩展平台 |
|---|---|---|
| 国内消费 / 生活方式 / 个人品牌 | 小红书问一问与点点、豆包（抖音）、千问 | 元宝（微信）、DeepSeek、百度 |
| 国内知识 / 内容 IP | 豆包、DeepSeek、知乎直答 | 元宝、Kimi、小红书 |
| 开发者 / 开源 | DeepSeek、ChatGPT、Claude | Perplexity、Kimi、Gemini |
| 电商（国内） | 淘宝问问、小红书、豆包 | 千问、元宝 |
| 出海 | ChatGPT、Google AI Overviews、Gemini、Perplexity | Claude、Grok、Copilot、Meta AI |
| B2B 工业 | DeepSeek、文心、豆包、元宝（公众号） | Kimi、智谱、WorkBuddy 等办公 Agent |
| 本地商家 | 小红书、抖音、百度（地图）、元宝 | 高德、大众点评自带的 AI 推荐 |

## 五、AI 爬虫名单（robots.txt 常见）

- 搜索/实时抓取类：OAI-SearchBot、ChatGPT-User、PerplexityBot、Perplexity-User、Claude-SearchBot、Claude-User
- 训练类：GPTBot、ClaudeBot、Google-Extended、CCBot、Applebot-Extended、Bytespider、Meta-ExternalAgent
- 国内搜索引擎：Baiduspider、Sogou web spider、360Spider、YisouSpider（神马）
- 想被 AI 搜索引用，至少不要挡搜索类爬虫；是否允许训练类由使用者自行决定。

## 六、手动监测清单（没有 API 的平台）

1. 每个入口用**同一批问题**（问题池里不带品牌名的那部分），新开对话，关闭个性化或登出账号（能关的话）。
2. 记录：是否提及、描述是否准确、引用了哪篇来源（小红书看署名作者，抖音看引用的视频）、截图。
3. 同一问题问 2 次，取较差的一次。
4. 填进 `templates/monitor-sheet.md`，「平台」一栏写入口名（如「小红书·问一问」）。
5. 用 `geo_clients.py monitor` 或 `geo_monitor.py --compare` 的格式保存，以便月度对比。
