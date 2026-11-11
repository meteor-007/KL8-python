# -*- coding: utf-8 -*-
"""Rewrite hardcoded cache/outputs/reports joins to paths helpers."""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    ".git", "archive", "__pycache__", "node_modules", "vendor",
    "storage",  # don't touch data files
}

# Patterns that are safe-ish mechanical rewrites when file already imports paths helpers
# or we inject import.

JOIN_PATTERNS = [
    # os.path.join(get_cache_dir(), ...)
    (
        re.compile(
            r'os\.path\.join\(\s*([A-Za-z_][\w\.]*)\s*,\s*[\'"]cache[\'"]\s*'
        ),
        r'os.path.join(get_cache_dir()',
        "get_cache_dir",
    ),
    (
        re.compile(
            r'os\.path\.join\(\s*([A-Za-z_][\w\.]*)\s*,\s*[\'"]outputs[\'"]\s*'
        ),
        r'os.path.join(get_outputs_dir()',
        "get_outputs_dir",
    ),
    (
        re.compile(
            r'os\.path\.join\(\s*([A-Za-z_][\w\.]*)\s*,\s*[\'"]output[\'"]\s*'
        ),
        r'os.path.join(get_outputs_dir()',
        "get_outputs_dir",
    ),
    (
        re.compile(
            r'os\.path\.join\(\s*([A-Za-z_][\w\.]*)\s*,\s*[\'"]reports[\'"]\s*'
        ),
        r'os.path.join(get_reports_dir()',
        "get_reports_dir",
    ),
    (
        re.compile(
            r'os\.path\.join\(\s*([A-Za-z_][\w\.]*)\s*,\s*[\'"]reviews[\'"]\s*'
        ),
        r'os.path.join(get_reviews_dir()',
        "get_reviews_dir",
    ),
]

# self.proj_dir / proj_dir style already covered by VAR pattern

IMPORT_LINE = (
    "from backend.utils.paths import ("
    "get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir"
    ")"
)


def needs_import(text: str, names: set[str]) -> bool:
    for n in names:
        if n in text and f"def {n}" not in text:
            # used
            pass
    used = {n for n in names if re.search(rf"\b{n}\b", text)}
    if not used:
        return False
    if "backend.utils.paths" in text or "utils.paths" in text:
        # may already import some
        return any(n not in text.split("import", 1)[-1][:500] if False else True for n in used)
    return True


def ensure_imports(text: str, needed: set[str]) -> str:
    if not needed:
        return text
    # If any get_*_dir already imported from paths, extend; else add import after future/coding
    if "get_cache_dir" in text and "from backend.utils.paths import" in text:
        # try to patch existing import
        def _patch(m):
            block = m.group(0)
            for n in sorted(needed):
                if n not in block:
                    block = block.rstrip(")\n") + f", {n})\n" if block.strip().endswith(")") else block
            return block
        # simpler: append a dedicated import if missing symbols
        missing = [n for n in needed if not re.search(rf"\b{n}\b", text[:2000])]
        if not missing:
            return text
        line = "from backend.utils.paths import " + ", ".join(sorted(needed)) + "\n"
        # insert after coding header
        lines = text.splitlines(True)
        insert_at = 0
        for i, ln in enumerate(lines[:40]):
            if ln.startswith("from __future__") or ln.startswith("#") or ln.startswith('"""') or ln.startswith("'''"):
                insert_at = i + 1
            if ln.startswith("import ") or ln.startswith("from "):
                insert_at = i
                break
        # find last consecutive import block start
        for i, ln in enumerate(lines[:80]):
            if ln.startswith("import ") or ln.startswith("from "):
                insert_at = i
                break
        lines.insert(insert_at, line)
        return "".join(lines)

    line = "from backend.utils.paths import " + ", ".join(sorted(needed)) + "\n"
    lines = text.splitlines(True)
    insert_at = 0
    for i, ln in enumerate(lines[:80]):
        if ln.startswith("import ") or ln.startswith("from "):
            insert_at = i
            break
        insert_at = i + 1
    lines.insert(insert_at, line)
    return "".join(lines)


def process_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    orig = text
    needed = set()
    for cre, repl, name in JOIN_PATTERNS:
        if cre.search(text):
            text = cre.sub(repl, text)
            needed.add(name)
    # also: os.path.join(get_cache_dir()# already covered by VAR pattern

    # string literals used as relative roots in freshness tables etc: "cache/..."
    # leave those; data_service may use them with proj join - handle separately

    if text == orig:
        return False

    text = ensure_imports(text, needed)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def main():
    changed = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        # only touch code areas
        rel = os.path.relpath(dirpath, ROOT)
        if not (rel.startswith("backend") or rel.startswith("tests") or rel.startswith("scripts") or rel == "."):
            if not any(rel.startswith(x) for x in ("backend", "tests", "scripts")):
                # allow root run_*.py
                if rel != ".":
                    continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if rel == "." and not (fn.startswith("run_") or fn in ("windows_service.py", "backend_daemon.py")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                if process_file(path):
                    changed.append(os.path.relpath(path, ROOT))
            except Exception as e:
                print("ERR", path, e)
    print(f"updated {len(changed)} files")
    for c in changed[:80]:
        print(" ", c)
    if len(changed) > 80:
        print(f"  ... +{len(changed)-80} more")


if __name__ == "__main__":
    main()
