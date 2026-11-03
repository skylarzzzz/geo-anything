#!/usr/bin/env python3
"""GEO Anything 搜索数据分析：把搜索平台导出的查询词表变成 GEO 内容机会和问题池（零依赖）

支持的导出文件（CSV，中英文表头都能识别）：
  - Google Search Console：效果 → 导出 → 「查询数」表（Queries.csv）
  - 百度搜索资源平台：搜索效果 → 导出关键词数据
  - 必应站长工具、其他工具：只要有「查询词/关键词、点击、展示/展现、排名」几列即可

为什么不用 API：Search Console API 需要 OAuth 授权和额外依赖，手机用户难以配置；
导出 CSV 在网页端点两下就能拿到，效果相同。

用法：
  python3 geo_gsc.py Queries.csv                         # 输出分析报告
  python3 geo_gsc.py Queries.csv --brand "慢慢,slowly"    # 区分品牌词与非品牌词
  python3 geo_gsc.py Queries.csv --questions-out geo/questions.txt   # 生成给 geo_monitor 用的问题池
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys

COLS = {
    "query": ["top queries", "query", "queries", "热门查询", "查询", "查询词", "关键词", "搜索词", "keyword", "keywords"],
    "clicks": ["clicks", "点击次数", "点击", "点击量"],
    "impr": ["impressions", "展示", "展示次数", "展现", "展现量", "曝光"],
    "ctr": ["ctr", "点击率"],
    "pos": ["position", "排名", "平均排名", "average position", "avg. position"],
}
Q_RE = re.compile(r"(什么|为什么|怎么|如何|哪个|哪些|哪家|是否|能不能|可以|有没有|多少|吗|呢|推荐|好用|区别|对比|"
                  r"教程|方法|步骤|\bvs\b|^(what|why|how|which|best|can|does|is|should|where|when)\b|\?|？)", re.I)
INTENT = [
    ("对比", re.compile(r"(区别|对比|比较|哪个好|哪个更|\bvs\b|versus|alternative|替代|还是)", re.I)),
    ("操作", re.compile(r"(怎么|如何|教程|步骤|方法|how to|tutorial|guide|设置|使用)", re.I)),
    ("认知", re.compile(r"(什么|有没有|推荐|哪些|哪家|best|top|what is|工具|软件|app)", re.I)),
]


def read_csv(path: str) -> list:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("无法识别文件编码")
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    # 找表头行（前 10 行中包含查询列的那一行）
    for hi, row in enumerate(rows[:10]):
        low = [c.strip().lower() for c in row]
        if any(c in COLS["query"] for c in low):
            break
    else:
        sys.exit("没有找到「查询词/关键词」列，请确认导出的是查询数据表")
    header = [c.strip().lower() for c in rows[hi]]
    idx = {}
    for k, names in COLS.items():
        for i, h in enumerate(header):
            if h in names:
                idx[k] = i
                break
    if "query" not in idx:
        sys.exit("没有找到查询词列")

    def num(v: str) -> float:
        v = (v or "").strip().replace(",", "").replace("%", "")
        try:
            return float(v)
        except ValueError:
            return 0.0

    out = []
    for r in rows[hi + 1:]:
        if len(r) <= idx["query"] or not r[idx["query"]].strip():
            continue
        g = lambda k: num(r[idx[k]]) if k in idx and idx[k] < len(r) else 0.0
        clicks, impr = g("clicks"), g("impr")
        ctr = g("ctr")
        raw_ctr = r[idx["ctr"]] if "ctr" in idx and idx["ctr"] < len(r) else ""
        if "%" in raw_ctr or ctr > 1:          # 「0.33%」或「33」都表示百分数
            ctr /= 100
        if not ctr and impr:
            ctr = clicks / impr
        out.append({"q": r[idx["query"]].strip(), "clicks": clicks, "impr": impr, "ctr": ctr, "pos": g("pos")})
    return out


def intent_of(q: str) -> str:
    for name, rx in INTENT:
        if rx.search(q):
            return name
    return "认知"


def to_question(q: str) -> str:
    """把搜索关键词改写成更像「问 AI」的句子。"""
    s = q.strip()
    if Q_RE.search(s) and re.search(r"[?？吗呢]$|^(what|why|how|which|can|does|is|should)\b", s, re.I):
        return s
    if re.search(r"[一-鿿]", s):
        if re.search(r"(推荐|哪个好|好用)$", s):
            return s + "？"
        if re.search(r"(怎么|如何|教程|方法|步骤)", s):
            return s.rstrip("？?") + "？"
        return f"{s}有哪些推荐？"
    if s.endswith("?"):
        return s
    if re.search(r"\bvs\.?\b|versus", s, re.I):
        return f"{s}: which is better?"
    return f"What are the best options for {s}?"


def analyze(rows: list, brand: list, top: int) -> tuple:
    brand_l = [b.lower() for b in brand]
    is_brand = lambda q: any(b in q.lower() for b in brand_l)
    total_impr = sum(r["impr"] for r in rows) or 1
    questions = [r for r in rows if Q_RE.search(r["q"])]
    # 高曝光低点击：曝光在前 30%，点击率低于该排名段的一般水平
    imprs = sorted((r["impr"] for r in rows), reverse=True)
    cutoff = imprs[int(len(imprs) * 0.3)] if imprs else 0
    low_ctr = [r for r in rows if r["impr"] >= max(cutoff, 10) and r["ctr"] < (0.05 if r["pos"] <= 5 else 0.02)]
    striking = [r for r in rows if 4 <= r["pos"] <= 20 and r["impr"] >= 10]
    non_brand = [r for r in rows if not is_brand(r["q"])]
    sort = lambda xs: sorted(xs, key=lambda r: -r["impr"])[:top]
    return {
        "n": len(rows), "impr": total_impr, "clicks": sum(r["clicks"] for r in rows),
        "brand_share": (sum(r["impr"] for r in rows if is_brand(r["q"])) / total_impr) if brand else None,
        "questions": sort(questions), "low_ctr": sort(low_ctr), "striking": sort(striking),
        "pool": sort([r for r in non_brand if Q_RE.search(r["q"])] or non_brand),
    }


def render(res: dict, brand: list) -> str:
    fmt = lambda r: f"| {r['q']} | {intent_of(r['q'])} | {r['impr']:.0f} | {r['clicks']:.0f} | {r['ctr'] * 100:.1f}% | {r['pos']:.1f} |"
    head = "| 查询 | 意图 | 展示 | 点击 | 点击率 | 排名 |\n|---|---|---|---|---|---|"
    L = ["# 搜索数据 → GEO 机会分析", "",
         f"共 {res['n']} 个查询，展示 {res['impr']:.0f} 次，点击 {res['clicks']:.0f} 次。"]
    if res["brand_share"] is not None:
        L.append(f"品牌词（{'、'.join(brand)}）占展示的 {res['brand_share'] * 100:.0f}%。"
                 + ("非品牌词占比高，说明有不少人在搜「问题」而不是搜你，正是 GEO 要抢的流量。"
                    if res["brand_share"] < 0.5 else "品牌词占比高，非品牌问题的覆盖还有空间。"))
    L += ["", "## 1. 问题型查询（用户也会拿去问 AI）", "",
          "这些查询本身就是问题，AI 搜索会直接生成答案。给每个问题准备一个「首句即答案」的段落或 FAQ。", "", head]
    L += [fmt(r) for r in res["questions"]] or ["| 无 | | | | | |"]
    L += ["", "## 2. 高曝光、低点击（被看见但没被选中）", "",
          "这类查询很可能已经出现 AI 摘要，用户看完摘要就走了。优化方向：让你的页面成为摘要引用的来源"
          "（定义句、数字、问答结构），同时改写标题和描述。", "", head]
    L += [fmt(r) for r in res["low_ctr"]] or ["| 无 | | | | | |"]
    L += ["", "## 3. 排名 4–20 的潜力词", "",
          "排名接近首页，补一段直接回答、加对比表或 FAQ，通常最容易同时提升搜索排名和 AI 引用。", "", head]
    L += [fmt(r) for r in res["striking"]] or ["| 无 | | | | | |"]
    L += ["", "## 4. 建议的问题池（可直接给 geo_monitor.py 使用）", ""]
    L += [f"- {intent_of(r['q'])}｜{to_question(r['q'])}" for r in res["pool"]]
    L += ["", "> 搜索数据反映的是「搜索框里的需求」，AI 对话里的问题通常更长、更口语化，可在此基础上补充。"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 搜索数据分析")
    ap.add_argument("csv", help="Search Console / 百度搜索资源平台导出的查询 CSV")
    ap.add_argument("--brand", default="", help="品牌词，逗号分隔")
    ap.add_argument("--top", type=int, default=15, help="每类最多列出多少条")
    ap.add_argument("--out", help="报告输出路径")
    ap.add_argument("--questions-out", help="把问题池写成 geo_monitor 可用的文件")
    a = ap.parse_args(argv)
    brand = [x.strip() for x in re.split(r"[,，]", a.brand) if x.strip()]
    rows = read_csv(a.csv)
    if not rows:
        sys.exit("文件里没有数据行")
    res = analyze(rows, brand, a.top)
    md = render(res, brand)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(md)
        print(f"已写入 {a.out}")
    else:
        print(md)
    if a.questions_out:
        with open(a.questions_out, "w", encoding="utf-8") as f:
            f.write("# 由 geo_gsc.py 根据搜索数据生成，建议人工检查后再使用\n")
            for r in res["pool"]:
                f.write(f"{intent_of(r['q'])}|{to_question(r['q'])}\n")
        print(f"问题池已写入 {a.questions_out}（{len(res['pool'])} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
