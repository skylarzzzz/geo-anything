#!/usr/bin/env python3
"""GEO Anything 生成式引擎模拟器（AutoGEO / GEO-bench 思路的简化版，零依赖）

在改动真正上线、等 AI 平台重新收录之前，先在本地「预演」：
把你的内容和几篇竞品内容一起作为来源交给一个 LLM，让它像 AI 搜索一样带引用作答，
统计你的内容被引用了多少、引用出现得多靠前。原文和改写稿各测一遍，就能看出改写是否有效。

指标（参考 GEO 论文 Aggarwal et al. 的可见度定义）：
  - 引用率：答案中至少引用你一次的比例
  - 字数份额：引用你的句子字数 ÷ 全部答案字数（多个来源共同引用时平分）
  - 位置加权份额：越靠前的句子权重越高（权重 e^(-句序/句数)）

用法：
  # 对比原文与改写稿
  python3 geo_simulate.py --questions q.txt --mine original.md --variant rewritten.md \\
      --competitors comp1.md comp2.md comp3.md --platform deepseek

  # 让 LLM 按规则自动改写，然后自动对比
  python3 geo_simulate.py --questions q.txt --mine original.md --competitors comp*.md --rewrite rewritten.md

API Key 与 geo_monitor.py 相同（DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY …）。
注意：这是模拟，结论用于比较不同版本的相对好坏，不等于真实平台的表现。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_monitor import DISPLAY, PROVIDERS, load_questions, provider_conf  # noqa: E402

CJK = re.compile(r"[一-鿿]")
WORD = re.compile(r"[A-Za-z0-9]+")
CITE = re.compile(r"\[(\d+(?:\s*[,，、]\s*\d+)*)\]")

ENGINE_PROMPT = """你是一个 AI 搜索引擎。请只根据下面给出的来源回答用户问题。
要求：
1. 每一句话结尾用 [编号] 标注它依据的来源，可以同时标多个，例如 [1][3]。
2. 不要使用来源以外的信息；来源不相关时可以不引用它。
3. 用自然、简洁的段落回答，不超过 300 字。

{sources}

用户问题：{question}"""

REWRITE_PROMPT = """你是 GEO（生成式引擎优化）编辑。请改写下面的内容，让 AI 搜索更容易理解和引用它。
必须遵守：
- 第一句直接给出定义或结论：「<名称> 是一个给 <谁> 用的 <品类>，用来 <解决什么>。」
- 小标题改成用户会问的问题；每段开头复述主语，能被单独摘录也读得懂。
- 步骤用编号列表，对比用表格。
- 保留原文中所有真实的数字、名称、链接；绝对不能编造任何数据、评价、案例或来源。
  原文缺少数据的地方，写成【需补充：xxx】提示作者补真实信息。
- 保持原作者的语气，不加营销夸张词。
只输出改写后的正文（Markdown），不要解释。

原文：
{content}"""


def chat(conf: dict, prompt: str, temperature: float = 0.2, timeout: int = 120) -> str:
    body = {"model": conf["model"], "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}], **conf["extra"]}
    body.pop("enable_search", None)            # 模拟时不联网，只看给定来源
    req = urllib.request.Request(conf["base"] + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {conf['key']}"})
    last = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def wlen(s: str) -> int:
    return len(CJK.findall(s)) + len(WORD.findall(s))


SENT_RE = re.compile(r"[^。！？!?；;\n]+(?:[。！？!?；;]+)?(?:\s*\[\d+(?:\s*[,，、]\s*\d+)*\])*")


def sentences(answer: str) -> list:
    """分句，并把句末标点之后紧跟的 [n] 引用归到这一句（中文答案常见「……。[2]」）。"""
    out = []
    for m in SENT_RE.finditer(answer):
        t = m.group(0).strip()
        if not t:
            continue
        if re.fullmatch(r"(\s*\[\d+(?:\s*[,，、]\s*\d+)*\])+", t) and out:
            out[-1] += t
        else:
            out.append(t)
    return out


def visibility(answer: str, mine_idx: int) -> dict:
    sents = sentences(answer)
    n = len(sents) or 1
    total = sum(wlen(re.sub(CITE, "", s)) for s in sents) or 1
    share = adj = 0.0
    adj_total = 0.0
    cited = False
    for i, s in enumerate(sents):
        ids = set()
        for m in CITE.finditer(s):
            ids.update(int(x) for x in re.split(r"\s*[,，、]\s*", m.group(1)))
        w = wlen(re.sub(CITE, "", s))
        weight = math.exp(-i / n)
        adj_total += w * weight
        if mine_idx in ids:
            cited = True
            share += w / len(ids)
            adj += w * weight / len(ids)
    return {"cited": cited, "share": share / total, "adj": adj / (adj_total or 1)}


def simulate(conf, question: str, mine: str, comps: list, trials: int, seed: int) -> dict:
    rng = random.Random(seed)
    res = []
    for t in range(trials):
        docs = comps[:] + [None]
        rng.shuffle(docs)                       # 你的内容随机出现在不同位置，消除位置偏差
        mine_idx = docs.index(None) + 1
        src = "\n\n".join(f"[{i}] {mine if d is None else d}" for i, d in enumerate(docs, 1))
        ans = chat(conf, ENGINE_PROMPT.format(sources=src, question=question))
        res.append(visibility(ans, mine_idx))
    k = len(res) or 1
    return {"cited": sum(r["cited"] for r in res) / k, "share": sum(r["share"] for r in res) / k,
            "adj": sum(r["adj"] for r in res) / k}


def trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 生成式引擎模拟器")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--mine", required=True, help="你的原文（Markdown/文本）")
    ap.add_argument("--variant", help="你的改写稿")
    ap.add_argument("--rewrite", help="让 LLM 自动改写原文并保存到这个路径，然后参与对比")
    ap.add_argument("--competitors", nargs="*", default=[], help="竞品/同类内容文件（建议 2–4 篇）")
    ap.add_argument("--platform", default="deepseek", choices=list(PROVIDERS))
    ap.add_argument("--trials", type=int, default=3, help="每题每版本模拟次数（默认 3）")
    ap.add_argument("--max-chars", type=int, default=3000, help="每篇来源截取的最大字数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", help="报告输出路径")
    a = ap.parse_args(argv)

    conf = provider_conf(a.platform)
    if not conf["key"] or not conf["model"]:
        sys.exit(f"请先设置 {conf['key_env']}" + ("（豆包还需要 ARK_MODEL）" if a.platform == "doubao" else ""))
    qs = [q["question"] for q in load_questions(a.questions)]
    read = lambda p: trim(open(p, encoding="utf-8", errors="replace").read(), a.max_chars)
    original = read(a.mine)
    comps = [read(p) for p in a.competitors]
    if len(comps) < 2:
        print("提示：竞品来源少于 2 篇时，份额会偏高，建议提供 2–4 篇同类内容。", file=sys.stderr)

    versions = {"原文": original}
    if a.rewrite:
        print("正在按 GEO 规则改写…", file=sys.stderr)
        rew = chat(conf, REWRITE_PROMPT.format(content=original), temperature=0.4)
        open(a.rewrite, "w", encoding="utf-8").write(rew)
        print(f"改写稿已保存到 {a.rewrite}（含【需补充】处请填入真实信息）", file=sys.stderr)
        versions["自动改写"] = trim(rew, a.max_chars)
    if a.variant:
        versions["改写稿"] = read(a.variant)

    rows = []
    for q in qs:
        for name, text in versions.items():
            try:
                r = simulate(conf, q, text, comps, a.trials, a.seed)
            except RuntimeError as e:
                print(f"  失败：{q[:30]}｜{name}：{e}", file=sys.stderr)
                continue
            rows.append({"q": q, "v": name, **r})
            print(f"  {q[:30]}｜{name}：引用率 {r['cited']:.0%}，份额 {r['share']:.0%}", file=sys.stderr)

    L = [f"# 生成式引擎模拟结果（{DISPLAY[a.platform]} · {conf['model']}）", "",
         f"问题 {len(qs)} 个 × 版本 {len(versions)} 个 × 每次 {a.trials} 轮；竞品来源 {len(comps)} 篇。", "",
         "| 问题 | 版本 | 引用率 | 字数份额 | 位置加权份额 |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['q']} | {r['v']} | {r['cited']:.0%} | {r['share']:.0%} | {r['adj']:.0%} |")
    L += ["", "## 汇总", "", "| 版本 | 平均引用率 | 平均字数份额 | 平均位置加权份额 | 相对原文 |", "|---|---|---|---|---|"]
    base = None
    for name in versions:
        rs = [r for r in rows if r["v"] == name]
        if not rs:
            continue
        c = sum(r["cited"] for r in rs) / len(rs)
        s = sum(r["share"] for r in rs) / len(rs)
        adj = sum(r["adj"] for r in rs) / len(rs)
        if base is None:
            base = adj
        rel = "—" if name == "原文" else (f"{(adj - base) / base:+.0%}" if base else "原文未被引用")
        L.append(f"| {name} | {c:.0%} | {s:.0%} | {adj:.0%} | {rel} |")
    L += ["", "> 这是本地模拟：只用于比较版本之间的相对好坏。真实平台还受收录、外部提及、个性化等因素影响，"
          "上线后请用 geo_monitor.py 复测。"]
    md = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
        print(f"已写入 {a.out}", file=sys.stderr)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
