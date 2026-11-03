# 致谢与参考


本项目的代码和文档均为原创编写，没有复制以下项目的代码。下面列出的是方法和思路上的参考，在此致谢。

**论文**
- [GEO: Generative Engine Optimization](https://github.com/GEO-optim/GEO)（Aggarwal et al.）：可见度指标与改写策略，`geo_simulate.py` 的评估方法参考了它
- [AutoGEO](https://github.com/cxcscmu/AutoGEO)（CMU）：自动学习生成式引擎偏好并改写内容的思路

**开源项目**
- [geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude)：多维度加权评分、并行子 agent、客户管理与报告模块的整体结构
- [ultimate-seo-geo](https://github.com/mykpono/ultimate-seo-geo)：审计 → 计划 → 执行的流程，按用途区分 AI 爬虫
- [SEO-GEO-AEO-Skill](https://github.com/SNLabat/SEO-GEO-AEO-Skill)：AEO 问答结构检查
- [claude-skill-seo-geo-optimizer](https://github.com/199-biotechnologies/claude-skill-seo-geo-optimizer)：对结构化数据作用的审慎结论
- [OranGEO AI Visibility Skill](https://github.com/PixelOrange7/orangeo-ai-visibility-skill)：「用户会怎么问 AI」的问题池思路
- [geo-optimizer-skill](https://pypi.org/project/geo-optimizer-skill/)：CI/CD 集成与 API 监测的思路

**小红书与国内平台资料**
- [你的笔记被AI引用了吗？小红书问一问+点点GEO优化全攻略](https://www.aiyingli.com/294682.html)
- [小红书GEO优化实战手册](https://m.sohu.com/a/991070573_211762)
- [小红书押注AI搜索，笔记内容成为「点点」卖点（钛媒体）](https://www.tmtpost.com/7411865.html)
- [能监测DeepSeek、豆包品牌提及率的 GEO 软件有哪些（IT之家）](https://www.ithome.com/1/011/106.htm)：分平台监测、不看平均值的依据

**与参考项目的主要不同**：中文 AI 平台与 App 内置 AI（小红书、抖音、微信等）优先；能优化的对象不限于网站；脚本零依赖、手机对话也能用；明确排除刷量、自问自答等操纵手段。
