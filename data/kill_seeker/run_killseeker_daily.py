"""
KillSeeker — 日常运行入口（整合版）
迁移自原 KillSeeker/main.py，适配主系统 data/ 目录结构。

用法（在 data/ 目录下执行）:
    python kill_seeker/run_killseeker_daily.py              # 完整杀号分析
    python kill_seeker/run_killseeker_daily.py --predict    # 仅杀号预测
    python kill_seeker/run_killseeker_daily.py --review     # 复盘上期杀号
    python kill_seeker/run_killseeker_daily.py --full       # 完整流程(复盘+预测)
    python kill_seeker/run_killseeker_daily.py --full --as-of PERIOD
    python kill_seeker/run_killseeker_daily.py --backtest N # N期回测
    python kill_seeker/run_killseeker_daily.py --diagnose   # 系统诊断
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

# ── 路径注入：让 kill_seeker/ 内部的 from kill_seeker.core.xxx 和 from kill_seeker.config.xxx 正常解析 ──
_THIS_DIR = Path(__file__).resolve().parent        # = data/kill_seeker/
_DATA_DIR = _THIS_DIR.parent                        # = data/
_PROJ_DIR = _DATA_DIR.parent                        # = Python-Project/

# 插入 kill_seeker 本身（使 core/ config/ 可被直接找到）
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
# 插入 data/（使主系统模块可被访问）
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))
# 插入 Python-Project/（使 kl8_stats 等兄弟包可被访问）
if str(_PROJ_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJ_DIR))

# ── 修改工作目录到 kill_seeker/，确保相对路径引用正确 ──
os.chdir(_THIS_DIR)

# ── 导入并执行原 main.py 逻辑 ──
# 原 main.py 已备份为 _original_main.py，直接 exec 它
_main_file = _THIS_DIR / "_original_main.py"
with open(_main_file, "r", encoding="utf-8") as _f:
    _code = _f.read()

exec(compile(_code, str(_main_file), "exec"), {"__name__": "__main__", "__file__": str(_main_file)})
