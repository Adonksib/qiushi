#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用本地 Chromium（Chrome / Edge）把 dist/print/*.html 打印成 dist/pdf/*.pdf。

    python scripts/build_pdf.py [--dist dist] [--issue 22]

依赖：本机安装 Chrome 或 Edge；Linux 下需 fonts-noto-cjk 提供中文字体。
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_chrome() -> str:
    for c in CANDIDATES:
        if c and os.path.exists(c):
            return c
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("未找到 Chrome/Edge，请设置环境变量 CHROME_PATH")


def to_file_url(path: str) -> str:
    p = os.path.abspath(path).replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return "file://" + p


def print_pdf(chrome: str, html_path: str, pdf_path: str, profile: str) -> bool:
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--disable-extensions",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={os.path.abspath(pdf_path)}",
        f"--user-data-dir={profile}",
        to_file_url(html_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False
    return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 8000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--issue", type=int, default=0)
    args = ap.parse_args()

    dist = os.path.join(ROOT, args.dist)
    print_dir = os.path.join(dist, "print")
    pdf_dir = os.path.join(dist, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)

    pattern = os.path.join(print_dir, f"2026-{args.issue:02d}.html" if args.issue else "*.html")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"没有找到待转换的 HTML：{pattern}")
        return 1

    chrome = find_chrome()
    print(f"→ 使用 {chrome}")
    print(f"→ 共 {len(files)} 期待转 PDF")

    ok = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, f in enumerate(files, 1):
            name = os.path.splitext(os.path.basename(f))[0]
            out = os.path.join(pdf_dir, name + ".pdf")
            profile = os.path.join(tmp, f"p{i}")
            if print_pdf(chrome, f, out, profile):
                size = os.path.getsize(out) // 1024
                print(f"  [{i:02d}/{len(files)}] ✓ {name}.pdf  {size} KB")
                ok += 1
            else:
                print(f"  [{i:02d}/{len(files)}] ✗ {name} 生成失败")

    print(f"\n完成：{ok}/{len(files)} 期 PDF 输出到 {pdf_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
