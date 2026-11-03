#!/usr/bin/env python3
"""GEO Anything 小红书笔记体检：按「问一问」「点点」的选取逻辑给笔记打分（零依赖）

用法：
  python3 geo_xhs.py note.txt                         # 第一行是标题，其余是正文（含话题标签）
  python3 geo_xhs.py note.txt --type 视频 --subtitle sub.txt --date 2026-10-01
  python3 geo_xhs.py note.txt --image-text img.txt --keyword "油皮防晒"
  python3 geo_xhs.py notes/ --json                    # 批量：目录下每个 .txt 一篇

--image-text：图片上的文字（封面标题、表格、标注），可手动抄录或用手机自带的「提取文字」
--subtitle：视频字幕或口播稿
依据：references/xiaohongshu.md。评分为经验规则，用于比较和改进，不代表平台官方算法。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime

CJK = re.compile(r"[一-鿿]")
NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|元|块|天|小时|分钟|岁|ml|g|款|个|步|次|周|月|年|cm|kg)?", re.I)
QUESTION = re.compile(r"([?？]|怎么|如何|为什么|什么|哪|是否|能不能|可以吗|有没有|吗$|值不值|要不要|区别|对比|推荐|测评|攻略|避坑)")
FILLER = re.compile(r"^(姐妹们|宝子们|家人们|集美们|宝宝们|今天|最近|终于|救命|谁懂|绝了|天呐)")
ANSWER_CUE = re.compile(r"(结论|答案|直接说|先说|推荐|选|就是|是|建议|适合|不要|别|可以|能)")
POINTS = re.compile(r"(^|\n)\s*(\d+[.、)）]|[①②③④⑤⑥⑦⑧⑨]|[1-9]️⃣|[一二三四五六七八九]、|[-•·▪✅✔📌])", re.M)
EXPERIENCE = re.compile(r"(实测|亲测|自用|用了\s*\d+|测试了|试了\s*\d+|对比了|坚持了|我的经验|踩过|翻车|空瓶|回购|\d+\s*(天|周|个月|年)(后|下来)?)")
FIT = re.compile(r"(适合|不适合|人群|谁适合|避雷|注意|缺点)")
SOURCE = re.compile(r"(来源|出处|官方|论文|研究|数据来自|根据|说明书|官网)")
ABSOLUTE = re.compile(r"(最好|最强|第一|顶级|绝对|100%|百分百|神器|必买|全网最|史上最|永久|根治|立刻见效)")
LURE = re.compile(r"(微信|vx|v信|wx|加我|私信领取|私我|二维码|淘宝搜|拼多多|链接在|主页领|戳我|进群|群聊)", re.I)
HASHTAG = re.compile(r"#[^\s#]+")
INVITE = re.compile(r"(评论区|告诉我|你们|你会|你觉得|还想看|想了解|留言|问我)")


def clen(s: str) -> int:
    return len(CJK.findall(s)) + len(re.findall(r"[A-Za-z]+", s))


def bigrams(s: str) -> set:
    t = "".join(CJK.findall(s))
    return {t[i:i + 2] for i in range(len(t) - 1)}


def parse_note(path: str) -> tuple:
    text = open(path, encoding="utf-8", errors="replace").read().strip()
    lines = text.splitlines()
    title = re.sub(r"^(标题[:：])", "", lines[0]).strip() if lines else ""
    body = "\n".join(lines[1:]).strip()
    body = re.sub(r"^(正文[:：])", "", body).strip()
    return title, body


def check(title: str, body: str, kind: str, image_text: str, subtitle: str, pub: str, keyword: str) -> dict:
    C = []

    def add(group, name, got, full, detail, fix=""):
        C.append({"group": group, "name": name, "got": got, "full": full, "detail": detail, "fix": fix})

    text_only = HASHTAG.sub("", body)
    first50 = "".join(text_only.split())[:50]
    tags = HASHTAG.findall(body)
    core = bigrams(keyword) if keyword else bigrams(title)

    # 标题 20
    add("标题", "问题式/答案式标题", 8 if QUESTION.search(title) else 0, 8, f"标题：{title}",
        "把标题写成用户会问的完整问题，例如「油皮夏天用什么防晒不闷痘？」")
    add("标题", "标题含具体数字", 4 if NUM.search(title) else 0, 4, "有数字" if NUM.search(title) else "无数字",
        "加入实测数量、价格、天数等数字，如「我实测了 6 款」")
    tl = clen(title)
    add("标题", "标题长度", 4 if 8 <= tl <= 20 else (2 if tl else 0), 4, f"{tl} 字（建议 8–20 字）",
        "小红书标题上限约 20 字，控制在 8–20 字内并保留问题主干")
    stuffing = title.count("|") + title.count("｜") + title.count("/") >= 2
    add("标题", "没有关键词堆砌", 0 if stuffing else 4, 4, "疑似堆砌" if stuffing else "正常",
        "用一句通顺的话代替「词｜词｜词」式标题")

    # 前 50 字 20
    ans = bool(ANSWER_CUE.search(first50)) and (bool(NUM.search(first50)) or len(first50) >= 20)
    add("开头", "前 50 字给出结论", 10 if ans else 0, 10, f"开头：{first50}",
        "第一句直接回答标题的问题，最好带一个具体数字或结论")
    add("开头", "开头没有寒暄铺垫", 0 if FILLER.search(first50) else 5, 5,
        "以寒暄开头" if FILLER.search(first50) else "直接进入正题", "删掉「姐妹们」「今天」等开场白，先给答案")
    overlap = len(core & bigrams(first50))
    add("开头", "开头呼应标题关键词", 5 if overlap >= 3 else (2 if overlap else 0), 5,
        f"与标题/关键词重合 {overlap} 个词片段", "开头复述标题里的核心词，让 AI 确认这段在回答哪个问题")

    # 结构与信息 20
    pts = len(POINTS.findall(body))
    add("结构", "分点论述", 8 if pts >= 3 else (4 if pts else 0), 8, f"{pts} 个要点标记",
        "用 1/2/3 或 1️⃣2️⃣3️⃣ 分点，每点一句结论加依据")
    blen = max(clen(text_only), 1)
    nums = len(NUM.findall(text_only))
    add("结构", "数据与细节", 6 if nums >= 5 else (3 if nums >= 2 else 0), 6, f"正文 {nums} 个数字",
        "补充真实的价格、时长、规格、测试结果")
    add("结构", "篇幅适中", 6 if 300 <= blen <= 1200 else (3 if blen >= 150 else 0), 6, f"约 {blen} 字",
        "正文 300–1200 字较适合被摘录：太短信息不够，太长重点不明")

    # 可信度 15
    add("可信", "一手实测/经验", 6 if EXPERIENCE.search(text_only) else 0, 6,
        "有实测表述" if EXPERIENCE.search(text_only) else "没有实测或使用过程",
        "写清你怎么测的：用了多久、什么条件、对比了几款（只写真实经历）")
    add("可信", "适合谁/不适合谁", 3 if FIT.search(text_only) else 0, 3, "有" if FIT.search(text_only) else "无",
        "加一行「适合 / 不适合」，AI 回答选型问题时常会引用")
    add("可信", "注明依据来源", 3 if SOURCE.search(text_only) else 0, 3, "有" if SOURCE.search(text_only) else "无",
        "引用说明书、官方数据或研究时注明出处")
    absw = sorted(set(ABSOLUTE.findall(title + text_only)))
    add("可信", "没有绝对化用语", 0 if absw else 3, 3, f"出现：{'、'.join(absw)}" if absw else "无",
        "去掉「最好」「第一」「神器」等绝对化用语（也可能触发平台限流）")

    # 多模态 10
    if kind == "视频":
        has = bool(subtitle.strip())
        add("多模态", "有字幕/口播稿", 5 if has else 0, 5, "已提供" if has else "未提供字幕",
            "视频一定要加字幕，AI 会读取字幕文字")
        first = "".join(subtitle.split())[:60]
        hit = len(core & bigrams(first)) >= 2
        add("多模态", "前 15 秒说出关键词和结论", 5 if hit else 0, 5, f"开头字幕：{first or '无'}",
            "前 15 秒口播先说问题和结论")
    else:
        has = bool(image_text.strip())
        add("多模态", "图片上有文字信息", 5 if has else 0, 5, "已提供图片文字" if has else "未提供或图片无文字",
            "封面写标题问题，图内标注关键信息（对比、价格、成分、地址）")
        rich = has and (len(NUM.findall(image_text)) >= 2 or "|" in image_text or "：" in image_text)
        add("多模态", "图片含关键数据或对比", 5 if rich else 0, 5, "有" if rich else "无",
            "第 2–3 张做成对比表或步骤图，把数字直接写在图上")

    # 话题与互动 10
    add("话题", "话题数量", 4 if 3 <= len(tags) <= 8 else (2 if tags else 0), 4, f"{len(tags)} 个：{' '.join(tags[:8])}",
        "放 3–8 个话题：问题类 + 高热 + 垂直")
    qtag = any(QUESTION.search(t) for t in tags)
    add("话题", "有问题类话题", 2 if qtag else 0, 2, "有" if qtag else "无", "加一个问题形式的话题，如 #油皮防晒怎么选")
    tail = "".join(text_only.split())[-60:]
    add("话题", "结尾邀请提问", 4 if INVITE.search(tail) else 0, 4, "有" if INVITE.search(tail) else "无",
        "结尾问一句「你还想了解 XX 吗？」，引导真实讨论（不要自问自答刷评论）")

    # 新鲜度 5
    if pub:
        try:
            days = (date.today() - datetime.strptime(pub, "%Y-%m-%d").date()).days
            add("新鲜度", "发布/更新时间", 5 if days <= 180 else (2 if days <= 365 else 0), 5, f"{days} 天前",
                "超过约半年的笔记建议更新信息或发布更新版")
        except ValueError:
            pass

    risks = []
    lure = sorted(set(LURE.findall(title + body)))
    if lure:
        risks.append(f"疑似站外引流用语：{'、'.join(lure)}（可能限流，且 AI 不会引用）")
    if absw:
        risks.append(f"绝对化用语：{'、'.join(absw)}")
    got = sum(c["got"] for c in C)
    full = sum(c["full"] for c in C) or 1
    return {"title": title, "score": round(got / full * 100), "checks": C, "risks": risks}


def render(r: dict) -> str:
    L = [f"## 《{r['title']}》 {r['score']}/100", ""]
    if r["risks"]:
        L += ["**风险提示**：" + "；".join(r["risks"]), ""]
    gaps = sorted([c for c in r["checks"] if c["got"] < c["full"]], key=lambda c: -(c["full"] - c["got"]))
    if gaps:
        L += ["**优先修改：**"] + [f"{i}. {c['name']}：{c['fix']}（+{c['full'] - c['got']} 分）"
                                  for i, c in enumerate(gaps[:5], 1)] + [""]
    L += ["| 类别 | 检查项 | 得分 | 说明 |", "|---|---|---|---|"]
    L += [f"| {c['group']} | {c['name']} | {c['got']}/{c['full']} | {c['detail'].replace('|', '/')} |" for c in r["checks"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="小红书笔记 GEO 体检")
    ap.add_argument("note", help="笔记文件（第一行标题），或包含多个 .txt 的目录")
    ap.add_argument("--type", default="图文", choices=["图文", "视频"])
    ap.add_argument("--image-text", help="图片上的文字（文件）")
    ap.add_argument("--subtitle", help="视频字幕或口播稿（文件）")
    ap.add_argument("--date", default="", help="发布或最近更新日期 YYYY-MM-DD")
    ap.add_argument("--keyword", default="", help="这篇笔记主答的问题关键词")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rd = lambda p: open(p, encoding="utf-8", errors="replace").read() if p else ""
    files = ([os.path.join(a.note, f) for f in sorted(os.listdir(a.note)) if f.endswith(".txt")]
             if os.path.isdir(a.note) else [a.note])
    results = []
    for f in files:
        title, body = parse_note(f)
        results.append(check(title, body, a.type, rd(a.image_text), rd(a.subtitle), a.date, a.keyword))
    if a.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))
    else:
        if len(results) > 1:
            print("| 笔记 | 得分 |\n|---|---|")
            for r in sorted(results, key=lambda r: r["score"]):
                print(f"| {r['title']} | {r['score']} |")
            print()
        for r in results:
            print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
