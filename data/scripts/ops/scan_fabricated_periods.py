# -*- coding: utf-8 -*-
"""扫描全库"编造兜底期号"残留 (else 202xxxx / else "202xxxx")。只读，不改文件。"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAT = re.compile(r"else\s+[\"']?20[0-9]{5}[\"']?")
EXCLUDE_DIRS = {"archive", "__pycache__", ".git", ".idea", "node_modules", "storage", "frontend"}

hits = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        try:
            lines = open(p, encoding="utf-8", errors="ignore").read().split("\n")
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if PAT.search(line):
                hits.append((rel, i, line.strip()))

print("命中 %d 处：" % len(hits))
for rel, i, line in hits:
    print("  %-58s %5d  %s" % (rel, i, line[:120]))
