"""
KillSeeker V1.0 — 杀号系统统一路径管理
所有路径通过本模块统一引用，零硬编码路径残留
"""
from pathlib import Path

# ===== 项目根目录 =====
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ===== 本系统各子目录 =====
CONFIG_DIR = PROJECT_ROOT / "config"
CORE_DIR = PROJECT_ROOT / "core"
OUTPUT_DIR = PROJECT_ROOT / "logs"
LOGS_DIR = PROJECT_ROOT / "logs"
MEMORY_DIR = PROJECT_ROOT / "memory"
EVOLUTION_DIR = PROJECT_ROOT / "evolution"

# ===== 共享数据层（只读） =====
DATA_ROOT = PROJECT_ROOT.parent / "data"
KL8_HISTORY_FILE = DATA_ROOT / "kl8_history_final.txt"
AUC_STATS_FILE = DATA_ROOT / "auc_stats.json"

# ===== 本系统数据文件 =====
KILL_LOGS = LOGS_DIR / "kill_logs.jsonl"
KILL_REPORT = LOGS_DIR / "kill_report.txt"
PATTERN_TEMPLATE_FILE = CORE_DIR / "pattern_templates.json"
CONTEXT_MEMORY_FILE = MEMORY_DIR / "CONTEXT_MEMORY.md"
EVOLUTION_LOG_FILE = EVOLUTION_DIR / "SYSTEM_EVOLUTION_LOG.md"

# ===== 确保关键目录存在 =====
for _d in [OUTPUT_DIR, LOGS_DIR, MEMORY_DIR, EVOLUTION_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
