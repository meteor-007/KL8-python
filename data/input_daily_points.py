# -*- coding: utf-8 -*-
"""Root shim: python input_daily_points.py -> scripts/input_daily_points.py"""
from __future__ import annotations
import runpy
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if __name__ == "__main__":
    runpy.run_path(os.path.join(_ROOT, "scripts", "input_daily_points.py"), run_name="__main__")
