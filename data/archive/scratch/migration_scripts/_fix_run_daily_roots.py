# -*- coding: utf-8 -*-
"""One-shot: fix Dual-Root bootstrap in modules/*/run_daily.py after move."""
import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = os.path.join(ROOT, "backend", "modules")

NEW_BOOTSTRAP = '''# 路径自适应 (模块迁入 backend/modules 后：向上定位项目根)
def _find_project_root(start: str) -> str:
    curr = start
    for _ in range(8):
        if os.path.isdir(os.path.join(curr, "backend")) and os.path.isdir(os.path.join(curr, "frontend")):
            return curr
        if os.path.exists(os.path.join(curr, "GEMINI.md")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return start

_PROJ_DIR = _find_project_root(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR
'''

SOFT = re.compile(
    r"(?:# 路径自适应[^\n]*\n)?"
    r"_PROJ_DIR = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\n"
    r"_BACKEND_DIR = os\.path\.join\(_PROJ_DIR, \"backend\"\)\n"
    r"for _p in \[_BACKEND_DIR, _PROJ_DIR\]:\n"
    r"    if _p not in sys\.path:\n"
    r"        sys\.path\.insert\(0, _p\)\n"
    r"(?:PROJ_DIR = _PROJ_DIR\n)?"
)

fixed = []
skipped = []
for path in glob.glob(os.path.join(MODS, "**", "run_daily.py"), recursive=True):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if SOFT.search(text):
        new = SOFT.sub(NEW_BOOTSTRAP + "\n", text, count=1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        fixed.append(os.path.relpath(path, ROOT))
    else:
        skipped.append(os.path.relpath(path, ROOT))

print("FIXED", len(fixed))
for p in fixed:
    print(" ", p)
print("SKIPPED", len(skipped))
for p in skipped:
    print(" ", p)
