# -*- coding: utf-8 -*-
"""One-shot: inject project-root bootstrap into backend/core compatibility shims."""
from __future__ import annotations

from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "backend" / "core"

HEADER = '''# -*- coding: utf-8 -*-
"""Compatibility shim: {old} -> {new}

可被直接执行；启动时注入项目根，避免 ModuleNotFoundError: backend。
"""
from __future__ import annotations

import os
import sys

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from {new} import *  # noqa: F401,F403
'''


def main() -> None:
    updated = []
    for path in sorted(CORE.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "Compatibility shim:" not in text:
            continue
        if "_PROJ_ROOT" in text:
            continue
        target = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("from backend.modules.") and " import " in s:
                target = s.split(" import ", 1)[0][5:]
                break
        if not target:
            continue
        old = f"backend.core.{path.stem}"
        path.write_text(HEADER.format(old=old, new=target), encoding="utf-8")
        updated.append(path.name)
    print(f"updated {len(updated)}: {updated}")


if __name__ == "__main__":
    main()
