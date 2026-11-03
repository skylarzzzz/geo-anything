#!/usr/bin/env python3
"""GEO Anything 监测脚本（零依赖，仅用 Python 标准库，Python 3.9+）

用各家 AI 的 API 批量跑问题池，自动判断：答案里有没有提到你、描述准不准、有没有给出你的链接，
按平台分别记分，并可与上一次结果对比。

重要说明：
- API 的回答不等于 App 里的回答。App 往往会联网搜索、带个性化，API 默认多半不联网。
  表中「模式」一列会注明：联网（会检索网页）或 模型记忆（只反映模型训练时学到的认知）。
- 两种都有价值：模型记忆说明 AI「本来就认识你」，联网说明 AI「搜得到你」。
- 想测 App 里的真实表现，仍建议按 references/monitoring.md 手动抽查。

用法：
  python3 geo_monitor.py --questions questions.txt --names "motion-atlas,Motion Atlas" \\
      --links "github.com/skylarzzzz/motion-atlas" --keywords "动效,skill,Claude" \\
      --platforms deepseek,qwen,perplexity --repeat 2 --out-dir geo-monitor

  python3 geo_monitor.py ... --compare geo-monitor/2026-11-04.json     # 与上一次对比
  python3 geo_monitor.py ... --dry-run                                  # 只看计划，不调用 API

问题文件：每行一个问题；# 开头为注释；可写成「意图|问题」，意图为 认知/对比/操作/品牌。

平台（--platforms，逗号分隔；--platforms all 表示所有已配置 Key 的平台；--list 查看完整列表）：
  国内：deepseek qwen doubao kimi hunyuan zhipu wenxin minimax stepfun baichuan spark
  海外：openai gemini claude grok perplexity mistral
每个平台需要对应的 API Key 环境变量（运行 --list 查看）。

模型名会随时间变化，脚本里的默认值可能已过时，可用 GEO_MODEL_<平台大写> 覆盖，例如 GEO_MODEL_GEMINI=gemini-2.5-pro。
接口地址可用 GEO_BASE_URL_<平台大写> 覆盖（走代理或测试）。
联网开关：支持联网的平台默认开启，可用 GEO_SEARCH_<平台大写>=0 关闭，测「模型记忆」。

没有公开 API 的 App 内置 AI（小红书点点/问一问、抖音@豆包、微信搜一搜、百度 AI 搜索、夸克、
知乎直答、Copilot、Google AI Overviews 等）请按 references/platforms.md 的手动监测清单抽查。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

def _p(display, base, key, model, group, api="openai", search=None):
    """search：开启联网时附加到请求体的参数；None 表示该平台 API 不支持联网（只测模型记忆）。"""
    return {"display": display, "base": base, "key_env": key, "model": model, "group": group,
            "api": api, "search": search}


PROVIDERS = {
    # ---- 国内
    "deepseek": _p("DeepSeek", "https://api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-chat", "国内"),
    "qwen":     _p("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY",
                   "qwen-plus", "国内", search={"enable_search": True}),
    "doubao":   _p("豆包", "https://ark.cn-beijing.volces.com/api/v3", "ARK_API_KEY", "", "国内"),
    "kimi":     _p("Kimi", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY", "moonshot-v1-8k", "国内"),
    "hunyuan":  _p("腾讯混元(元宝)", "https://api.hunyuan.cloud.tencent.com/v1", "HUNYUAN_API_KEY",
                   "hunyuan-turbos-latest", "国内", search={"enable_enhancement": True}),
    "zhipu":    _p("智谱清言(GLM)", "https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY", "glm-4-plus", "国内",
                   search={"tools": [{"type": "web_search", "web_search": {"enable": True}}]}),
    "wenxin":   _p("文心(百度)", "https://qianfan.baidubce.com/v2", "QIANFAN_API_KEY", "ernie-4.5-turbo-128k", "国内",
                   search={"web_search": {"enable": True}}),
    "minimax":  _p("MiniMax(海螺)", "https://api.minimaxi.com/v1", "MINIMAX_API_KEY", "MiniMax-M1", "国内"),
    "stepfun":  _p("阶跃星辰(跃问)", "https://api.stepfun.com/v1", "STEPFUN_API_KEY", "step-2-16k", "国内"),
    "baichuan": _p("百川", "https://api.baichuan-ai.com/v1", "BAICHUAN_API_KEY", "Baichuan4", "国内"),
    "spark":    _p("讯飞星火", "https://spark-api-open.xf-yun.com/v1", "SPARK_API_KEY", "4.0Ultra", "国内"),
    # ---- 海外
    "openai":     _p("ChatGPT(API)", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini", "海外"),
    "gemini":     _p("Gemini", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY",
                     "gemini-2.5-flash", "海外", api="gemini", search={"google_search": {}}),
    "claude":     _p("Claude", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "claude-sonnet-5-5", "海外",
                     api="anthropic", search={"type": "web_search_20250305", "name": "web_search", "max_uses": 3}),
    "grok":       _p("Grok", "https://api.x.ai/v1", "XAI_API_KEY", "grok-4", "海外"),
    "perplexity": _p("Perplexity", "https://api.perplexity.ai", "PERPLEXITY_API_KEY", "sonar", "海外", search={}),
    "mistral":    _p("Mistral(Le Chat)", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-large-latest", "海外"),
}
DISPLAY = {k: v["display"] for k, v in PROVIDERS.items()}
SYSTEM = "请像回答普通用户一样直接回答问题；如果推荐具体的工具、项目或品牌，请写出名称和链接。"
URL_RE = re.compile(r"https?://[^\s)\]>\"'，。]+")


def provider_conf(name: str) -> dict:
    p = PROVIDERS[name]
    up = name.upper()
    model = os.environ.get(f"GEO_MODEL_{up}") or (os.environ.get("ARK_MODEL") if name == "doubao" else "") or p["model"]
    search_on = p["search"] is not None and os.environ.get(f"GEO_SEARCH_{up}", "1") != "0"
    return {"name": name, "base": os.environ.get(f"GEO_BASE_URL_{up}", p["base"]).rstrip("/"),
            "key": os.environ.get(p["key_env"], ""), "key_env": p["key_env"], "model": model, "api": p["api"],
            "search": p["search"] if search_on else None, "mode": "联网" if search_on else "模型记忆"}


def _post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def complete(conf: dict, user: str, system: str = "", temperature: float = 0.3,
             use_search: bool = True, timeout: int = 120) -> tuple:
    """统一调用各家接口，返回 (回答文本, 引用链接列表)。"""
    search = conf["search"] if use_search else None
    if conf["api"] == "anthropic":
        body = {"model": conf["model"], "max_tokens": 2048, "temperature": temperature,
                "messages": [{"role": "user", "content": user}]}
        if system:
            body["system"] = system
        if search:
            body["tools"] = [search]
        data = _post(conf["base"] + "/messages", body,
                     {"x-api-key": conf["key"], "anthropic-version": "2023-06-01"}, timeout)
        texts, cites = [], []
        for b in data.get("content") or []:
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
                cites += [c.get("url", "") for c in b.get("citations") or [] if isinstance(c, dict)]
        return "".join(texts), [c for c in cites if c]
    if conf["api"] == "gemini":
        body = {"contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if search:
            body["tools"] = [search]
        url = f"{conf['base']}/models/{conf['model']}:generateContent"
        data = _post(url, body, {"x-goog-api-key": conf["key"]}, timeout)
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or [])
        cites = []
        for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks") or []:
            web = ch.get("web") or {}
            cites += [web.get("uri", ""), web.get("title", "")]   # uri 可能是跳转链接，title 通常是域名
        return text, [c for c in cites if c]
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    body = {"model": conf["model"], "temperature": temperature, "messages": msgs, **(search or {})}
    data = _post(conf["base"] + "/chat/completions", body, {"Authorization": f"Bearer {conf['key']}"}, timeout)
    msg = (data.get("choices") or [{}])[0].get("message", {})
    cites = list(data.get("citations") or [])
    cites += [s.get("url", "") for s in data.get("search_results") or [] if isinstance(s, dict)]
    for w in data.get("web_search") or []:                       # 智谱
        if isinstance(w, dict):
            cites.append(w.get("link", ""))
    for w in (data.get("search_info") or {}).get("search_results") or []:   # 千问 / 文心
        if isinstance(w, dict):
            cites.append(w.get("url", ""))
    return msg.get("content") or "", [c for c in cites if isinstance(c, str) and c]


def ask(conf: dict, question: str, timeout: int = 120) -> dict:
    last = ""
    for attempt in range(3):
        try:
            answer, cites = complete(conf, question, SYSTEM, 0.3, True, timeout)
            return {"ok": True, "answer": answer, "citations": cites}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
            if e.code not in (429, 500, 502, 503, 504, 529):
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            last = str(e)
        time.sleep(2 * (attempt + 1))
    return {"ok": False, "answer": "", "citations": [], "error": last}


def judge(answer: str, citations: list, names: list, links: list, keywords: list) -> dict:
    low = answer.lower()
    mention = any(n.lower() in low for n in names)
    hay = low + " " + " ".join(citations).lower() + " " + " ".join(URL_RE.findall(answer)).lower()
    link = any(l.lower() in hay for l in links) if links else False
    if not mention:
        accurate = False
    elif keywords:
        hits = sum(1 for k in keywords if k.lower() in low)
        accurate = hits >= max(1, (len(keywords) + 1) // 2)
    else:
        accurate = None                                # 未提供关键词：需人工判断
    s = int(mention) + int(bool(accurate)) + int(link)
    return {"mention": mention, "accurate": accurate, "link": link, "score": s}


def load_questions(path: str) -> list:
    qs = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            intent, q = (x.strip() for x in line.split("|", 1))
        else:
            intent, q = "", line
        qs.append({"intent": intent, "question": q})
    return qs


def split(s: str) -> list:
    return [x.strip() for x in re.split(r"[,，]", s or "") if x.strip()]


def render_md(run: dict, prev: dict | None) -> str:
    L = [f"# GEO 监测记录：{'、'.join(run['names'][:2])} · {run['date']}", "",
         "| # | 问题 | 意图 | 平台 | 模式 | 提及 | 准确 | 链接 | 得分 |", "|---|---|---|---|---|---|---|---|---|"]
    mark = lambda v: "待人工" if v is None else ("✓" if v else "✗")
    for i, r in enumerate(run["results"], 1):
        if not r["ok"]:
            L.append(f"| {i} | {r['question']} | {r['intent']} | {DISPLAY[r['platform']]} | {r['mode']} | 调用失败 | | | |")
            continue
        j = r["judge"]
        L.append(f"| {i} | {r['question']} | {r['intent']} | {DISPLAY[r['platform']]} | {r['mode']} | "
                 f"{mark(j['mention'])} | {mark(j['accurate'])} | {mark(j['link'])} | {j['score']}/3 |")
    L += ["", "## 平台汇总", "", "| 平台 | 模式 | 有效问题 | 提及率 | 可见度 | 较上次 |", "|---|---|---|---|---|---|"]
    prev_sum = (prev or {}).get("summary", {})
    for p, s in run["summary"].items():
        delta = ""
        if p in prev_sum:
            d = s["visibility"] - prev_sum[p]["visibility"]
            delta = f"{d:+.0f} 个百分点"
        L.append(f"| {DISPLAY[p]} | {s['mode']} | {s['n']} | {s['mention_rate']:.0f}% | {s['visibility']:.0f}% | {delta or '—'} |")
    if prev:
        L += ["", "## 与上次相比的变化", ""]
        old = {(r["platform"], r["question"]): r for r in prev.get("results", []) if r.get("ok")}
        changes = []
        for r in run["results"]:
            o = old.get((r["platform"], r["question"]))
            if r["ok"] and o and o["judge"]["mention"] != r["judge"]["mention"]:
                changes.append(f"- {DISPLAY[r['platform']]}｜{r['question']}：" +
                               ("新增提及" if r["judge"]["mention"] else "不再提及"))
        L += changes or ["- 提及情况没有变化"]
    L += ["", "> 可见度 = 总得分 ÷（有效问题数 × 3）。重复提问时取最低分（保守口径）。",
          "> 「模型记忆」模式只反映模型训练时的认知，与 App 联网回答可能不同。"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 监测脚本")
    ap.add_argument("--list", action="store_true", help="列出全部支持的平台与所需的 Key")
    ap.add_argument("--questions", help="问题文件")
    ap.add_argument("--names", help="对象名称及别称，逗号分隔")
    ap.add_argument("--links", default="", help="你的域名或链接片段，逗号分隔")
    ap.add_argument("--keywords", default="", help="一句话定义里的关键词，用于判断描述是否准确")
    ap.add_argument("--platforms", default="all", help="平台，逗号分隔；all 表示所有已配置 Key 的平台")
    ap.add_argument("--repeat", type=int, default=2, help="每题重复次数，取最低分（默认 2）")
    ap.add_argument("--out-dir", default="geo-monitor", help="输出目录")
    ap.add_argument("--compare", help="上一次结果的 JSON 文件")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    a = ap.parse_args(argv)

    if a.list:
        print("| 平台 | 代号 | 地区 | 默认模型 | 联网 | 需要的环境变量 | 已配置 |\n|---|---|---|---|---|---|---|")
        for k, p in PROVIDERS.items():
            key = p["key_env"] + (" + ARK_MODEL" if k == "doubao" else "")
            print(f"| {p['display']} | {k} | {p['group']} | {p['model'] or '（需自填）'} | "
                  f"{'支持' if p['search'] is not None else '—'} | {key} | {'✓' if os.environ.get(p['key_env']) else ''} |")
        return 0
    if not a.questions or not a.names:
        ap.error("需要 --questions 和 --names（或用 --list 查看平台）")
    if a.platforms.strip().lower() == "all":
        a.platforms = ",".join(k for k, p in PROVIDERS.items() if os.environ.get(p["key_env"]))
        if not a.platforms:
            print("还没有配置任何平台的 API Key，运行 --list 查看需要哪些环境变量。", file=sys.stderr)
            return 2

    qs = load_questions(a.questions)
    names, links, kws = split(a.names), split(a.links), split(a.keywords)
    plats = [p for p in split(a.platforms) if p in PROVIDERS]
    unknown = [p for p in split(a.platforms) if p not in PROVIDERS]
    if unknown:
        print(f"忽略未知平台：{', '.join(unknown)}", file=sys.stderr)
    confs = []
    for p in plats:
        c = provider_conf(p)
        if not c["key"]:
            print(f"跳过 {DISPLAY[p]}：未设置 {c['key_env']}", file=sys.stderr)
        elif not c["model"]:
            print(f"跳过 {DISPLAY[p]}：未设置模型（豆包需要 ARK_MODEL，填推理接入点 ID）", file=sys.stderr)
        else:
            confs.append(c)
    calls = len(qs) * len(confs) * a.repeat
    print(f"问题 {len(qs)} 个 × 平台 {len(confs)} 个 × 重复 {a.repeat} 次 = {calls} 次调用", file=sys.stderr)
    if a.dry_run or not confs or not qs:
        for c in confs:
            print(f"  {DISPLAY[c['name']]}：{c['model']}（{c['mode']}）", file=sys.stderr)
        return 0 if (a.dry_run or (confs and qs)) else 2

    results = []
    for q in qs:
        for c in confs:
            best = None
            for _ in range(max(1, a.repeat)):
                r = ask(c, q["question"])
                if r["ok"]:
                    r["judge"] = judge(r["answer"], r["citations"], names, links, kws)
                if best is None or (r["ok"] and (not best["ok"] or r["judge"]["score"] < best["judge"]["score"])):
                    best = r
            best.update({"platform": c["name"], "mode": c["mode"], "model": c["model"], **q})
            results.append(best)
            print(f"  {DISPLAY[c['name']]}｜{q['question'][:30]}："
                  + (f"{best['judge']['score']}/3" if best["ok"] else f"失败 {best.get('error', '')[:60]}"),
                  file=sys.stderr)

    summary = {}
    for c in confs:
        rs = [r for r in results if r["platform"] == c["name"] and r["ok"]]
        n = len(rs)
        summary[c["name"]] = {
            "mode": c["mode"], "n": n,
            "mention_rate": (sum(r["judge"]["mention"] for r in rs) / n * 100) if n else 0,
            "visibility": (sum(r["judge"]["score"] for r in rs) / (n * 3) * 100) if n else 0,
        }
    run = {"date": date.today().isoformat(), "names": names, "links": links, "keywords": kws,
           "summary": summary, "results": results}
    prev = json.load(open(a.compare, encoding="utf-8")) if a.compare else None

    os.makedirs(a.out_dir, exist_ok=True)
    jp = os.path.join(a.out_dir, f"{run['date']}.json")
    mp = os.path.join(a.out_dir, f"{run['date']}.md")
    json.dump(run, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(mp, "w", encoding="utf-8").write(render_md(run, prev))
    print(f"已写入 {mp} 和 {jp}", file=sys.stderr)
    for p, s in summary.items():
        print(f"{DISPLAY[p]}（{s['mode']}）：提及率 {s['mention_rate']:.0f}%，可见度 {s['visibility']:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
