#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/digests/*.json 的结构与「金句必须出自原文」。

    python scripts/check_digests.py            # 全部
    python scripts/check_digests.py --issue 22 # 单期
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISSUE_DIR = os.path.join(ROOT, "data", "issues")
DIGEST_DIR = os.path.join(ROOT, "data", "digests")

REQUIRED = ["issue", "theme", "one_line", "overview", "keywords", "topics", "exam", "quotes"]
TYPES = {"shenlun", "changshi", "mianshi"}


def norm(s: str) -> str:
    s = s.replace("「", "“").replace("」", "”")
    return re.sub(r"[\s，。、；：,.;:「」“”‘’\"']", "", s)


def check(no: int) -> list[str]:
    errs: list[str] = []
    ip = os.path.join(ISSUE_DIR, f"2026-{no:02d}.json")
    dp = os.path.join(DIGEST_DIR, f"2026-{no:02d}.json")
    if not os.path.exists(dp):
        return [f"缺少提炼文件 {dp}"]
    issue = json.load(open(ip, encoding="utf-8"))
    dg = json.load(open(dp, encoding="utf-8"))

    for k in REQUIRED:
        if k not in dg:
            errs.append(f"缺少字段 {k}")

    if len(dg.get("one_line", "")) > 70:
        errs.append("one_line 过长（>70字）")
    if not (len(dg.get("overview") or []) >= 2):
        errs.append("overview 至少 2 段")
    if not (3 <= len(dg.get("topics") or []) <= 6):
        errs.append("topics 应为 3-6 个")
    if len(dg.get("quotes") or []) < 3:
        errs.append("quotes 至少 3 条")

    # 考点必须覆盖三类题型
    types = {e.get("type") for e in dg.get("exam") or []}
    if not types <= TYPES:
        errs.append(f"exam.type 出现非法值：{types - TYPES}")
    if len(types) < 3:
        errs.append(f"exam 三类题型未覆盖（现为 {types}）")

    # topics 必须有要点
    for t in dg.get("topics") or []:
        if not t.get("name"):
            errs.append("topic 缺 name")
        if len(t.get("points") or []) < 2:
            errs.append(f"topic「{t.get('name')}」要点少于 2 条")

    # 金句逐字校验
    corpus = norm(" ".join(" ".join(a.get("paragraphs", [])) for a in issue["articles"]))
    for q in dg.get("quotes") or []:
        text = q.get("text", "") if isinstance(q, dict) else str(q)
        if norm(text) not in corpus:
            errs.append(f"金句不在原文中：{text[:38]}")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, default=0)
    args = ap.parse_args()

    nos = [args.issue] if args.issue else sorted(
        int(f.split("-")[1].split(".")[0]) for f in os.listdir(ISSUE_DIR) if f.endswith(".json")
    )

    bad = 0
    for no in nos:
        errs = check(no)
        if errs:
            bad += 1
            print(f"✗ 第 {no} 期")
            for e in errs:
                print(f"    - {e}")
        else:
            print(f"✓ 第 {no} 期")

    print(f"\n{'全部通过' if not bad else f'{bad} 期有问题'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
