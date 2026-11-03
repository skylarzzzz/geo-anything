#!/usr/bin/env python3
"""GEO Anything 报告生成器：把体检 / 监测结果做成可交付的图表报告（支持白标）

输入：geo_check.py --json 的体检结果，和/或 geo_monitor.py 输出的监测 JSON。
输出：
  - 自包含 HTML（零依赖，含仪表盘、柱状图，手机可看，浏览器「打印 → 存储为 PDF」即得 PDF）
  - PDF（可选，需要 pip install reportlab；中文使用内置字体，无需额外字体文件）

用法：
  python3 geo_check.py https://example.com --json > audit.json
  python3 geo_report.py --audit audit.json --out report.html
  python3 geo_report.py --audit audit.json --monitor geo-monitor/2026-11-04.json --out report.html --pdf report.pdf

白标（以你自己的工作室名义交付给客户）：
  --brand "某某 GEO 工作室" --color "#E8590C" --logo logo.png --client "客户名称" --footer "联系：…"
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import mimetypes
import os
import sys
from datetime import date

DIM_ORDER = ["A", "B", "C", "D", "E", "F"]
DIM_NAMES = {"A": "可引用性", "B": "外部提及度", "C": "实体清晰度", "D": "技术可读性",
             "E": "结构化数据", "F": "平台适配"}
PLAT_NAMES = {"deepseek": "DeepSeek", "kimi": "Kimi", "qwen": "通义千问", "doubao": "豆包",
              "perplexity": "Perplexity", "openai": "ChatGPT(API)"}


def esc(x) -> str:
    return html.escape(str(x))


def grade(s: float) -> str:
    return "容易被引用" if s >= 80 else "有机会但有缺口" if s >= 60 else "基本不可见" if s >= 40 else "先修基础问题"


def logo_src(path: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://", "data:")):
        return path
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


# ---------------------------------------------------------------- SVG 图表

def gauge_svg(score: float, color: str) -> str:
    r, cx, cy = 80, 100, 100
    frac = max(0.0, min(1.0, score / 100))
    ang = math.pi * (1 - frac)
    x, y = cx + r * math.cos(ang), cy - r * math.sin(ang)
    large = 0
    return (f'<svg viewBox="0 0 200 120" class="gauge" role="img" aria-label="得分 {score:.0f}">'
            f'<path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--track)" stroke-width="16" stroke-linecap="round"/>'
            + (f'<path d="M20 100 A80 80 0 {large} 1 {x:.1f} {y:.1f}" fill="none" stroke="{esc(color)}" '
               f'stroke-width="16" stroke-linecap="round"/>' if frac > 0 else "")
            + f'<text x="100" y="92" text-anchor="middle" class="g-num">{score:.0f}</text>'
            f'<text x="100" y="114" text-anchor="middle" class="g-sub">/ 100</text></svg>')


def bars_svg(rows: list, color: str, max_value: float = 100, unit: str = "%") -> str:
    """rows: [(label, value, full)]；value 按 full 换算成百分比宽度。"""
    h = 34 * len(rows) + 8
    out = [f'<svg viewBox="0 0 360 {h}" class="bars" role="img">']
    for i, (label, value, full) in enumerate(rows):
        y = 8 + i * 34
        pct = 0 if not full else max(0.0, min(1.0, value / full))
        w = 200 * pct
        txt = f"{value:g}/{full:g}" if unit == "" else f"{value:.0f}{unit}"
        out.append(f'<text x="0" y="{y + 15}" class="b-label">{esc(label)}</text>'
                   f'<rect x="110" y="{y + 3}" width="200" height="16" rx="8" fill="var(--track)"/>'
                   + (f'<rect x="110" y="{y + 3}" width="{w:.1f}" height="16" rx="8" fill="{esc(color)}"/>' if w > 0 else "")
                   + f'<text x="318" y="{y + 15}" class="b-val">{esc(txt)}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#faf9f7;--card:#fff;--ink:#1f1d1a;--muted:#6b665e;--line:#e7e3dc;--track:#efebe4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--card:#201f1c;--ink:#f1eee8;--muted:#a39d93;--line:#34312c;--track:#2c2a26}}
:root[data-theme="dark"]{--bg:#171614;--card:#201f1c;--ink:#f1eee8;--muted:#a39d93;--line:#34312c;--track:#2c2a26}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:28px 16px 60px}
header{display:flex;align-items:center;gap:12px;border-bottom:3px solid var(--brand);padding-bottom:14px;margin-bottom:22px}
header img{height:36px;max-width:140px;object-fit:contain}
.brand{font-weight:700;letter-spacing:.02em}.meta{color:var(--muted);font-size:13px;margin-left:auto;text-align:right}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px;padding-left:10px;border-left:4px solid var(--brand)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.hero{display:grid;grid-template-columns:220px 1fr;gap:18px;align-items:center}
@media (max-width:620px){.hero{grid-template-columns:1fr}}
.gauge{width:100%;max-width:220px}.g-num{font-size:40px;font-weight:700;fill:var(--ink)}.g-sub{font-size:12px;fill:var(--muted)}
.bars{width:100%}.b-label{font-size:12px;fill:var(--ink)}.b-val{font-size:12px;fill:var(--muted)}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;background:var(--brand);color:#fff;font-size:13px}
ol li{margin:6px 0}table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:7px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.ok{color:#2f9e44}.bad{color:#e03131}.muted{color:var(--muted)}
.tablewrap{overflow-x:auto}footer{margin-top:36px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
@media print{body{background:#fff}.card{break-inside:avoid}}
"""


def build_html(audit: dict | None, monitor: dict | None, o) -> str:
    color = o.color
    title_obj = (audit or {}).get("title") or (audit or {}).get("source") or "、".join((monitor or {}).get("names", [])[:2])
    P = [f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
         f'<meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>GEO 报告 · {esc(o.client or title_obj)}</title><style>:root{{--brand:{esc(color)}}}{CSS}</style></head>'
         f'<body><div class="wrap"><header>']
    if o.logo:
        P.append(f'<img src="{esc(logo_src(o.logo))}" alt="">')
    P.append(f'<div class="brand">{esc(o.brand)}</div><div class="meta">{esc(date.today().isoformat())}'
             + (f'<br>客户：{esc(o.client)}' if o.client else "") + '</div></header>')
    P.append(f'<h1>AI 搜索可见度（GEO）报告</h1><div class="muted">对象：{esc(title_obj)}</div>')

    if audit:
        sc = audit.get("score", 0)
        dims = audit.get("dims", {})
        rows = [(f"{k} {v['name']}", v["score"], v["full"]) for k, v in sorted(dims.items())]
        P.append('<h2>总体得分</h2><div class="card hero">' + gauge_svg(sc, color) +
                 f'<div><span class="pill">{esc(grade(sc))}</span>'
                 f'<p>可测维度合计 {audit.get("measured", 0)}/{audit.get("measured_full", 0)}。'
                 '外部提及度与平台适配需结合联网调研与实测（见下方监测部分）。</p>'
                 + bars_svg(rows, color, unit="") + '</div></div>')
        checks = audit.get("checks", [])
        gaps = [c for c in checks if c["got"] < c["full"] and c.get("fix")]
        gaps.sort(key=lambda c: (-(c["full"] - c["got"]) / max(c.get("minutes", 15), 1)))
        if gaps:
            P.append('<h2>优先行动（快赢）</h2><div class="card"><ol>')
            for c in gaps[:6]:
                P.append(f'<li><b>{esc(c["name"])}</b>：{esc(c["fix"])} '
                         f'<span class="muted">（约 {c.get("minutes", 15)} 分钟，+{c["full"] - c["got"]:g} 分）</span></li>')
            P.append('</ol></div>')
        P.append('<h2>检查明细</h2><div class="card tablewrap"><table><tr><th>维度</th><th>检查项</th><th>得分</th><th>说明</th></tr>')
        for c in checks:
            if c["full"] == 0:
                cls, sc_txt = "muted", "不适用"
            else:
                cls = "ok" if c["got"] >= c["full"] else ("bad" if c["got"] == 0 else "")
                sc_txt = f'{c["got"]:g}/{c["full"]:g}'
            P.append(f'<tr><td>{esc(c["dim"])}</td><td>{esc(c["name"])}</td><td class="{cls}">{sc_txt}</td>'
                     f'<td>{esc(c["detail"])}</td></tr>')
        P.append('</table></div>')

    if monitor:
        summ = monitor.get("summary", {})
        rows = [(f"{PLAT_NAMES.get(p, p)}·{s['mode']}", s["visibility"], 100) for p, s in summ.items()]
        P.append('<h2>AI 平台可见度</h2><div class="card">' + bars_svg(rows, color) +
                 '<p class="muted">可见度 = 提及 + 描述准确 + 附链接，每题满分 3 分；「模型记忆」反映模型本身的认知，'
                 '「联网」反映搜索后的回答。</p></div>')
        res = monitor.get("results", [])
        if res:
            P.append('<div class="card tablewrap" style="margin-top:12px"><table><tr><th>问题</th><th>平台</th><th>提及</th><th>准确</th><th>链接</th></tr>')
            mk = lambda v: '<span class="muted">待人工</span>' if v is None else ('<span class="ok">✓</span>' if v else '<span class="bad">✗</span>')
            for r in res:
                if not r.get("ok"):
                    continue
                j = r["judge"]
                P.append(f'<tr><td>{esc(r["question"])}</td><td>{esc(PLAT_NAMES.get(r["platform"], r["platform"]))}</td>'
                         f'<td>{mk(j["mention"])}</td><td>{mk(j["accurate"])}</td><td>{mk(j["link"])}</td></tr>')
            P.append('</table></div>')

    P.append(f'<footer>{esc(o.footer) if o.footer else ""}'
             f'<div>评分为启发式规则，用于稳定对比前后变化，不代表任何 AI 平台的官方算法。</div>'
             + ('' if o.white_label else '<div>Generated with GEO Anything · github.com/skylarzzzz/geo-anything</div>')
             + '</footer></div></body></html>')
    return "".join(P)


# ---------------------------------------------------------------- PDF（可选）

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


def register_cjk_font(path: str, pdfmetrics) -> str:
    """嵌入 TrueType 轮廓的中文字体；reportlab 不支持 CFF 轮廓（如 Noto CJK 的 .otf）。"""
    from reportlab.pdfbase.ttfonts import TTFont
    for cand in ([path] if path else []) + FONT_CANDIDATES:
        if cand and os.path.exists(cand):
            try:
                pdfmetrics.registerFont(TTFont("GeoCJK", cand, subfontIndex=0) if cand.lower().endswith(".ttc")
                                        else TTFont("GeoCJK", cand))
                return "GeoCJK"
            except Exception:
                continue
    return ""


def build_pdf(audit: dict | None, monitor: dict | None, o, path: str) -> bool:
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError:
        print("未安装 reportlab，跳过 PDF。可运行 pip install reportlab，或用浏览器打开 HTML 后「打印 → 存储为 PDF」。",
              file=sys.stderr)
        return False
    F = register_cjk_font(o.font, pdfmetrics)
    if not F:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        F = "STSong-Light"
        print("提示：未找到可嵌入的中文 TrueType 字体，PDF 使用内置字体，部分阅读器可能显示不全；"
              "可用 --font 指定 .ttf/.ttc 文件。", file=sys.stderr)
    brand = HexColor(o.color)
    grey = HexColor("#6b665e")
    track = HexColor("#efebe4")
    W, H = A4
    cv = canvas.Canvas(path, pagesize=A4)
    y = H - 50

    def newpage_if(need):
        nonlocal y
        if y - need < 50:
            cv.showPage()
            y = H - 50

    def text(s, size=10, color=None, x=50):
        nonlocal y
        cv.setFont(F, size)
        cv.setFillColor(color or HexColor("#1f1d1a"))
        # 简单按字符数换行
        per = int((W - x - 50) / (size * 0.95))
        s = str(s)
        for i in range(0, max(len(s), 1), per):
            newpage_if(size + 6)
            cv.drawString(x, y, s[i:i + per])
            y -= size + 5

    def bar(label, value, full, unit=""):
        nonlocal y
        newpage_if(22)
        cv.setFont(F, 9)
        cv.setFillColor(HexColor("#1f1d1a"))
        cv.drawString(50, y, label)
        cv.setFillColor(track)
        cv.roundRect(170, y - 2, 260, 10, 5, fill=1, stroke=0)
        pct = 0 if not full else max(0, min(1, value / full))
        if pct:
            cv.setFillColor(brand)
            cv.roundRect(170, y - 2, 260 * pct, 10, 5, fill=1, stroke=0)
        cv.setFillColor(grey)
        cv.drawString(440, y, f"{value:.0f}%" if unit == "%" else f"{value:g}/{full:g}")
        y -= 20

    if o.logo and not o.logo.startswith(("http", "data:")) and os.path.exists(o.logo):
        try:
            cv.drawImage(o.logo, 50, y - 22, height=28, width=90, preserveAspectRatio=True, mask="auto")
            cv.setFont(F, 12)
            cv.drawString(150, y - 12, o.brand)
        except Exception:
            text(o.brand, 12)
    else:
        text(o.brand, 12, brand)
    cv.setStrokeColor(brand)
    cv.setLineWidth(2)
    cv.line(50, y - 16, W - 50, y - 16)
    y -= 40
    text("AI 搜索可见度（GEO）报告", 18)
    text(f"日期：{date.today().isoformat()}" + (f"　客户：{o.client}" if o.client else ""), 9, grey)
    if audit:
        text(f"对象：{audit.get('title') or audit.get('source')}", 9, grey)
        y -= 8
        sc = audit.get("score", 0)
        # 仪表盘
        newpage_if(120)
        cx, cy, r = 120, y - 70, 55
        cv.setLineWidth(12)
        cv.setStrokeColor(track)
        cv.arc(cx - r, cy - r, cx + r, cy + r, 0, 180)
        if sc > 0:
            cv.setStrokeColor(brand)
            cv.arc(cx - r, cy - r, cx + r, cy + r, 180 - 180 * min(sc, 100) / 100, 180 * min(sc, 100) / 100)
        cv.setFont(F, 26)
        cv.setFillColor(HexColor("#1f1d1a"))
        cv.drawCentredString(cx, cy - 4, f"{sc:.0f}")
        cv.setFont(F, 10)
        cv.setFillColor(grey)
        cv.drawCentredString(cx, cy - 20, f"/100 · {grade(sc)}")
        y0 = y
        y = y0 - 20
        for k, v in sorted(audit.get("dims", {}).items()):
            cv.setFont(F, 9)
            label = f"{k} {v['name']}"
            pct = v["score"] / v["full"] if v["full"] else 0
            cv.setFillColor(HexColor("#1f1d1a"))
            cv.drawString(230, y, label)
            cv.setFillColor(track)
            cv.roundRect(320, y - 2, 170, 10, 5, fill=1, stroke=0)
            if pct:
                cv.setFillColor(brand)
                cv.roundRect(320, y - 2, 170 * pct, 10, 5, fill=1, stroke=0)
            cv.setFillColor(grey)
            cv.drawString(498, y, f"{v['score']:g}/{v['full']}")
            y -= 20
        y = min(y, y0 - 140)
        text("优先行动", 13, brand)
        gaps = [c for c in audit.get("checks", []) if c["got"] < c["full"] and c.get("fix")]
        gaps.sort(key=lambda c: (-(c["full"] - c["got"]) / max(c.get("minutes", 15), 1)))
        for i, c in enumerate(gaps[:6], 1):
            text(f"{i}. {c['name']}：{c['fix']}（约 {c.get('minutes', 15)} 分钟）", 9)
        y -= 6
        text("检查明细", 13, brand)
        for c in audit.get("checks", []):
            st = "不适用" if c["full"] == 0 else f"{c['got']:g}/{c['full']:g}"
            text(f"[{c['dim']}] {c['name']}　{st}　{c['detail']}", 8)
    if monitor:
        y -= 8
        text("AI 平台可见度", 13, brand)
        for p, s in monitor.get("summary", {}).items():
            bar(f"{PLAT_NAMES.get(p, p)}·{s['mode']}", s["visibility"], 100, "%")
    y -= 10
    if o.footer:
        text(o.footer, 8, grey)
    text("评分为启发式规则，用于对比前后变化，不代表 AI 平台官方算法。", 7, grey)
    if not o.white_label:
        text("Generated with GEO Anything · github.com/skylarzzzz/geo-anything", 7, grey)
    cv.save()
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 报告生成器")
    ap.add_argument("--audit", help="geo_check.py --json 的输出")
    ap.add_argument("--monitor", help="geo_monitor.py 输出的 JSON")
    ap.add_argument("--out", default="geo-report.html", help="HTML 输出路径")
    ap.add_argument("--pdf", help="PDF 输出路径（需要 reportlab）")
    ap.add_argument("--brand", default="GEO Anything", help="白标：你的品牌/工作室名称")
    ap.add_argument("--color", default="#E8590C", help="白标：品牌主色，如 #E8590C")
    ap.add_argument("--logo", default="", help="白标：logo 图片路径或链接")
    ap.add_argument("--client", default="", help="客户名称")
    ap.add_argument("--footer", default="", help="页脚文字，如联系方式")
    ap.add_argument("--white-label", action="store_true", help="去掉 GEO Anything 署名")
    ap.add_argument("--font", default="", help="PDF 使用的中文字体文件（.ttf/.ttc，TrueType 轮廓）")
    o = ap.parse_args(argv)
    if not o.audit and not o.monitor:
        ap.error("至少提供 --audit 或 --monitor 之一")
    audit = json.load(open(o.audit, encoding="utf-8")) if o.audit else None
    monitor = json.load(open(o.monitor, encoding="utf-8")) if o.monitor else None
    with open(o.out, "w", encoding="utf-8") as f:
        f.write(build_html(audit, monitor, o))
    print(f"已生成 {o.out}")
    if o.pdf and build_pdf(audit, monitor, o, o.pdf):
        print(f"已生成 {o.pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
