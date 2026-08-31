"""
KillSeeker V1.0 — 杀号系统统一路径管理（整合版）
已迁移至主系统 data/ 目录下，所有路径基于 data/ 根目录统一引用。
"""
from pathlib import Path

# ===== 项目根目录（= data/ 主系统根）=====
# 文件位于 data/kill_seeker/config/paths.py，向上 2 级即 data/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ===== 本子系统各目录 =====
KILLSEEKER_ROOT = PROJECT_ROOT / "kill_seeker"
CONFIG_DIR    = KILLSEEKER_ROOT / "config"
CORE_DIR      = KILLSEEKER_ROOT / "core"
OUTPUT_DIR    = KILLSEEKER_ROOT / "logs"
LOGS_DIR      = KILLSEEKER_ROOT / "logs"
MEMORY_DIR    = KILLSEEKER_ROOT / "memory"
EVOLUTION_DIR = KILLSEEKER_ROOT / "evolution"

# ===== 共享数据层（与主系统共用，只读）=====
# data/ 本身就是数据根
DATA_ROOT = PROJECT_ROOT
KL8_HISTORY_FILE = DATA_ROOT / "kl8_history_final.txt"
AUC_STATS_FILE   = DATA_ROOT / "auc_stats.json"

# ===== 本子系统专属数据文件 =====
KILL_LOGS             = LOGS_DIR / "kill_logs.jsonl"
KILL_REPORT           = LOGS_DIR / "kill_report.txt"
PATTERN_TEMPLATE_FILE = CORE_DIR / "pattern_templates.json"
CONTEXT_MEMORY_FILE   = MEMORY_DIR / "CONTEXT_MEMORY.md"
EVOLUTION_LOG_FILE    = EVOLUTION_DIR / "SYSTEM_EVOLUTION_LOG.md"

# ===== 确保关键目录存在 =====
for _d in [OUTPUT_DIR, LOGS_DIR, MEMORY_DIR, EVOLUTION_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
