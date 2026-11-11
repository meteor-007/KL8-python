# -*- coding: utf-8 -*-
"""Move misplaced from __future__ imports to legal positions."""
import os

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")


def fix_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    fut_idxs = [i for i, l in enumerate(lines) if l.startswith("from __future__ import")]
    if not fut_idxs:
        return False

    fi = fut_idxs[0]
    bad = False
    in_doc = False
    doc_char = None
    for i, l in enumerate(lines[:fi]):
        s = l.strip()
        if not s or s.startswith("#") or s.startswith("#!"):
            continue
        if not in_doc and (s.startswith('"""') or s.startswith("'''")):
            doc_char = s[:3]
            if s.count(doc_char) >= 2 and len(s) > 3:
                continue
            in_doc = True
            continue
        if in_doc:
            if doc_char and doc_char in s:
                in_doc = False
            continue
        bad = True
        break
    if not bad:
        return False

    futures = [lines[i] for i in fut_idxs]
    body = [l for i, l in enumerate(lines) if i not in fut_idxs]

    insert_at = 0
    in_doc = False
    doc_char = None
    for i, l in enumerate(body):
        s = l.strip()
        if i == 0 and (s.startswith("#") or s.startswith("#!")):
            insert_at = 1
            continue
        if not in_doc and (s.startswith('"""') or s.startswith("'''")):
            doc_char = s[:3]
            if s.count(doc_char) >= 2 and len(s) > 3:
                insert_at = i + 1
                break
            in_doc = True
            insert_at = i + 1
            continue
        if in_doc:
            insert_at = i + 1
            if doc_char and doc_char in s:
                break
            continue
        insert_at = i
        break

    new_lines = body[:insert_at] + futures + body[insert_at:]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(new_lines)
    return True


def main():
    fixed = []
    for dirpath, _, files in os.walk(ROOT):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dirpath, f)
            if fix_file(p):
                fixed.append(os.path.relpath(p, ROOT))
    print("fixed", len(fixed))
    for p in fixed:
        print(" ", p)


if __name__ == "__main__":
    main()
