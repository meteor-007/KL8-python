# -*- coding: utf-8 -*-
"""Compatibility shim: backend.core.kl8_lab -> backend.modules.kl8_lab"""
from __future__ import annotations
import os as _os

_REAL = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..", "modules", 'kl8_lab')
)
__path__ = [_REAL]

_real_init = _os.path.join(_REAL, "__init__.py")
if _os.path.isfile(_real_init):
    with open(_real_init, "r", encoding="utf-8") as _f:
        _code = compile(_f.read(), _real_init, "exec")
    exec(_code, globals())
