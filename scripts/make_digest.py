#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用大模型为某一期生成「重点提炼 / 考点」结构化数据。

    export LLM_API_KEY=sk-xxx          # 必填
    export LLM_BASE_URL=https://api.deepseek.com   # 可选，兼容 OpenAI 协议即可
    export LLM_MODEL=deepseek-chat                 # 可选
    python scripts/make_digest.py --issue 23
    python scripts/make_digest.py --missing       # 只补还没提炼的期

输出：data/digests/2026-NN.json
没有 API Key 时脚本以退出码 0 结束（站点会跳过提炼区，只展示全文）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISSUE_DIR = os.path.join(ROOT, "data", "issues")
DIGEST_DIR = os.path.join(ROOT, "data", "digests")

SYSTEM = """你是资深的公务员考试命题研究者，长期跟踪《求是》杂志与中央文件的话语体系。
你的任务不是写读后感，而是把一期《求是》拆成对备考真正有用的东西：
哪些论述是新的、哪些提法是第一次出现的、哪些内容可能变成申论材料或常识考点。

判断标准（务必遵守）：
1. 只写原文里有的内容，不得编造数据、会议名称、文件名称、领导讲话。
2. 提炼要具体到"论断"层面，不要写"强调了重要性"这类空话。宁可少写，不要注水。
3. 考点判断要落到题型上：申论考什么主题、材料可能怎么用；常识考哪个知识点；面试可能问什么。
4. 语言用规范的机关文风，但要点句要短，适合背诵。"""

USER_TMPL = """下面是《求是》2026 年第 {issue} 期的全部篇目（含正文节选）。

{articles}

请输出一个 JSON 对象（不要 Markdown 代码块，不要任何解释文字），字段如下：

{{
  "issue": {issue},
  "theme": "本期主题，8-16字，两个关键词用 · 连接，如：亚太共同体 · 全面从严治党",
  "one_line": "一句话主线，30-45字，说清这期为什么在这个时间点集中讲这些",
  "overview": ["速览段落1，60-100字", "速览段落2，60-100字", "速览段落3（可选）"],
  "keywords": ["4-6个考点关键词，每个2-8字"],
  "heat": 4,
  "topics": [
    {{
      "name": "专题名，6-14字",
      "summary": "这个专题在回答什么问题，40-70字",
      "points": ["要点1，一句话，25-55字，要含具体论断", "要点2", "要点3", "要点4（可选）"],
      "sources": ["对应的文章标题，原样抄录"]
    }}
  ],
  "exam": [
    {{
      "type": "shenlun",
      "topic": "考点名，6-14字",
      "angle": "命题角度，说明会从哪个切口出题，40-70字",
      "detail": "展开：如果出这道题，材料和设问大概长什么样，60-110字",
      "phrases": ["可直接入文的表述，10-30字，2-3条"]
    }}
  ],
  "quotes": [{{"text": "原文金句，必须是原文中的句子，20-60字", "use": "用在哪，6-16字"}}]
}}

要求：
- topics 3-5 个，按重要性排序，覆盖本期主干；每篇重要文章都应落在某个 topic 的 sources 里。
- exam 4-6 条，type 只能取 shenlun（申论）、changshi（常识时政）、mianshi（面试）三者之一，三类都要有。
- quotes 4-6 条，必须逐字摘自原文，不得改写。
- heat 为本期考点热度，1-5 的整数（涉及党的全国代表大会、中央全会、总书记重要文章取 4-5）。"""


def load_issue(no: int) -> dict | None:
    p = os.path.join(ISSUE_DIR, f"2026-{no:02d}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_articles_text(issue: dict, per_article: int = 1100) -> str:
    blocks = []
    for i, a in enumerate(issue["articles"], 1):
        text = "\n".join(a.get("paragraphs", []))
        head = text[:per_article]
        tail = ""
        if len(text) > per_article + 400:
            tail = "\n…（中略）…\n" + text[-380:]
        blocks.append(
            f"【{i}】{a['title']}\n"
            f"栏目：{a.get('category','')}　作者：{a.get('author','') or '未署名'}　{a.get('chars',0)}字\n"
            f"{head}{tail}"
        )
    return "\n\n".join(blocks)


def call_llm(prompt: str, retries: int = 3) -> str:
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    url = base + "/v1/chat/completions" if not base.endswith("/v1") else base + "/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    last = None
    for i in range(retries):
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"调用模型失败：{last}")


def extract_json(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def render_pdf_note(d: dict) -> str:
    return f"{d.get('theme','')} — {d.get('one_line','')}"


def _norm(s: str) -> str:
    s = s.replace("「", "“").replace("」", "”")
    return re.sub(r"[\s，。、；：,.;:「」“”‘’\"']", "", s)


def verify_quotes(digest: dict, issue: dict) -> int:
    """金句必须逐字出自原文，否则直接删掉——宁可少一条，也不能让用户背错。"""
    corpus = _norm(" ".join(" ".join(a.get("paragraphs", [])) for a in issue["articles"]))
    kept = []
    for q in digest.get("quotes") or []:
        text = q.get("text", "") if isinstance(q, dict) else str(q)
        if _norm(text) and _norm(text) in corpus:
            kept.append(q)
        else:
            print(f"    ! 剔除疑似编造的金句：{text[:40]}")
    digest["quotes"] = kept
    return len(kept)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, default=0)
    ap.add_argument("--missing", action="store_true", help="补齐所有缺提炼的期次")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只打印 prompt，不调模型")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY") and not args.dry_run:
        print("! 未设置 LLM_API_KEY，跳过提炼生成（站点仍会正常构建，只显示全文）")
        return 0

    os.makedirs(DIGEST_DIR, exist_ok=True)

    targets: list[int] = []
    if args.issue:
        targets = [args.issue]
    elif args.missing:
        for fn in sorted(os.listdir(ISSUE_DIR)):
            if fn.endswith(".json"):
                no = int(fn.split("-")[1].split(".")[0])
                if args.force or not os.path.exists(os.path.join(DIGEST_DIR, f"2026-{no:02d}.json")):
                    targets.append(no)

    if not targets:
        print("没有需要处理的期次")
        return 0

    for no in targets:
        issue = load_issue(no)
        if not issue:
            print(f"! 第 {no} 期数据不存在，先运行 scrape.py")
            continue
        prompt = USER_TMPL.format(issue=no, articles=build_articles_text(issue))
        if args.dry_run:
            print(prompt[:2000])
            continue
        print(f"→ 第 {no} 期 生成提炼中…（{len(prompt)} 字符）")
        try:
            d = extract_json(call_llm(prompt))
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ 失败：{e}")
            continue
        d["issue"] = no
        d["year"] = 2026
        d["model"] = os.environ.get("LLM_MODEL", "deepseek-chat")
        d["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        nq = verify_quotes(d, issue)
        with open(os.path.join(DIGEST_DIR, f"2026-{no:02d}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        print(f"  ✓ {render_pdf_note(d)}（金句 {nq} 条通过校验）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
