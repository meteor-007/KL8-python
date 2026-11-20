# -*- coding: utf-8 -*-
"""快乐8 点位+遗漏号科学检验与反向证伪 · 统一入口转发脚本"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
val_dir = os.path.join(current_dir, "validation")
sys.path.insert(0, val_dir)
os.chdir(val_dir)

import main

if __name__ == "__main__":
    main.main()
