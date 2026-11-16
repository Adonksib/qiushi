#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
求是网《求是》杂志抓取器

流程：年份索引页 -> 各期目录页 -> 每篇文章页 -> 结构化 JSON

用法：
    python scripts/scrape.py            # 增量：只抓没有的期次
    python scripts/scrape.py --force    # 全量重抓
    python scripts/scrape.py --issue 22 # 只抓第 22 期
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

BASE = "https://www.qstheory.cn"
TOC_INDEX = BASE + "/qs/mulu.htm"
YEAR = 2026

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
ISSUE_DIR = os.path.join(DATA_DIR, "issues")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CST = timezone(timedelta(hours=8))

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
)

# 需要从目录里剔除的非文章链接
SKIP_TITLE = re.compile(r"网站声明|理论资源导航|^$")

# 栏目归类规则：(正则, 栏目名)
CATEGORY_RULES = [
    (r"党员来信", "党员来信"),
    (r"党刊精选", "党刊精选"),
    (r"^统计图表", "统计图表"),
    (r"^深度调研", "深度调研"),
    (r"^文化中国", "文化中国"),
    (r"^学习问答", "学习问答"),
    (r"^关注", "专题·关注"),
    (r"^本期导读", "本期导读"),
    (r"^社论", "社论"),
    (r"本刊评论员", "本刊评论员"),
    (r"本刊编辑部", "本刊编辑部"),
    (r"求是网评论员", "评论"),
]


def log(*a):
    print(*a, flush=True)


def get(url: str, tries: int = 4) -> str:
    """带重试的 GET，返回解码后的 HTML 文本。"""
    last = None
    for i in range(tries):
        try:
            r = _session.get(url, timeout=40)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(1.5 * (i + 1) + random.random())
    raise RuntimeError(f"抓取失败 {url}: {last}")


def clean(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def find_year_index() -> str:
    """从在线读刊目录页找到「2026年」的索引页地址。"""
    soup = BeautifulSoup(get(TOC_INDEX), "html.parser")
    for a in soup.find_all("a"):
        if a.get_text(strip=True) == f"{YEAR}年":
            return requests.compat.urljoin(BASE + "/qs/", a["href"])
    raise RuntimeError("未找到年份索引页")


def list_issue_pages(year_url: str) -> list[tuple[int, str]]:
    """年份索引页 -> [(期号, 目录页URL), ...]"""
    soup = BeautifulSoup(get(year_url), "html.parser")
    out: dict[int, str] = {}
    for a in soup.find_all("a"):
        t = a.get_text(strip=True)
        m = re.search(rf"{YEAR}年第(\d+)期", t)
        if m:
            out[int(m.group(1))] = requests.compat.urljoin(year_url, a["href"])
    return sorted(out.items())


def parse_toc(url: str) -> dict:
    """目录页 -> 期次信息 + 文章链接列表"""
    html = get(url)
    soup = BeautifulSoup(html, "html.parser")

    page_title = soup.title.get_text(strip=True) if soup.title else ""
    m = re.search(rf"{YEAR}年第(\d+)期", page_title)
    issue_no = int(m.group(1)) if m else 0

    # 出版日期：优先取正文里 "来源：《求是》2026/22" 附近的日期
    pub_date = ""
    text_all = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    dm = re.search(r"(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}", text_all)
    if dm:
        pub_date = dm.group(1)

    articles = []
    seen = set()
    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))
        href = requests.compat.urljoin(url, a["href"])
        if SKIP_TITLE.search(title):
            continue
        if not re.search(r"/c\.html$", href):
            continue
        if "/qssyggw/" in href:
            continue
        # 期次目录里的文章链接都落在本期目录所在日期目录下
        if href in seen:
            continue
        seen.add(href)
        articles.append({"title": title, "url": href})

    return {
        "year": YEAR,
        "issue": issue_no,
        "published": pub_date,
        "toc_url": url,
        "articles": articles,
    }


def guess_category(title: str, author: str, body: str, label: str = "") -> str:
    if author and author.startswith("习近平"):
        return "习近平重要文章"
    if label:
        return {"关注人工智能": "专题·关注"}.get(label, label)
    for pat, name in CATEGORY_RULES:
        if re.search(pat, title):
            return name
    head = body[:260]
    if "本刊评论员" in head or "本刊评论员" in title:
        return "本刊评论员"
    if "本刊编辑部" in head:
        return "本刊编辑部"
    return "理论文章"


def parse_article(url: str) -> dict:
    html = get(url)
    soup = BeautifulSoup(html, "html.parser")

    # 标题
    title = ""
    h1 = soup.find("h1")
    if h1 and clean(h1.get_text()):
        title = clean(h1.get_text())
    if not title and soup.title:
        title = clean(soup.title.get_text().split("-")[0])
    title = re.sub(r"[\s※]+$", "", title)
    # 目录页里栏目名会混进标题，如「深度调研│家政服务业…」，拆出来单独记
    label = ""
    lm = re.match(
        r"^(深度调研|文化中国|学习问答|关注人工智能|本期导读|社论|党员来信|党刊精选|求是专访)\s*[│|｜]\s*",
        title,
    )
    if lm:
        label = lm.group(1)
        title = title[lm.end():]

    # 正文容器
    node = soup.find("div", id="detailContent") or soup.find("div", class_="content")
    if node is None:
        node = soup.body

    for bad in node.find_all(["script", "style", "iframe"]):
        bad.decompose()

    paragraphs: list[str] = []
    for p in node.find_all(["p", "div", "h2", "h3", "h4"]):
        t = clean(p.get_text(" ", strip=True))
        if not t:
            continue
        # 过滤页面噪音
        if re.match(r"^(扫描二维码|网站编辑|【网站声明】|责任编辑|分享到)", t):
            continue
        if len(t) <= 1 and not re.search(r"[\u4e00-\u9fa5]", t):
            continue
        paragraphs.append(t)

    # 去重相邻重复（h 标签与 p 嵌套时会出现）
    dedup: list[str] = []
    for t in paragraphs:
        if dedup and dedup[-1] == t:
            continue
        dedup.append(t)
    paragraphs = dedup

    full_text = "\n".join(paragraphs)

    # 作者 / 来源 / 日期：元信息常在正文容器之外，取整页文本头部
    page_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    author = ""
    am = re.search(r"作\s*者[：:]\s*([\u4e00-\u9fa5A-Za-z·\s]{2,20}?)\s*(?:来源|20\d{2}-\d{2}-\d{2}|$)", page_text)
    if am:
        author = clean(am.group(1))
    if not author:
        # 兜底：正文前几段里独立成行的人名
        for t in paragraphs[:4]:
            if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}(?:\s+[\u4e00-\u9fa5]{1,4})?", t):
                author = t
                break
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", page_text[:800])
    date = dm.group(1) if dm else ""

    # 去掉页头元信息段落
    LABELS = {"深度调研", "文化中国", "学习问答", "关注人工智能", "本期导读", "社论", "党员来信", "党刊精选"}
    body_paras = [
        t
        for t in paragraphs
        if not re.match(r"^(作者|来源|发布时间|2026-\d{2}-\d{2})[：:]?", t)
        and re.sub(r"[\s※]+$", "", t) != title
        and t != author
        and t not in LABELS
    ]

    return {
        "title": title,
        "url": url,
        "label": label,
        "author": author,
        "date": date,
        "paragraphs": body_paras,
        "chars": sum(len(t) for t in body_paras),
    }


def scrape_issue(issue_no: int, toc_url: str) -> dict:
    log(f"  · 第 {issue_no} 期 目录")
    toc = parse_toc(toc_url)
    arts = []
    for i, a in enumerate(toc["articles"], 1):
        try:
            art = parse_article(a["url"])
        except Exception as e:  # noqa: BLE001
            log(f"    ! 失败 {a['title'][:20]}: {e}")
            continue
        art["category"] = guess_category(
            art["title"], art["author"], "\n".join(art["paragraphs"]), art.get("label", "")
        )
        arts.append(art)
        log(f"    [{i:02d}/{len(toc['articles'])}] {art['chars']:>5}字  {art['title'][:34]}")
        time.sleep(0.45 + random.random() * 0.35)

    toc["articles"] = arts
    toc["article_count"] = len(arts)
    toc["total_chars"] = sum(a["chars"] for a in arts)
    toc["fetched_at"] = datetime.now(CST).isoformat(timespec="seconds")
    return toc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="全量重抓")
    ap.add_argument("--issue", type=int, default=0, help="只抓指定期号")
    args = ap.parse_args()

    os.makedirs(ISSUE_DIR, exist_ok=True)

    log("→ 读取年份索引")
    year_url = find_year_index()
    pages = list_issue_pages(year_url)
    log(f"  发现 {len(pages)} 期：{pages[0][0]} - {pages[-1][0]}")

    if args.issue:
        pages = [(n, u) for n, u in pages if n == args.issue]

    updated = 0
    for issue_no, toc_url in pages:
        out_path = os.path.join(ISSUE_DIR, f"{YEAR}-{issue_no:02d}.json")
        if os.path.exists(out_path) and not args.force:
            log(f"  = 第 {issue_no} 期已存在，跳过")
            continue
        log(f"→ 抓取第 {issue_no} 期")
        data = scrape_issue(issue_no, toc_url)
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, out_path)
        log(f"  ✓ 第 {issue_no} 期完成：{data['article_count']} 篇 / {data['total_chars']} 字")
        updated += 1

    # 汇总索引
    issues = []
    for fn in sorted(os.listdir(ISSUE_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(ISSUE_DIR, fn), encoding="utf-8") as f:
            d = json.load(f)
        issues.append(
            {
                "issue": d["issue"],
                "published": d.get("published", ""),
                "article_count": d.get("article_count", 0),
                "total_chars": d.get("total_chars", 0),
                "titles": [a["title"] for a in d["articles"]],
            }
        )
    with open(os.path.join(DATA_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "year": YEAR,
                "count": len(issues),
                "latest": max((i["issue"] for i in issues), default=0),
                "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
                "issues": issues,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )

    log(f"\n完成：本次更新 {updated} 期，累计 {len(issues)} 期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
