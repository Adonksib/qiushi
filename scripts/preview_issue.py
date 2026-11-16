#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印某一期的「速读版」，供人工或模型快速把握全期内容。

    python scripts/preview_issue.py --issue 22
    python scripts/preview_issue.py --issue 22 --head 700 --tail 200
"""
from __future__ import annotations

import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISSUE_DIR = os.path.join(ROOT, "data", "issues")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--head", type=int, default=900)
    ap.add_argument("--tail", type=int, default=180)
    args = ap.parse_args()

    p = os.path.join(ISSUE_DIR, f"2026-{args.issue:02d}.json")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)

    print(f"《求是》2026 年第 {args.issue} 期　出版 {d.get('published')}　"
          f"{d['article_count']} 篇 / {d['total_chars']} 字\n")

    for i, a in enumerate(d["articles"], 1):
        text = "\n".join(a.get("paragraphs", []))
        head = text[: args.head]
        tail = ""
        if len(text) > args.head + args.tail * 2:
            tail = "\n……\n" + text[-args.tail :]
        print("=" * 72)
        print(f"[{i:02d}] {a['title']}")
        print(f"     栏目：{a.get('category')}　作者：{a.get('author') or '未署名'}　{a.get('chars')}字")
        print("-" * 72)
        print(head + tail)
        print()


if __name__ == "__main__":
    main()
