# -*- coding: utf-8 -*-
"""Rewrite backend.core.* package shims with correct relative paths."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "backend", "core")

MAPPING = {
    "gold_pick2": "gold_pick2",
    "sixteen_period": "sixteen",
    "formula_jingle": "formula_jingle",
    "point_suppression": "point_suppression",
    "aggregation": "aggregation",
    "unified_brain": "unified_brain",
    "kl8_lab": "kl8_lab",
    "follow_analysis": "_retired/follow",
    "spatial_points": "_retired/spatial_points",
    "lstm": "_retired/lstm",
}

TPL = '''# -*- coding: utf-8 -*-
"""Compatibility shim: backend.core.{pkg} -> backend.modules.{real}"""
from __future__ import annotations
import os as _os

_REAL = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "modules", {parts})
)
__path__ = [_REAL]

_real_init = _os.path.join(_REAL, "__init__.py")
if _os.path.isfile(_real_init):
    with open(_real_init, "r", encoding="utf-8") as _f:
        _code = compile(_f.read(), _real_init, "exec")
    exec(_code, globals())
'''

for pkg, real in MAPPING.items():
    parts = ", ".join(repr(p) for p in real.split("/"))
    body = TPL.format(pkg=pkg, real=real, parts=parts)
    path = os.path.join(CORE, pkg, "__init__.py")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("rewrote", pkg, "->", real)

# Ensure modules/unified_brain/__init__.py has no BOM and is valid
ub = os.path.join(ROOT, "backend", "modules", "unified_brain", "__init__.py")
with open(ub, "w", encoding="utf-8", newline="\n") as f:
    f.write('# -*- coding: utf-8 -*-\n"""unified_brain module"""\n')
print("reset modules/unified_brain/__init__.py")
