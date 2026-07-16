from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
DATA_ROOT = WORKSPACE_ROOT / "data"
KL8_HISTORY_FILE = DATA_ROOT / "kl8_history_final.txt"
# daily_points.txt 是「点位」数据，不是开奖号码；本系统预测只依赖 kl8_history_final.txt
DAILY_POINTS_FILE = DATA_ROOT / "daily_points.txt"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MODEL_DIR = OUTPUT_DIR / "models"
PRED_DIR = OUTPUT_DIR / "predictions"
REPORT_TXT = OUTPUT_DIR / "latest_report.txt"
REPORT_JSON = OUTPUT_DIR / "latest_report.json"
PRED_LOG = OUTPUT_DIR / "pred_logs.jsonl"

for _d in (OUTPUT_DIR, MODEL_DIR, PRED_DIR):
    _d.mkdir(parents=True, exist_ok=True)
