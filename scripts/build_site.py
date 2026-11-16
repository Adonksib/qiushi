#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 data/ 下的期次数据 + 提炼数据，渲染成静态站点。

    python scripts/build_site.py [--out dist]

产出：
    dist/index.html              首页（全部期次）
    dist/issues/2026-22.html     期次详情（可交互）
    dist/print/2026-22.html      打印版（全文展开，供生成 PDF）
    dist/assets/*                样式与脚本
    dist/pdf/2026-22.pdf         由 build_pdf.py 生成，这里只做占位链接
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CST = timezone(timedelta(hours=8))

CAT_STYLE = {
    "习近平重要文章": "xim",
    "本刊评论员": "ping",
    "本刊编辑部": "ping",
    "社论": "ping",
    "本期导读": "ping",
}

EXAM_LABEL = {"shenlun": ("申论", "shenlun"), "changshi": ("常识·时政", "changshi"), "mianshi": ("面试", "mianshi")}

NAV = [
    ("index.html", "全部期次"),
    ("latest", "最新一期"),
    ("about.html", "使用说明"),
]


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 组件

def topbar(active: str, latest_no: int, prefix: str = "") -> str:
    latest_href = f"{prefix}issues/2026-{latest_no:02d}.html" if latest_no else f"{prefix}index.html"
    items = []
    for href, label in NAV:
        real = latest_href if href == "latest" else prefix + href
        cls = ' class="active"' if label == active else ""
        items.append(f'<a href="{real}"{cls}>{esc(label)}</a>')
    return f"""
<header class="topbar">
  <div class="topbar-in">
    <a class="brand" href="{prefix}index.html">
      <span class="mark">求</span>
      <span class="name">求是·考点</span>
      <span class="sub">2026 全年《求是》要点提炼</span>
    </a>
    <nav class="topnav">{''.join(items)}</nav>
  </div>
</header>"""


def footer(generated_at: str) -> str:
    return f"""
<footer class="footer">
  <div class="footer-in">
    <b>关于本站</b>　本站自动抓取<a href="https://www.qstheory.cn/" target="_blank" rel="noopener">求是网</a>《求是》杂志
    2026 年各期公开内容，提炼要点与考点方向，供公务员考试备考使用。<br>
    文字版权归原作者及求是杂志社所有，本站仅作学习研究之用，不作商业用途；引用请以原刊为准。<br>
    <b>页面更新</b>　{esc(generated_at)}　·　数据每日自动同步，新一期上线后当日入库。
  </div>
</footer>"""


def parse_paragraphs(paras: list[str]) -> str:
    """把段落数组渲染成正文 HTML，识别小标题序号与图片说明。"""
    out = []
    for t in paras:
        t = t.strip()
        if not t:
            continue
        # 图片说明
        if len(t) < 160 and ("摄" in t and ("新华社" in t or "/摄" in t or "记者" in t)):
            out.append(f'<p class="imgph">{esc(t)}</p>')
            continue
        # 中文序号小标题：一 / 二 / 三
        if re.fullmatch(r"[一二三四五六七八九十]{1,3}", t):
            out.append(f'<p class="num">{esc(t)}</p>')
            continue
        if t.startswith("（") and t.endswith("）") and len(t) < 90:
            out.append(f'<p class="plain">{esc(t)}</p>')
            continue
        out.append(f"<p>{esc(t)}</p>")
    return "\n".join(out)


def article_block(i: int, art: dict, open_flag: bool) -> str:
    cat = art.get("category", "理论文章")
    cat_cls = CAT_STYLE.get(cat, "")
    meta_inner = f'<span class="cat {cat_cls}">{esc(cat)}</span>'
    if art.get("author"):
        meta_inner += f"<span>{esc(art['author'])}</span>"
    meta_inner += f'<span>{art.get("chars", 0)} 字</span>'
    body = parse_paragraphs(art.get("paragraphs", []))
    if not body.strip():
        body = '<p class="imgph">本篇为图片/图表内容，请点击文末链接查看求是网原文。</p>'
    open_attr = " open" if open_flag else ""
    return f"""
<details class="art" id="art-{i}"{open_attr}>
  <summary>
    <span class="idx">{i:02d}</span>
    <span class="t">
      <h3>{esc(art['title'])}</h3>
      <span class="m">{meta_inner}</span>
    </span>
    <svg class="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M6 9l6 6 6-6"/></svg>
  </summary>
  <div class="body">{body}</div>
  <div class="foot">
    <span>{esc(art.get('author', '') or '佚名')}</span>
    <a href="{esc(art['url'])}" target="_blank" rel="noopener">求是网原文 ↗</a>
  </div>
</details>"""


def sidenav(issues, current: int, toc: list[dict]) -> str:
    li = []
    for it in sorted(issues, key=lambda x: -x["issue"]):
        cls = ' class="on"' if it["issue"] == current else ""
        li.append(f'<li><a href="2026-{it["issue"]:02d}.html"{cls}><i>{it["issue"]:02d}</i>第 {it["issue"]} 期</a></li>')
    toc_li = "".join(
        f'<li><a href="#art-{i}">{esc(t["title"])[:26]}</a></li>' for i, t in enumerate(toc[:26], 1)
    )
    return f"""
<aside class="sidenav no-print">
  <h4>2026 年各期</h4>
  <ul>{''.join(li)}</ul>
  <h4>本期篇目</h4>
  <ul class="toc">{toc_li}</ul>
</aside>"""


def topic_block(i: int, t: dict, art_lookup: dict) -> str:
    pts = "".join(f"<li>{esc(p)}</li>" for p in t.get("points", []))
    srcs = t.get("sources") or []
    src_html = ""
    if srcs:
        names = "；".join(srcs)
        src_html = f'<div class="src">对应篇目：{esc(names)}</div>'
    return f"""
<div class="topic">
  <h3><span class="n">{i}</span>{esc(t.get('name', ''))}</h3>
  {f'<p class="sum">{esc(t["summary"])}</p>' if t.get("summary") else ''}
  <ul>{pts}</ul>
  {src_html}
</div>"""


def exam_block(e: dict) -> str:
    label, cls = EXAM_LABEL.get(e.get("type", ""), ("考点", ""))
    phrases = "".join(f"<span>{esc(p)}</span>" for p in e.get("phrases", []) or [])
    detail = f'<p><span class="lbl">考点展开</span>{esc(e["detail"])}</p>' if e.get("detail") else ""
    angle = f'<p><span class="lbl">命题角度</span>{esc(e["angle"])}</p>' if e.get("angle") else ""
    phr = f'<div class="phr">{phrases}</div>' if phrases else ""
    return f"""
<div class="exam">
  <div class="exam-top">
    <span class="exam-type {cls}">{esc(label)}</span>
    <span class="exam-topic">{esc(e.get('topic', ''))}</span>
  </div>
  <div class="exam-body">{angle}{detail}{phr}</div>
</div>"""


# ---------------------------------------------------------------- 首页

def build_index(issues_all: list[dict], digests: dict, out_dir: str) -> None:
    latest = max((i["issue"] for i in issues_all), default=0)
    n_art = sum(i.get("article_count", 0) for i in issues_all)
    n_chars = sum(i.get("total_chars", 0) for i in issues_all)
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")

    cards = []
    for it in sorted(issues_all, key=lambda x: -x["issue"]):
        no = it["issue"]
        d = digests.get(no, {})
        theme = d.get("theme") or "本期要点整理中"
        line = d.get("one_line") or ""
        kws = d.get("keywords", [])[:4]
        heat = d.get("heat", 0)
        new = '<span class="tag-new">最新</span>' if no == latest else ""
        kw_html = "".join(f'<span class="tag k">{esc(k)}</span>' for k in kws)
        search_blob = " ".join(
            [theme, line, " ".join(kws), " ".join(it.get("titles", [])[:30]), f"第{no}期 {no}"]
        ).lower()
        heat_html = ""
        if heat:
            heat_html = f'<span class="tag">考点热度 {"●" * heat}{"○" * (5 - heat)}</span>'
        cards.append(f"""
<a class="card" href="issues/2026-{no:02d}.html" data-q="{esc(search_blob)}" data-heat="{heat}">
  <div class="card-top">
    <div class="card-no">{no:02d}<small>期</small></div>
    <div class="card-meta">
      <div class="card-date">{esc(it.get('published') or '')} 出版 {new}</div>
      <h3 class="card-theme">{esc(theme)}</h3>
    </div>
  </div>
  <p class="card-line">{esc(line) or '本期共 ' + str(it.get('article_count',0)) + ' 篇，已全文收录，要点提炼整理中。'}</p>
  <div class="card-tags">{kw_html}{heat_html}</div>
  <div class="card-foot">
    <span>{it.get('article_count', 0)} 篇</span>
    <span>{it.get('total_chars', 0) // 1000} 千字</span>
    <span class="pdf">含 PDF</span>
    <span class="go">阅读 →</span>
  </div>
</a>""")

    # 全年高频考点：按关键词出现期数排序
    freq: dict[str, int] = {}
    for no, dg in digests.items():
        for k in dg.get("keywords", []) or []:
            freq[k] = freq.get(k, 0) + 1
    top = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:14]
    cloud = "".join(
        f'<button class="kchip" data-kw="{esc(k)}">{esc(k)}<i>{c}</i></button>' for k, c in top if c >= 2
    )
    cloud_html = ""
    if cloud:
        cloud_html = f"""
  <section class="cloud no-print">
    <div class="cloud-head"><h2>全年高频考点</h2><span>数字为出现期数，点一下筛选相关期次</span></div>
    <div class="cloud-body">{cloud}</div>
  </section>"""

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>求是·考点｜2026 年《求是》各期要点提炼与考点预测</title>
<meta name="description" content="自动汇总《求是》杂志 2026 年全部期次，逐期提炼核心要点、申论素材与可能出题方向，支持在线阅读与 PDF 下载。公务员考试备考资料站。">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
{topbar("全部期次", latest)}
<main>
  <section class="hero">
    <div class="hero-kicker">QIUSHI · 2026 · EXAM PREP</div>
    <h1>把每一期《求是》<br>读成一份<em>考点清单</em></h1>
    <p class="lede">《求是》是公务员考试最稳定、最权威的命题语料来源。本站自动收录 2026 年全部期次全文，
    逐期提炼核心论述、申论可用表达与大概率出题方向，每期均可导出 PDF 离线精读。</p>
    <div class="stats">
      <div class="stat"><b>{len(issues_all)}</b><span>已收录期数</span></div>
      <div class="stat"><b>{n_art}</b><span>收录文章</span></div>
      <div class="stat"><b>{n_chars // 10000}</b><span>万字全文</span></div>
      <div class="stat"><b>第 {latest} 期</b><span>最新入库</span></div>
    </div>
  </section>

  <div class="toolbar no-print">
    <label class="search">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" type="search" placeholder="搜索主题、关键词或篇名，例如：新质生产力 / 共同富裕 / 全面从严治党">
    </label>
    <div class="chips" id="chips">
      <button class="chip on" data-f="all">全部</button>
      <button class="chip" data-f="hot">重点期</button>
      <button class="chip" data-f="new">近三期</button>
    </div>
  </div>

  {cloud_html}

  <section class="grid" id="grid">
    {''.join(cards)}
  </section>
  <div class="empty" id="empty" style="display:none">没有匹配的期次，换个关键词试试。</div>
</main>
{footer(now)}
<script src="assets/app.js"></script>
</body>
</html>"""
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


# ---------------------------------------------------------------- 期次详情

def issue_pager(issues_all: list[dict], no: int, digests: dict) -> str:
    nos = sorted(i["issue"] for i in issues_all)
    idx = nos.index(no) if no in nos else -1
    prev_no = nos[idx - 1] if idx > 0 else None
    next_no = nos[idx + 1] if 0 <= idx < len(nos) - 1 else None

    def cell(n, direction):
        if not n:
            return '<span></span>'
        theme = (digests.get(n) or {}).get("theme") or f"2026 年第 {n} 期"
        return (
            f'<a href="2026-{n:02d}.html"><span class="dir">{direction}</span>'
            f'<span class="t">第 {n} 期 · {esc(theme)}</span></a>'
        )

    return f'<nav class="pager no-print">{cell(prev_no, "← 上一期")}{cell(next_no, "下一期 →")}</nav>'


def build_issue(
    issue: dict,
    issues_all: list[dict],
    digest: dict | None,
    out_dir: str,
    print_mode: bool,
    all_digests: dict | None = None,
) -> None:
    no = issue["issue"]
    latest = max((i["issue"] for i in issues_all), default=0)
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    arts = issue["articles"]
    d = digest or {}

    title = f"第 {no} 期（{issue.get('published','')}）"
    theme = d.get("theme") or f"2026 年第 {no} 期"
    head_sub = d.get("one_line") or f"本期共 {len(arts)} 篇，全文已收录。"

    # —— 速览
    ov = d.get("overview") or []
    if isinstance(ov, str):
        ov = [ov]
    brief_html = ""
    if ov:
        brief_html = '<section class="sec" id="brief"><div class="sec-head"><h2>本期速览</h2><span class="hint">3 分钟看懂这一期在讲什么</span></div><div class="brief">' + \
            "".join(f"<p>{esc(p)}</p>" for p in ov) + "</div></section>"

    # —— 专题提炼
    topics = d.get("topics") or []
    topics_html = ""
    if topics:
        topics_html = '<section class="sec" id="topics"><div class="sec-head"><h2>重点提炼</h2><span class="hint">按主题聚合，直接背这一栏</span></div>' + \
            "".join(topic_block(i, t, {}) for i, t in enumerate(topics, 1)) + "</section>"

    # —— 考点预测
    exams = d.get("exam") or []
    exam_html = ""
    if exams:
        exam_html = '<section class="sec" id="exam"><div class="sec-head"><h2>大概率出题方向</h2><span class="hint">按题型给角度，不是押题，是准备弹药</span></div><div class="exam-grid">' + \
            "".join(exam_block(e) for e in exams) + "</div></section>"

    # —— 金句
    quotes = d.get("quotes") or []
    quote_html = ""
    if quotes:
        qs = []
        for q in quotes:
            if isinstance(q, str):
                qs.append(f'<div class="quote">{esc(q)}</div>')
            else:
                qs.append(f'<div class="quote">{esc(q.get("text",""))}<span class="use">{esc(q.get("use",""))}</span></div>')
        quote_html = '<section class="sec" id="quotes"><div class="sec-head"><h2>可直接用的金句</h2><span class="hint">申论与面试的现成表达</span></div><div class="quotes">' + "".join(qs) + "</div></section>"

    # —— 全文
    open_first = not print_mode
    art_html = "".join(article_block(i, a, False) for i, a in enumerate(arts, 1))
    pager = "" if print_mode else issue_pager(issues_all, no, all_digests or {})

    body = f"""
<main class="{'print-doc' if print_mode else ''}">
  <div class="wrap">
    <div class="layout">
      {'' if print_mode else sidenav(issues_all, no, arts)}
      <div>
        <div class="article-head">
          <div class="issue-eyebrow">《求是》2026 年第 {no} 期 · {esc(issue.get('published',''))}</div>
          <h1>{esc(theme)}</h1>
          <p class="sub">{esc(head_sub)}</p>
          <div class="head-stats">
            <span>收录 <b>{len(arts)}</b> 篇</span>
            <span>全文 <b>{issue.get('total_chars',0) // 1000}</b> 千字</span>
            {'<span>考点热度 <b>' + '●' * int(d.get('heat', 0)) + '</b></span>' if d.get('heat') else ''}
            <span><a href="../pdf/2026-{no:02d}.pdf" target="_blank">下载本期 PDF ↗</a></span>
          </div>
        </div>

        {brief_html}
        {topics_html}
        {exam_html}
        {quote_html}

        <section class="sec" id="fulltext">
          <div class="sec-head"><h2>本期目录与全文</h2><span class="hint">共 {len(arts)} 篇，点击展开</span></div>
          <div class="tools-row no-print">
            <button class="btn" onclick="document.querySelectorAll('details.art').forEach(d=>d.open=true)">全部展开</button>
            <button class="btn" onclick="document.querySelectorAll('details.art').forEach(d=>d.open=false)">全部收起</button>
            <a class="btn primary" href="../pdf/2026-{no:02d}.pdf" target="_blank">导出本期 PDF</a>
          </div>
          {art_html}
        </section>
        {pager}
      </div>
    </div>
  </div>
</main>"""

    if print_mode:
        page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>《求是》2026 年第 {no} 期 要点与全文</title>
<link rel="stylesheet" href="../assets/style.css">
<style>
  .art > summary {{ cursor: default; }}
  .art[open] .body, .art .body {{ display: block; }}
</style>
</head>
<body class="print-doc">
<div class="wrap">
  <div class="print-page-head">
    <div class="k">《求是》2026 年第 {no} 期 · 备考手册</div>
    <h1>{esc(theme)}</h1>
    <div class="m">{esc(issue.get('published',''))} 出版　·　收录 {len(arts)} 篇 / {issue.get('total_chars',0)} 字　·　求是·考点整理</div>
  </div>
{body_html_only(brief_html, topics_html, exam_html, quote_html, arts, print_mode=True)}
</div>
</body>
</html>"""
    else:
        page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>第 {no} 期 · {esc(theme)}｜求是·考点 2026</title>
<meta name="description" content="{esc(head_sub)}">
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
{topbar(f"第 {no} 期", latest, "../")}
{body}
{footer(now)}
<script>
document.querySelectorAll('.sidenav .toc a').forEach(a=>{{
  a.addEventListener('click',()=>{{
    const el=document.querySelector(a.getAttribute('href'));
    if(el) el.open=true;
  }});
}});
</script>
</body>
</html>"""

    sub = "print" if print_mode else "issues"
    os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    with open(os.path.join(out_dir, sub, f"2026-{no:02d}.html"), "w", encoding="utf-8") as f:
        f.write(page)


def body_html_only(brief, topics, exam, quotes, arts, print_mode=True) -> str:
    """打印版只需要内容块，不要交互外壳。"""
    art_html = "".join(article_block(i, a, True) for i, a in enumerate(arts, 1))
    return f"""
{brief}
{topics}
{exam}
{quotes}
<section class="sec" id="fulltext">
  <div class="sec-head"><h2>本期全文</h2><span class="hint">共 {len(arts)} 篇</span></div>
  {art_html}
</section>"""


# ---------------------------------------------------------------- 说明页

def build_about(issues_all, out_dir, now):
    latest = max((i["issue"] for i in issues_all), default=0)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>使用说明｜求是·考点</title>
<link rel="stylesheet" href="assets/style.css"></head>
<body>
{topbar("使用说明", latest)}
<main class="wrap" style="max-width:820px;padding-top:44px;padding-bottom:90px">
  <div class="article-head">
    <div class="issue-eyebrow">使用说明</div>
    <h1>这站怎么用</h1>
    <p class="sub">不是把杂志搬上网，而是把每一期拆成可背、可引、可预测的备考材料。</p>
  </div>
  <section class="sec">
    <div class="sec-head"><h2>三个层次</h2></div>
    <div class="topic"><h3><span class="n">1</span>本期速览</h3>
      <p class="sum">先用 3 分钟读完这一期的主线：这期在集中讲什么、为什么此时讲、和哪场会议或哪个文件呼应。</p></div>
    <div class="topic"><h3><span class="n">2</span>重点提炼</h3>
      <p class="sum">按主题聚合要点，一条一句，可以直接当笔记背。每条要点后标注了它出自哪篇文章，需要展开时去全文里找。</p></div>
    <div class="topic"><h3><span class="n">3</span>出题方向</h3>
      <p class="sum">分申论、常识时政、面试三类给角度。这不是押题，而是告诉你「如果考这一块，会从哪个口子切」。</p></div>
    <div class="topic"><h3><span class="n">4</span>全文与 PDF</h3>
      <p class="sum">每篇原文都在页面底部，可展开精读；每期都能导出 PDF，打印出来做批注。</p></div>
  </section>
  <section class="sec">
    <div class="sec-head"><h2>更新机制</h2></div>
    <div class="brief"><p>站点由 GitHub Actions 每日定时抓取求是网，新一期上线后当天自动入库、自动重新生成页面与 PDF，无需手动操作。</p></div>
  </section>
  <section class="sec">
    <div class="sec-head"><h2>版权说明</h2></div>
    <div class="brief"><p>全部文字版权归原作者与求是杂志社所有，本站仅作个人学习研究使用，不用于商业用途。引用请以《求是》原刊为准。</p></div>
  </section>
</main>
{footer(now)}</body></html>"""
    with open(os.path.join(out_dir, "about.html"), "w", encoding="utf-8") as f:
        f.write(page)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()

    out_dir = os.path.join(ROOT, args.out)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "pdf"), exist_ok=True)

    # 静态资源
    site_dir = os.path.join(ROOT, "site")
    for fn in os.listdir(os.path.join(site_dir, "assets")):
        shutil.copy2(os.path.join(site_dir, "assets", fn), os.path.join(out_dir, "assets", fn))

    # 数据
    idx = load_json(os.path.join(DATA, "index.json"), {"issues": []})
    issues_all = idx.get("issues", [])

    issues = []
    for fn in sorted(os.listdir(os.path.join(DATA, "issues"))):
        if fn.endswith(".json"):
            issues.append(load_json(os.path.join(DATA, "issues", fn)))

    digests = {}
    ddir = os.path.join(DATA, "digests")
    if os.path.isdir(ddir):
        for fn in os.listdir(ddir):
            if fn.endswith(".json"):
                dg = load_json(os.path.join(ddir, fn))
                if dg and dg.get("issue"):
                    digests[int(dg["issue"])] = dg

    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    build_index(issues_all, digests, out_dir)
    build_about(issues_all, out_dir, now)
    for issue in issues:
        build_issue(issue, issues_all, digests.get(issue["issue"]), out_dir, False, digests)
        build_issue(issue, issues_all, digests.get(issue["issue"]), out_dir, True, digests)

    # 让 GitHub Pages 不跑 Jekyll
    open(os.path.join(out_dir, ".nojekyll"), "w").close()

    # 首页的 app.js 由 site/assets 拷入，这里补一个同名文件若缺失
    print(f"✓ 站点已生成：{out_dir}（{len(issues)} 期，{len(digests)} 期含提炼）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
