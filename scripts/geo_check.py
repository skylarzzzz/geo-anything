#!/usr/bin/env python3
"""GEO Anything 体检脚本（零依赖，仅用 Python 标准库，Python 3.9+）

对网站、GitHub 仓库或本地文件做可复现的 GEO 体检，覆盖脚本能客观测量的四个维度：
  A 可引用性(25)  C 实体清晰度(15)  D 技术可读性(15)  E 结构化数据(10)
B 外部提及度(20) 和 F 平台适配(15) 需要联网搜索与人工判断，由 skill 对话部分完成。

用法：
  python3 geo_check.py https://example.com
  python3 geo_check.py https://github.com/owner/repo
  python3 geo_check.py ./index.html            # 本地 HTML
  python3 geo_check.py ./README.md             # 本地 Markdown
  python3 geo_check.py URL --json              # 输出 JSON
  python3 geo_check.py URL --out report.md     # 写入文件
  python3 geo_check.py URL --min-score 70      # 低于 70 分退出码为 1（用于 CI）

环境变量：GITHUB_TOKEN（可选，提高 GitHub API 频率上限）
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser

UA = "geo-anything-check/1.2 (+https://github.com/skylarzzzz/geo-anything)"
TIMEOUT = 20

SEARCH_BOTS = ["OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-SearchBot"]
TRAIN_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Bytespider"]
SCHEMA_TYPES = {"Organization", "Person", "WebSite", "SoftwareApplication", "Product",
                "FAQPage", "HowTo", "Article", "BlogPosting", "LocalBusiness", "Course",
                "WebApplication", "SoftwareSourceCode", "Service"}

DEF_RE = re.compile(r"(是一个|是一款|是一套|是一种|是给|是专为|专门帮|帮助你|帮你|让你|"
                    r"(^|[。！!\s])一(个|款|套)[^，。]{1,24}[：:，,]|"
                    r"\bis an?\b|\bis the\b|\bhelps\b|\blets you\b|\benables\b)", re.I)
QUESTION_RE = re.compile(r"([?？]|^(什么|为什么|怎么|如何|哪|是否|能否|可以|有没有)|"
                         r"(什么|吗|呢|哪些|多少|怎么办|怎么用)$|"
                         r"^(what|why|how|which|can|does|is|do|should|where|when)\b)", re.I)
PLACEHOLDER_RE = re.compile(r"(USERNAME|YOUR[-_]?USER(NAME)?|your-username|<你的[^>]*>|example\.com|"
                            r"\bTODO\b|\bTBD\b|xxx\.github\.io)", re.I)
COMPARE_RE = re.compile(r"(区别|对比|比较|相比|vs\.?|versus|compar|alternative|替代)", re.I)
AUTHOR_RE = re.compile(r"(作者|by\s+[A-Z@]|author|创作者|开发者|maintainer|made by)", re.I)
DATE_RE = re.compile(r"(更新[:：于]?|updated|last updated|发布于|20\d\d[-/.年]\d{1,2})", re.I)
NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|倍|个|种|步|分钟|小时|天|万|k\b|x\b)?", re.I)
CJK_RE = re.compile(r"[一-鿿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")


# ---------------------------------------------------------------- 文档模型

@dataclass
class Doc:
    source: str
    kind: str                      # website | github | file-html | file-md
    ok: bool = True
    error: str = ""
    title: str = ""
    description: str = ""
    canonical: bool = False
    og: bool = False
    author_meta: bool = False
    date_meta: bool = False
    headings: list = field(default_factory=list)
    paragraphs: list = field(default_factory=list)
    has_list: bool = False
    has_table: bool = False
    has_image: bool = False
    jsonld: list = field(default_factory=list)
    text: str = ""
    raw_size: int = 0
    script_count: int = 0
    links: list = field(default_factory=list)      # [(href, text)]
    extra: dict = field(default_factory=dict)


LAST_FETCH = {}


def http_get(url: str, accept: str = "*/*", token: str | None = None) -> tuple[int, str]:
    headers = {"User-Agent": UA, "Accept": accept}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            raw = r.read()
            LAST_FETCH.update({"url": url, "seconds": time.time() - t0, "bytes": len(raw)})
            return r.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, ""


class _HTMLExtractor(HTMLParser):
    BLOCK = {"p", "li", "td", "th", "dd", "blockquote", "section", "article", "div"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.doc_title = ""
        self.meta = {}
        self.links = []
        self.headings = []
        self.paragraphs = []
        self.jsonld_raw = []
        self.has_list = self.has_table = self.has_image = False
        self.script_count = 0
        self._stack = []
        self._buf = []
        self._in_title = False
        self._in_script = None
        self._script_buf = []
        self._heading = None
        self._heading_buf = []
        self.anchors = []
        self._a_href = None
        self._a_buf = []
        self.lazy_imgs = self.imgs = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content") or ""
        elif tag == "link":
            self.links.append(((a.get("rel") or "").lower(), a.get("href") or ""))
        elif tag == "script":
            self.script_count += 1
            self._in_script = (a.get("type") or "").lower()
            self._script_buf = []
        elif tag == "style":
            self._in_script = "style"
        elif tag in ("ul", "ol"):
            self.has_list = True
        elif tag == "table":
            self.has_table = True
        elif tag in ("img", "video", "picture"):
            self.has_image = True
            if tag == "img":
                self.imgs += 1
                if (a.get("loading") or "").lower() == "lazy":
                    self.lazy_imgs += 1
        elif tag == "a":
            self._a_href = a.get("href") or ""
            self._a_buf = []
        elif re.fullmatch(r"h[1-6]", tag):
            self._flush()
            self._heading = tag
            self._heading_buf = []
        elif tag in self.BLOCK or tag == "br":
            self._flush()

    def handle_endtag(self, tag):
        if tag == "a" and self._a_href is not None:
            self.anchors.append((self._a_href, " ".join("".join(self._a_buf).split())))
            self._a_href = None
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style"):
            if self._in_script == "application/ld+json":
                self.jsonld_raw.append("".join(self._script_buf))
            self._in_script = None
        elif self._heading and tag == self._heading:
            h = " ".join("".join(self._heading_buf).split())
            if h:
                self.headings.append((int(tag[1]), h))
            self._heading = None
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._in_script:
            if self._in_script == "application/ld+json":
                self._script_buf.append(data)
            return
        if self._a_href is not None:
            self._a_buf.append(data)
        if self._in_title:
            self.doc_title += data
        elif self._heading:
            self._heading_buf.append(data)
        else:
            self._buf.append(data)

    def _flush(self):
        t = " ".join("".join(self._buf).split())
        if t:
            self.paragraphs.append(t)
        self._buf = []

    def close(self):
        super().close()
        self._flush()


def _collect_types(obj, out: set):
    if isinstance(obj, dict):
        t = obj.get("@type")
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, list):
            out.update(x for x in t if isinstance(x, str))
        for v in obj.values():
            _collect_types(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_types(v, out)


def parse_html(source: str, html: str, kind: str) -> Doc:
    p = _HTMLExtractor()
    p.feed(html)
    p.close()
    d = Doc(source=source, kind=kind)
    d.raw_size = len(html)
    d.script_count = p.script_count
    d.title = " ".join(p.doc_title.split())
    d.description = p.meta.get("description") or p.meta.get("og:description") or ""
    d.og = any(k.startswith("og:") for k in p.meta)
    d.canonical = any("canonical" in rel for rel, _ in p.links)
    d.author_meta = bool(p.meta.get("author") or p.meta.get("article:author"))
    d.date_meta = any(k in p.meta for k in ("article:modified_time", "article:published_time",
                                            "last-modified", "date"))
    d.headings = p.headings
    d.paragraphs = [x for x in p.paragraphs if len(x) > 1]
    d.has_list, d.has_table, d.has_image = p.has_list, p.has_table, p.has_image
    d.links = p.anchors
    d.extra["imgs"], d.extra["lazy_imgs"] = p.imgs, p.lazy_imgs
    for raw in p.jsonld_raw:
        try:
            d.jsonld.append(json.loads(raw))
        except json.JSONDecodeError:
            d.extra["jsonld_invalid"] = d.extra.get("jsonld_invalid", 0) + 1
    d.text = "\n".join(h for _, h in d.headings) + "\n" + "\n".join(d.paragraphs)
    return d


def parse_markdown(source: str, md: str, kind: str) -> Doc:
    d = Doc(source=source, kind=kind)
    d.raw_size = len(md)
    md = re.sub(r"```.*?```", "", md, flags=re.S)          # 去掉代码块
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    if re.search(r"<img\b|!\[[^\]]*\]\([^)]+\)", md, re.I):
        d.has_image = True
    if re.search(r"<table\b", md, re.I):
        d.has_table = True
    if re.search(r"<(ul|ol)\b", md, re.I):
        d.has_list = True
    d.extra["placeholders"] = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(md)})
    d.links = [(m.group(2), m.group(1)) for m in re.finditer(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)[^)]*\)", md)]
    d.links += [(m.group(1), "") for m in re.finditer(r'<a\s[^>]*href="([^"]+)"', md, re.I)]
    # README 里常见的 HTML 写法：转成 Markdown 结构再解析
    md = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>",
                lambda m: "\n\n" + "#" * int(m.group(1)) + " " + re.sub(r"<[^>]+>", "", m.group(2)) + "\n\n",
                md, flags=re.S | re.I)
    md = re.sub(r"</?(p|div|table|tr|section)\b[^>]*>", "\n\n", md, flags=re.I)
    md = re.sub(r"<br\s*/?>", " ", md, flags=re.I)
    buf = []

    def flush():
        t = " ".join(" ".join(buf).split())
        if t:
            d.paragraphs.append(t)
        buf.clear()

    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m:
            flush()
            h = re.sub(r"[*_`]", "", m.group(2)).strip()
            d.headings.append((len(m.group(1)), h))
            if not d.title and len(m.group(1)) == 1:
                d.title = h
            continue
        if not s:
            flush()
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            d.has_list = True
            flush()
            buf.append(re.sub(r"^([-*+]|\d+[.)])\s+", "", s))
            flush()
            continue
        if s.startswith("|") and s.count("|") >= 2:
            d.has_table = True
            flush()
            if not re.fullmatch(r"[|\s:-]+", s):
                d.paragraphs.append(" ".join(s.strip("|").split("|")).strip())
            continue
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"[*_`>]", "", s).strip()
        if s:
            buf.append(s)
    flush()
    d.text = "\n".join(h for _, h in d.headings) + "\n" + "\n".join(d.paragraphs)
    return d


# ---------------------------------------------------------------- 抓取

def load_github(owner: str, repo: str) -> Doc:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    api = f"https://api.github.com/repos/{owner}/{repo}"
    status, body = http_get(api, "application/vnd.github+json", token)
    if status == 401 and token:                      # 无效 token 时退回匿名
        token = None
        status, body = http_get(api, "application/vnd.github+json")
    if status != 200:
        return Doc(source=f"github.com/{owner}/{repo}", kind="github", ok=False,
                   error=f"GitHub API 返回 {status}（仓库不存在、私有或触发频率限制）")
    info = json.loads(body)
    rs, rbody = http_get(api + "/readme", "application/vnd.github+json", token)
    readme = ""
    if rs == 200:
        rj = json.loads(rbody)
        readme = base64.b64decode(rj.get("content", "")).decode("utf-8", errors="replace")
    d = parse_markdown(f"https://github.com/{owner}/{repo}", readme, "github")
    rel_s, _ = http_get(api + "/releases/latest", "application/vnd.github+json", token)
    d.description = info.get("description") or ""
    d.extra.update({
        "stars": info.get("stargazers_count", 0),
        "topics": info.get("topics") or [],
        "homepage": info.get("homepage") or "",
        "license": (info.get("license") or {}).get("spdx_id") or "",
        "pushed_at": info.get("pushed_at") or "",
        "has_release": rel_s == 200,
        "readme_chars": len(readme),
        "owner": owner,
    })
    d.date_meta = bool(info.get("pushed_at"))
    d.author_meta = True                              # 仓库天然有 owner
    return d


def load_website(url: str) -> Doc:
    status, html = http_get(url, "text/html,application/xhtml+xml")
    if status != 200 or not html:
        return Doc(source=url, kind="website", ok=False,
                   error=f"页面返回 {status or '网络错误'}，无法读取（可能被拦截、需要登录或地址错误）")
    d = parse_html(url, html, "website")
    d.extra["fetch_seconds"] = round(LAST_FETCH.get("seconds", 0), 2)
    d.extra["page_kb"] = round(LAST_FETCH.get("bytes", 0) / 1024)
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    rs, robots = http_get(base + "/robots.txt", "text/plain")
    d.extra["robots_found"] = rs == 200 and bool(robots.strip())
    d.extra["robots"] = robots if rs == 200 else ""
    ls, llms = http_get(base + "/llms.txt", "text/plain")
    d.extra["llms_txt"] = ls == 200 and bool(llms.strip()) and "<html" not in llms[:500].lower()
    return d


def load_file(path: str) -> Doc:
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    if path.lower().endswith((".md", ".markdown", ".txt")):
        return parse_markdown(path, content, "file-md")
    d = parse_html(path, content, "file-html")
    folder = os.path.dirname(os.path.abspath(path))
    rp = os.path.join(folder, "robots.txt")
    lp = os.path.join(folder, "llms.txt")
    d.extra["robots_found"] = os.path.exists(rp)
    d.extra["robots"] = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    d.extra["llms_txt"] = os.path.exists(lp)
    return d


def load_repo_dir(path: str) -> Doc:
    """本地仓库目录（例如 CI 里 checkout 出来的代码）。"""
    readme_path = next((os.path.join(path, n) for n in ("README.md", "readme.md", "README.MD", "README")
                        if os.path.exists(os.path.join(path, n))), None)
    readme = open(readme_path, encoding="utf-8", errors="replace").read() if readme_path else ""
    d = parse_markdown(os.path.abspath(path), readme, "github")
    lic = any(os.path.exists(os.path.join(path, n)) for n in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    meta = {}
    mp = os.path.join(path, ".github", "geo.json")       # 可选：手动填写 About / topics 供本地检查
    if os.path.exists(mp):
        try:
            meta = json.load(open(mp, encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    d.description = meta.get("description", "")
    d.extra.update({
        "local": True,
        "topics": meta.get("topics", []),
        "homepage": meta.get("homepage", ""),
        "license": "LICENSE" if lic else "",
        "has_release": bool(meta.get("has_release")),
        "readme_chars": len(readme),
        "has_meta": bool(meta),
    })
    d.author_meta = bool(meta.get("author"))
    return d


def load(target: str) -> Doc:
    if os.path.isdir(target):
        return load_repo_dir(target)
    if os.path.exists(target):
        return load_file(target)
    if not re.match(r"^https?://", target):
        if target.startswith(("/", ".", "~")):
            return Doc(source=target, kind="file", ok=False, error="找不到这个本地文件或目录")
        target = "https://" + target
    m = re.match(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)", target)
    if m:
        return load_github(m.group(1), m.group(2).removesuffix(".git"))
    return load_website(target)


# ---------------------------------------------------------------- 性能（PageSpeed Insights）

def pagespeed(url: str) -> dict:
    """调用 Google PageSpeed Insights（免费，PSI_API_KEY 可选），返回移动端 Core Web Vitals。"""
    q = {"url": url, "strategy": "mobile", "category": "performance"}
    if os.environ.get("PSI_API_KEY"):
        q["key"] = os.environ["PSI_API_KEY"]
    api = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + urllib.parse.urlencode(q)
    global TIMEOUT
    old, TIMEOUT = TIMEOUT, 90
    status, body = http_get(api, "application/json")
    TIMEOUT = old
    if status != 200 or not body:
        return {"ok": False, "error": f"PageSpeed Insights 返回 {status or '网络错误'}"}
    data = json.loads(body)
    out = {"ok": True, "source": "field"}
    m = (data.get("loadingExperience") or {}).get("metrics") or {}
    if "LARGEST_CONTENTFUL_PAINT_MS" in m:
        out["lcp_ms"] = m["LARGEST_CONTENTFUL_PAINT_MS"].get("percentile")
        out["cls"] = (m.get("CUMULATIVE_LAYOUT_SHIFT_SCORE") or {}).get("percentile", 0) / 100
        out["inp_ms"] = (m.get("INTERACTION_TO_NEXT_PAINT") or {}).get("percentile")
    else:                                   # 没有真实用户数据时用实验室数据
        au = (data.get("lighthouseResult") or {}).get("audits") or {}
        out["source"] = "lab"
        out["lcp_ms"] = (au.get("largest-contentful-paint") or {}).get("numericValue")
        out["cls"] = (au.get("cumulative-layout-shift") or {}).get("numericValue")
        out["tbt_ms"] = (au.get("total-blocking-time") or {}).get("numericValue")
    perf = ((data.get("lighthouseResult") or {}).get("categories") or {}).get("performance") or {}
    if perf.get("score") is not None:
        out["perf_score"] = round(perf["score"] * 100)
    return out


# ---------------------------------------------------------------- robots 解析

def robots_allows(robots: str, bot: str) -> bool | None:
    """返回该爬虫是否可抓取根路径；None 表示没有 robots.txt（默认允许）。"""
    if not robots:
        return None
    groups, agents, rules, last_was_agent = [], [], [], False
    for line in robots.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not last_was_agent and agents:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(v.lower())
            last_was_agent = True
        elif k in ("allow", "disallow"):
            rules.append((k, v))
            last_was_agent = False
    if agents:
        groups.append((agents, rules))
    chosen = None
    for ags, rls in groups:
        if bot.lower() in ags:
            chosen = rls
            break
    if chosen is None:
        for ags, rls in groups:
            if "*" in ags:
                chosen = rls
                break
    if chosen is None:
        return True
    best_len, allowed = -1, True
    for k, path in chosen:
        if path == "" and k == "disallow":
            continue
        if "/".startswith(path) or path == "/":
            if len(path) > best_len or (len(path) == best_len and k == "allow"):
                best_len, allowed = len(path), (k == "allow")
    return allowed


# ---------------------------------------------------------------- 评分

@dataclass
class Check:
    dim: str
    name: str
    got: float
    full: float
    detail: str
    fix: str = ""
    minutes: int = 15


def text_len(s: str) -> int:
    """中文按字计，英文按词计 × 2 折算成可比较的长度。"""
    return len(CJK_RE.findall(s)) + 2 * len(LATIN_WORD_RE.findall(s))


EXPERIENCE_RE = re.compile(r"(我(们)?(用|测|试|做|实测|亲测)|实测|亲测|案例|实践|case study|we (tested|built|used)|"
                           r"in our (test|experience)|hands-on)", re.I)
ABOUT_RE = re.compile(r"(关于|联系|about|contact|作者介绍|团队)", re.I)


def external_links(d: Doc) -> list:
    host = urllib.parse.urlparse(d.source).netloc if d.source.startswith("http") else ""
    out = []
    for href, _ in d.links:
        if href.startswith("http"):
            h = urllib.parse.urlparse(href).netloc
            if h and h != host and not h.endswith("shields.io"):
                out.append(href)
    return out


def score(d: Doc, psi: dict | None = None) -> list[Check]:
    c: list[Check] = []
    paras = [p for p in d.paragraphs if text_len(p) >= 8]
    first = paras[0] if paras else ""
    definition = bool(DEF_RE.search(d.description or "")) or any(DEF_RE.search(p) for p in paras[:3])
    total_len = max(text_len(d.text), 1)
    numbers = len(NUM_RE.findall(d.text))
    num_density = numbers / total_len * 1000
    q_heads = [h for _, h in d.headings if QUESTION_RE.search(h)]
    blocks = [p for p in paras if 80 <= text_len(p) <= 450]

    # ---- A 可引用性 (25)
    c.append(Check("A", "首段直接给结论/定义", 6 if (first and DEF_RE.search(first)) else (3 if definition else 0), 6,
                   f"首段：{first[:60]}{'…' if len(first) > 60 else ''}" if first else "未找到正文段落",
                   "把第一段改成「<名称> 是一个给 <谁> 用的 <品类>，用来 <解决什么>。」", 10))
    c.append(Check("A", "可独立摘录的答案段", min(6, len(blocks) * 2), 6,
                   f"中等长度、可单独成段的段落 {len(blocks)} 个（建议 ≥3）",
                   "补 3 段以上各自回答一个问题、开头复述主语的段落（中文约 200–350 字）", 30))
    c.append(Check("A", "事实密度（数字/数据）", 5 if num_density >= 6 else (3 if num_density >= 2 else 0), 5,
                   f"每千字约 {num_density:.1f} 个数字",
                   "加入真实的数字：数量、步骤数、耗时、版本、对比结果（只写真实数据）", 20))
    c.append(Check("A", "问题式小标题", 4 if len(q_heads) >= 2 else (2 if q_heads else 0), 4,
                   f"问题式标题 {len(q_heads)} 个：{'；'.join(q_heads[:3])}",
                   "把小标题改成用户会问的问题，如「它和 XX 有什么区别？」", 10))
    c.append(Check("A", "列表或表格", (2 if d.has_list else 0) + (2 if d.has_table else 0), 4,
                   f"列表：{'有' if d.has_list else '无'}；表格：{'有' if d.has_table else '无'}",
                   "步骤改成编号列表，对比改成表格", 10))

    # ---- C 实体清晰度 (15)
    c.append(Check("C", "统一的一句话定义", 5 if definition else 0, 5,
                   "找到定义句" if definition else "未找到「X 是…」类定义句",
                   "写一句定义，并在所有平台保持一致", 10))
    author = d.author_meta or bool(AUTHOR_RE.search(d.text))
    c.append(Check("C", "作者/主体信息", 4 if author else 0, 4,
                   "有作者信号" if author else "未发现作者或主体信息",
                   "在文首或文末写明作者与主页链接", 5))
    dated = d.date_meta or bool(DATE_RE.search(d.text))
    c.append(Check("C", "更新时间", 3 if dated else 0, 3,
                   "有日期信号" if dated else "未发现更新日期",
                   "加上「更新：YYYY-MM-DD」", 5))
    compare = bool(COMPARE_RE.search(d.text))
    c.append(Check("C", "与同类的区别", 3 if compare else 0, 3,
                   "有对比内容" if compare else "未发现与同类的对比",
                   "加一段或一张表说明与 2–3 个同类的区别", 20))

    # ---- C 中的 E-E-A-T（经验、专业、权威、可信）信号
    ext = external_links(d)
    c.append(Check("C", "E-E-A-T：引用外部来源", 3 if len(ext) >= 3 else (1 if ext else 0), 3,
                   f"外链 {len(ext)} 个", "为关键说法链接到原始来源（论文、官方文档、数据出处）", 15))
    exp = bool(EXPERIENCE_RE.search(d.text))
    c.append(Check("C", "E-E-A-T：一手经验/案例", 3 if exp else 0, 3,
                   "有实测或案例表述" if exp else "没有一手经验、实测或案例",
                   "加一段真实使用过程或案例：做了什么、结果如何", 20))
    about = any(ABOUT_RE.search(t or "") or ABOUT_RE.search(h or "") for h, t in d.links) or \
        any(ABOUT_RE.search(h) for _, h in d.headings)
    c.append(Check("C", "E-E-A-T：关于/联系方式", 2 if about else 0, 2,
                   "有关于或联系入口" if about else "没有关于/联系入口",
                   "加「关于作者」或「联系」入口，说明背景与联系方式", 10))

    # ---- D 技术可读性 (15) / E 结构化数据 (10)
    if d.kind == "github":
        x = d.extra
        rc = x.get("readme_chars", 0)
        c.append(Check("D", "README 内容充足", 5 if rc >= 1500 else (2 if rc >= 400 else 0), 5,
                       f"README 约 {rc} 字符", "README 至少写清定义、上手、功能、FAQ", 30))
        c.append(Check("D", "效果图/GIF", 3 if d.has_image else 0, 3,
                       "有图片" if d.has_image else "README 没有图片", "加一张效果截图或 GIF", 15))
        quick = any(re.search(r"(上手|安装|快速|开始|install|quick ?start|getting started|usage|用法|怎么用)", h, re.I)
                    for _, h in d.headings)
        c.append(Check("D", "上手/安装说明", 3 if quick else 0, 3,
                       "有上手章节" if quick else "没有上手/安装章节", "加「30 秒上手」章节", 10))
        c.append(Check("D", "已发布 Release", 2 if x.get("has_release") else 0, 2,
                       "有 Release" if x.get("has_release") else "没有 Release", "发布 v1.0 Release 并写更新说明", 5))
        bilingual = len(CJK_RE.findall(d.text)) > 50 and len(LATIN_WORD_RE.findall(d.text)) > 80
        c.append(Check("D", "中英双语", 2 if bilingual else 0, 2,
                       "中英文都有" if bilingual else "只有单一语言", "首段加一句英文定义，覆盖海外 AI", 5))
        ph = x.get("placeholders", [])
        c.append(Check("D", "没有未替换的占位符", 0 if ph else 2, 2,
                       f"发现占位内容：{', '.join(ph[:5])}" if ph else "未发现占位链接",
                       "把 USERNAME 等占位链接替换成真实地址，否则 AI 引用时会给出无效链接", 5))
        remote_meta = not x.get("local") or x.get("has_meta")
        if remote_meta:
            desc = bool(d.description)
            c.append(Check("E", "About 描述", 4 if desc else 0, 4,
                           f"About：{d.description[:60]}" if desc else "About 为空",
                           "About 写「是什么 + 给谁 + 关键词」，≤120 字符", 5))
            nt = len(x.get("topics", []))
            c.append(Check("E", "Topics 标签", 3 if nt >= 5 else (1 if nt else 0), 3,
                           f"{nt} 个：{', '.join(x.get('topics', [])[:8])}", "加 6–12 个 topics（品类词 + 场景词）", 5))
            c.append(Check("E", "主页链接与开源协议", (1.5 if x.get("homepage") else 0) + (1.5 if x.get("license") else 0), 3,
                           f"主页：{x.get('homepage') or '无'}；协议：{x.get('license') or '无'}",
                           "在 About 填主页链接，并添加 LICENSE", 5))
        else:
            c.append(Check("E", "About / Topics（本地无法读取）", 0, 0,
                           "本地目录读不到 GitHub 的 About 与 topics：用网址体检，或在 .github/geo.json 中填写后再查",
                           "", 0))
    else:
        tl = text_len(d.text)
        heavy_js = d.script_count >= 5 and tl < 300
        c.append(Check("D", "无需 JS 即可读到正文", 5 if tl >= 500 else (2 if tl >= 200 else 0), 5,
                       f"抓到可读正文约 {tl} 字（脚本 {d.script_count} 个）" + ("，疑似纯前端渲染" if heavy_js else ""),
                       "把核心介绍、FAQ 直接写进 HTML，或启用预渲染/静态导出", 60))
        robots = d.extra.get("robots", "")
        blocked = [b for b in SEARCH_BOTS if robots_allows(robots, b) is False]
        c.append(Check("D", "AI 搜索爬虫放行", 4 if not blocked else (2 if len(blocked) < len(SEARCH_BOTS) else 0), 4,
                       ("robots.txt 未找到（默认允许）" if not d.extra.get("robots_found") else
                        ("搜索类爬虫均已放行" if not blocked else f"被拦截：{', '.join(blocked)}")),
                       "在 robots.txt 放行 OAI-SearchBot、ChatGPT-User、PerplexityBot、Claude-SearchBot", 10))
        c.append(Check("D", "llms.txt", 2 if d.extra.get("llms_txt") else 0, 2,
                       "已有 llms.txt" if d.extra.get("llms_txt") else "没有 llms.txt",
                       "按 templates/llms.txt 生成并放到站点根目录", 15))
        c.append(Check("D", "标题与描述", (1 if d.title else 0) + (1 if d.description else 0), 2,
                       f"title：{d.title[:40] or '无'}；description：{'有' if d.description else '无'}",
                       "补全 <title> 与 meta description（含定义句）", 5))
        c.append(Check("D", "canonical 与 Open Graph", (1 if d.canonical else 0) + (1 if d.og else 0), 2,
                       f"canonical：{'有' if d.canonical else '无'}；OG：{'有' if d.og else '无'}",
                       "加 canonical 链接和 og:title / og:description / og:image", 10))
        if d.kind == "website":
            sec, kb = d.extra.get("fetch_seconds", 0), d.extra.get("page_kb", 0)
            c.append(Check("D", "响应速度与体积", (1 if sec <= 2 else 0) + (1 if kb <= 1500 else 0), 2,
                           f"HTML 下载 {sec}s，{kb} KB（本次网络条件下）",
                           "压缩 HTML、减少内联脚本，确保 2 秒内返回", 30))
        imgs, lazy = d.extra.get("imgs", 0), d.extra.get("lazy_imgs", 0)
        if imgs >= 4:
            c.append(Check("D", "图片懒加载", 1 if lazy >= imgs // 2 else 0, 1,
                           f"{imgs} 张图片，{lazy} 张懒加载", "非首屏图片加 loading=\"lazy\"", 10))
        if psi is not None:
            if psi.get("ok"):
                lcp, cls = psi.get("lcp_ms"), psi.get("cls")
                good = (1.5 if lcp is not None and lcp <= 2500 else 0) + (1.5 if cls is not None and cls <= 0.1 else 0)
                inp = psi.get("inp_ms")
                detail = (f"移动端 LCP {lcp/1000 if lcp else '?'}s，CLS {round(cls, 3) if cls is not None else '?'}"
                          + (f"，INP {inp}ms" if inp else "")
                          + (f"，性能分 {psi['perf_score']}" if "perf_score" in psi else "")
                          + f"（{'真实用户数据' if psi['source'] == 'field' else '实验室数据'}）")
                c.append(Check("D", "Core Web Vitals", good, 3, detail,
                               "优化首屏最大元素（压缩主图、预加载字体）、给图片和广告位预留尺寸", 60))
            else:
                c.append(Check("D", "Core Web Vitals", 0, 0, psi.get("error", "未取得数据"), "", 0))
        types: set = set()
        _collect_types(d.jsonld, types)
        relevant = types & SCHEMA_TYPES
        c.append(Check("E", "存在 JSON-LD", 4 if d.jsonld else 0, 4,
                       f"{len(d.jsonld)} 段" + (f"（另有 {d.extra['jsonld_invalid']} 段格式错误）" if d.extra.get("jsonld_invalid") else ""),
                       "按 templates/schema 添加 JSON-LD", 20))
        c.append(Check("E", "类型匹配对象", 3 if relevant else 0, 3,
                       f"类型：{', '.join(sorted(types)) or '无'}",
                       "至少包含 WebSite / Organization / Person / SoftwareApplication / Product 之一", 10))
        faq = bool(types & {"FAQPage", "HowTo"})
        c.append(Check("E", "FAQPage / HowTo", 3 if faq else 0, 3,
                       "有" if faq else "没有问答类结构化数据", "把 FAQ 区块同步写成 FAQPage JSON-LD", 15))
    return c


DIM_NAMES = {"A": "可引用性", "C": "实体清晰度", "D": "技术可读性", "E": "结构化数据"}
DIM_FULL = {"A": 25, "C": 15, "D": 15, "E": 10}


def summarize(checks: list[Check]) -> dict:
    dims = {}
    for k in DIM_FULL:
        got = sum(x.got for x in checks if x.dim == k)
        full = sum(x.full for x in checks if x.dim == k)
        if full == 0:            # 该维度在当前对象上无法测量，不计入
            continue
        dims[k] = {"name": DIM_NAMES[k], "score": round(got / full * DIM_FULL[k], 1), "full": DIM_FULL[k]}
    measured = sum(v["score"] for v in dims.values())
    measured_full = sum(v["full"] for v in dims.values()) or 1
    return {"dims": dims, "measured": round(measured, 1), "measured_full": measured_full,
            "score": round(measured / measured_full * 100)}


def grade(s: int) -> str:
    return "容易被引用" if s >= 80 else "有机会但有缺口" if s >= 60 else "基本不可见" if s >= 40 else "先修基础问题"


def quick_wins(checks: list[Check], n: int = 5) -> list[Check]:
    gaps = [x for x in checks if x.got < x.full and x.fix]
    gaps.sort(key=lambda x: (-(x.full - x.got) / max(x.minutes, 1), x.minutes))
    return gaps[:n]


def render_md(d: Doc, checks: list[Check], s: dict) -> str:
    L = [f"# GEO 体检报告：{d.title or d.source}", "",
         f"对象：{d.source}  ｜ 类型：{d.kind}  ｜ 日期：{date.today().isoformat()}", ""]
    if d.kind == "github" and not d.extra.get("local"):
        L.append(f"Stars：{d.extra.get('stars', 0)}  ｜ 最近推送：{d.extra.get('pushed_at', '')[:10]}")
        L.append("")
    L += [f"## 结论", "",
          f"脚本可测部分得分 **{s['score']}/100**（{grade(s['score'])}），"
          f"即可测维度（{'/'.join(s['dims'])}）合计 {s['measured']}/{s['measured_full']}。",
          "B 外部提及度、F 平台适配需联网搜索和人工判断，请在对话中用 `/geo 体检` 补全。", "",
          "| 维度 | 得分 | 满分 |", "|---|---|---|"]
    for k, v in s["dims"].items():
        L.append(f"| {k} {v['name']} | {v['score']} | {v['full']} |")
    L += ["", "## 快赢清单", ""]
    for i, x in enumerate(quick_wins(checks), 1):
        L.append(f"{i}. **{x.name}**：{x.fix}（约 {x.minutes} 分钟，可得 {x.full - x.got:g} 分）")
    L += ["", "## 明细", "", "| 维度 | 检查项 | 得分 | 说明 |", "|---|---|---|---|"]
    for x in checks:
        L.append(f"| {x.dim} | {x.name} | {x.got:g}/{x.full:g} | {x.detail.replace('|', '/')} |")
    L += ["", "> 以上为启发式规则（经验法则），用于稳定对比前后变化，不代表任何 AI 平台的官方算法。"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GEO Anything 体检脚本")
    ap.add_argument("target", help="网址、GitHub 仓库地址或本地文件路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--out", help="写入文件路径")
    ap.add_argument("--min-score", type=int, default=0, help="低于该分数时退出码为 1")
    ap.add_argument("--psi", action="store_true", help="调用 PageSpeed Insights 获取 Core Web Vitals（仅网站）")
    a = ap.parse_args(argv)

    d = load(a.target)
    if not d.ok:
        print(f"无法体检：{d.error}", file=sys.stderr)
        return 2
    psi = pagespeed(d.source) if (a.psi and d.kind == "website") else None
    checks = score(d, psi)
    s = summarize(checks)
    if a.json:
        out = json.dumps({"source": d.source, "kind": d.kind, "title": d.title, "date": date.today().isoformat(),
                          **s, "checks": [x.__dict__ for x in checks],
                          "quick_wins": [x.name for x in quick_wins(checks)]},
                         ensure_ascii=False, indent=2)
    else:
        out = render_md(d, checks, s)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"已写入 {a.out}，得分 {s['score']}/100")
    else:
        print(out)
    if a.min_score and s["score"] < a.min_score:
        print(f"得分 {s['score']} 低于阈值 {a.min_score}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
