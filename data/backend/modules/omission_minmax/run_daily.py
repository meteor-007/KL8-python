# -*- coding: utf-8 -*-
"""
每日独立推演入口脚本 (run_daily) - 纯血统零点位版
================================================================================
@author czw
@since 2026-10-31
"""
import sys
from .engine import run_pure_omission_resonance

def main():
    target_period = sys.argv[1] if len(sys.argv) > 1 else "2026290"
    run_pure_omission_resonance(target_period)

if __name__ == "__main__":
    main()
