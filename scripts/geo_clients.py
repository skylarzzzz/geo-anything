#!/usr/bin/env python3
"""GEO Anything 客户管理：线索管线、自动提案、月度对比（零依赖）

给接 GEO 服务的个人或工作室用。数据存在 --data 指定的目录（默认 ./geo-clients），
是普通 JSON 文件，可以放进私有仓库同步。

用法：
  python3 geo_clients.py add "某某咖啡" --url https://example.org --type 本地商家 --contact "微信 xxx"
  python3 geo_clients.py list
  python3 geo_clients.py stage "某某咖啡" 已体检
  python3 geo_clients.py audit "某某咖啡" audit.json          # 记录一次体检结果（来自 geo_check.py --json）
  python3 geo_clients.py monitor "某某咖啡" geo-monitor/2026-11-04.json
  python3 geo_clients.py proposal "某某咖啡" --prices "1999,4999,9999" --out proposal.md
  python3 geo_clients.py compare "某某咖啡" --out monthly.md   # 最近两次体检/监测的变化
  python3 geo_clients.py compare --old a.json --new b.json     # 直接对比两个体检文件
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

STAGES = ["线索", "已联系", "已体检", "已提案", "已签约", "服务中", "已结束", "流失"]
DIM_NAMES = {"A": "可引用性", "B": "外部提及度", "C": "实体清晰度", "D": "技术可读性",
             "E": "结构化数据", "F": "平台适配"}
PLAT = {"deepseek": "DeepSeek", "kimi": "Kimi", "qwen": "通义千问", "doubao": "豆包",
        "perplexity": "Perplexity", "openai": "ChatGPT(API)"}


def db_path(data: str) -> str:
    os.makedirs(data, exist_ok=True)
    return os.path.join(data, "clients.json")


def load_db(data: str) -> dict:
    p = db_path(data)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"clients": {}}


def save_db(data: str, db: dict):
    p = db_path(data)
    tmp = p + ".tmp"
    json.dump(db, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def get_client(db: dict, name: str) -> dict:
    c = db["clients"].get(name)
    if not c:
        sys.exit(f"没有找到客户「{name}」，先用 add 添加。现有：{', '.join(db['clients']) or '无'}")
    return c


# ---------------------------------------------------------------- 提案

def proposal_md(c: dict, audit: dict | None, prices: list, brand: str) -> str:
    today = date.today().isoformat()
    L = [f"# {c['name']} · AI 搜索可见度（GEO）优化方案", "",
         f"提交方：{brand} ｜ 日期：{today}", "", "## 一、为什么现在要做", "",
         "越来越多的用户不再翻搜索结果，而是直接问豆包、DeepSeek、元宝、ChatGPT 等 AI。"
         "AI 回答里提到谁、怎么描述、给不给链接，正在影响用户的选择。GEO 的目标是提高"
         f"「{c['name']}」在这些回答中被提及、被准确描述、被附上链接的概率。", ""]
    if audit:
        sc = audit.get("score", 0)
        L += ["## 二、现状诊断", "",
              f"对 {audit.get('source', c.get('url', ''))} 的体检结果：脚本可测部分 **{sc}/100**。", "",
              "| 维度 | 得分 | 满分 |", "|---|---|---|"]
        for k, v in sorted(audit.get("dims", {}).items()):
            L.append(f"| {k} {v['name']} | {v['score']} | {v['full']} |")
        gaps = [x for x in audit.get("checks", []) if x["got"] < x["full"] and x.get("fix")]
        gaps.sort(key=lambda x: -(x["full"] - x["got"]))
        if gaps:
            L += ["", "主要问题："]
            L += [f"- **{x['name']}**：{x['detail']}" for x in gaps[:6]]
        L.append("")
    else:
        L += ["## 二、现状诊断", "", "（尚未体检。建议先运行 geo_check.py 获取基线分数后再发送本方案。）", ""]

    tiers = [
        ("基础版：体检与修复", "一次性",
         ["完整 GEO 体检报告（含 PDF）", "一句话定义与实体卡（全平台统一的介绍文案）",
          "官网/主页的 llms.txt、结构化数据、FAQ 区块", "快赢清单逐项修复", "交付后 1 次复测"],
         "2–3 周"),
        ("标准版：修复 + 内容 + 监测", "按月",
         ["包含基础版全部内容", "每月 4–8 篇可被 AI 引用的问答型内容（官网/公众号/知乎/小红书）",
          "问题池（20–40 个真实用户问题）", "每月多平台监测与复盘报告", "外部提及布点计划与执行建议"],
         "建议至少 3 个月"),
        ("全托管版：持续增长", "按月",
         ["包含标准版全部内容", "每周监测与竞品对比", "第三方平台提及运营（只做真实内容，不刷量）",
          "数据看板与月度会议", "针对新上线 AI 平台的适配"],
         "建议 6 个月起"),
    ]
    L += ["## 三、方案与报价", ""]
    for i, (name, cycle, items, dur) in enumerate(tiers):
        price = prices[i] if i < len(prices) and prices[i] else "<价格>"
        unit = "元" if price != "<价格>" else ""
        L += [f"### {name}", "", f"费用：{price}{unit}（{cycle}）｜ 周期：{dur}", ""]
        L += [f"- {x}" for x in items]
        L.append("")
    L += ["## 四、怎么衡量效果", "",
          "- **可见度**：同一批问题，在每个 AI 平台上「提及 + 描述准确 + 附链接」的得分率，分平台统计，不看平均值",
          "- **体检分**：每月复测，对比各维度变化",
          "- **业务指标**（如有）：来自 AI 平台的访问、咨询、转化", "",
          "## 五、说明", "",
          "- GEO 提高的是被推荐的概率，**不承诺排名或「保证被 AI 推荐」**。",
          "- 全程只使用真实信息：不编造数据和评价、不刷帖、不在页面中隐藏针对 AI 的指令。",
          "- AI 平台收录存在延迟，通常 2–6 周开始看到变化，不同平台节奏不同。", "",
          f"联系：{c.get('owner_contact') or '<你的联系方式>'}", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- 对比

def compare_audits(old: dict, new: dict) -> list:
    L = ["## 体检分变化", "",
         f"总分：{old.get('score', 0)} → **{new.get('score', 0)}**（{new.get('score', 0) - old.get('score', 0):+d}）", "",
         "| 维度 | 上次 | 本次 | 变化 |", "|---|---|---|---|"]
    keys = sorted(set(old.get("dims", {})) | set(new.get("dims", {})))
    for k in keys:
        o = old.get("dims", {}).get(k, {}).get("score")
        n = new.get("dims", {}).get(k, {}).get("score")
        d = f"{n - o:+.1f}" if (o is not None and n is not None) else "—"
        L.append(f"| {k} {DIM_NAMES.get(k, k)} | {o if o is not None else '—'} | {n if n is not None else '—'} | {d} |")
    oc = {x["name"]: x for x in old.get("checks", [])}
    fixed, regress = [], []
    for x in new.get("checks", []):
        p = oc.get(x["name"])
        if not p or x["full"] == 0:
            continue
        if x["got"] > p["got"]:
            fixed.append(f"- ✅ {x['name']}：{p['got']:g} → {x['got']:g}")
        elif x["got"] < p["got"]:
            regress.append(f"- ⚠️ {x['name']}：{p['got']:g} → {x['got']:g}（{x['detail']}）")
    L += ["", "### 已改善", ""] + (fixed or ["- 无"]) + ["", "### 退步（需处理）", ""] + (regress or ["- 无"])
    return L


def compare_monitors(old: dict, new: dict) -> list:
    L = ["## AI 平台可见度变化", "", "| 平台 | 上次 | 本次 | 变化 |", "|---|---|---|---|"]
    for p in sorted(set(old.get("summary", {})) | set(new.get("summary", {}))):
        o = old.get("summary", {}).get(p, {}).get("visibility")
        n = new.get("summary", {}).get(p, {}).get("visibility")
        d = f"{n - o:+.0f} 个百分点" if (o is not None and n is not None) else "—"
        L.append(f"| {PLAT.get(p, p)} | {'—' if o is None else f'{o:.0f}%'} | {'—' if n is None else f'{n:.0f}%'} | {d} |")
    L += ["", "> 分平台看：一个平台上升、另一个平台下降是常见现象，平均值会掩盖下降。"]
    return L


def monthly_md(name: str, a_old, a_new, m_old, m_new) -> str:
    L = [f"# {name} · GEO 月度报告", "", f"日期：{date.today().isoformat()}", ""]
    if a_old and a_new:
        L += compare_audits(a_old, a_new) + [""]
    elif a_new:
        L += ["## 体检分", "", f"本次 {a_new.get('score')}/100（暂无上次记录可对比）", ""]
    if m_old and m_new:
        L += compare_monitors(m_old, m_new) + [""]
    elif m_new:
        L += ["## AI 平台可见度", ""] + [f"- {PLAT.get(p, p)}：{s['visibility']:.0f}%" for p, s in m_new.get("summary", {}).items()] + [""]
    L += ["## 下月动作", "", "1. <根据「退步」和最低的平台补内容或修复>", "2. <……>", "3. <……>", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 客户管理")
    ap.add_argument("--data", default="geo-clients", help="数据目录（默认 ./geo-clients）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="添加客户/线索")
    s.add_argument("name"); s.add_argument("--url", default=""); s.add_argument("--type", default="")
    s.add_argument("--contact", default=""); s.add_argument("--notes", default="")
    s.add_argument("--stage", default="线索", choices=STAGES)
    sub.add_parser("list", help="列出全部客户")
    s = sub.add_parser("stage", help="更新阶段"); s.add_argument("name"); s.add_argument("stage", choices=STAGES)
    s = sub.add_parser("note", help="追加备注"); s.add_argument("name"); s.add_argument("text")
    s = sub.add_parser("audit", help="记录体检结果"); s.add_argument("name"); s.add_argument("file")
    s = sub.add_parser("monitor", help="记录监测结果"); s.add_argument("name"); s.add_argument("file")
    s = sub.add_parser("proposal", help="生成提案")
    s.add_argument("name"); s.add_argument("--audit", help="指定体检文件（默认用最近一次记录）")
    s.add_argument("--prices", default="", help="三档报价，逗号分隔，如 1999,4999,9999")
    s.add_argument("--brand", default="<你的工作室>"); s.add_argument("--out")
    s = sub.add_parser("compare", help="月度对比")
    s.add_argument("name", nargs="?"); s.add_argument("--old"); s.add_argument("--new"); s.add_argument("--out")
    a = ap.parse_args(argv)

    db = load_db(a.data)
    out_text = None
    if a.cmd == "add":
        if a.name in db["clients"]:
            sys.exit(f"客户「{a.name}」已存在")
        db["clients"][a.name] = {"name": a.name, "url": a.url, "type": a.type, "contact": a.contact,
                                 "stage": a.stage, "created": date.today().isoformat(),
                                 "notes": [a.notes] if a.notes else [], "audits": [], "monitors": []}
        save_db(a.data, db)
        print(f"已添加「{a.name}」（{a.stage}）")
    elif a.cmd == "list":
        cs = db["clients"].values()
        if not cs:
            print("还没有客户")
        print("| 客户 | 类型 | 阶段 | 最近体检分 | 最近监测 | 网址 |\n|---|---|---|---|---|---|")
        for c in sorted(cs, key=lambda c: STAGES.index(c["stage"])):
            la = c["audits"][-1] if c["audits"] else None
            lm = c["monitors"][-1] if c["monitors"] else None
            ms = "、".join(f"{PLAT.get(p, p)} {v['visibility']:.0f}%" for p, v in (lm or {}).get("summary", {}).items())
            print(f"| {c['name']} | {c['type']} | {c['stage']} | "
                  f"{(str(la['score']) + '（' + la['date'] + '）') if la else '—'} | {ms or '—'} | {c['url']} |")
    elif a.cmd == "stage":
        get_client(db, a.name)["stage"] = a.stage
        save_db(a.data, db); print(f"「{a.name}」→ {a.stage}")
    elif a.cmd == "note":
        get_client(db, a.name)["notes"].append(f"{date.today().isoformat()} {a.text}")
        save_db(a.data, db); print("已记录")
    elif a.cmd in ("audit", "monitor"):
        c = get_client(db, a.name)
        data = json.load(open(a.file, encoding="utf-8"))
        data.setdefault("date", date.today().isoformat())
        c["audits" if a.cmd == "audit" else "monitors"].append(data)
        if a.cmd == "audit" and STAGES.index(c["stage"]) < STAGES.index("已体检"):
            c["stage"] = "已体检"
        save_db(a.data, db)
        print(f"已记录「{a.name}」的{'体检' if a.cmd == 'audit' else '监测'}结果（共 {len(c[a.cmd + 's'])} 次）")
    elif a.cmd == "proposal":
        c = get_client(db, a.name)
        audit = json.load(open(a.audit, encoding="utf-8")) if a.audit else (c["audits"][-1] if c["audits"] else None)
        prices = [x.strip() for x in a.prices.split(",")] if a.prices else []
        out_text = proposal_md(c, audit, prices, a.brand)
        if STAGES.index(c["stage"]) < STAGES.index("已提案"):
            c["stage"] = "已提案"
            save_db(a.data, db)
    elif a.cmd == "compare":
        if a.old and a.new:
            o, n = (json.load(open(f, encoding="utf-8")) for f in (a.old, a.new))
            is_mon = "summary" in n and "results" in n
            out_text = monthly_md(a.name or n.get("source", "对比"), None if is_mon else o, None if is_mon else n,
                                  o if is_mon else None, n if is_mon else None)
        elif a.name:
            c = get_client(db, a.name)
            A, M = c["audits"], c["monitors"]
            out_text = monthly_md(a.name, A[-2] if len(A) >= 2 else None, A[-1] if A else None,
                                  M[-2] if len(M) >= 2 else None, M[-1] if M else None)
        else:
            sys.exit("请提供客户名，或同时提供 --old 和 --new")
    if out_text is not None:
        if getattr(a, "out", None):
            open(a.out, "w", encoding="utf-8").write(out_text)
            print(f"已写入 {a.out}")
        else:
            print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
