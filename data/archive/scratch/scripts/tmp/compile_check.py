import py_compile
import os
import sys
from pathlib import Path

# 切换到项目根目录（脚本位于 <root>/scripts/tmp/）
os.chdir(Path(__file__).resolve().parents[2])
files = [
    'pipeline/auto_generate_daily_report.py',
    'data_acquisition/fetch_kl8_history.py',
    'data_acquisition/process_hot_numbers.py',
    'data_acquisition/sync_history_to_excel.py',
    'data_acquisition/generate_hot_excel.py',
    'format/apply_formats.py',
    'core/feature_optimizer.py',
    'core/algorithm_optimizer.py',
    'core/strategy_optimizer.py',
    'core/entropy_optimizer.py',
    'core/score_composer.py',
    'core/loss_weight_updater.py',
    'core/walk_forward_validator.py',
    'learning/autonomous_learner.py',
    'utils/excel_lock.py',
    'utils/paths.py',
    'main_v2.py',
]

ok_count = 0
fail_count = 0
for f in files:
    if not os.path.exists(f):
        print(f'MISS: {f}')
        continue
    try:
        py_compile.compile(f, doraise=True)
        ok_count += 1
        print(f'OK: {f}')
    except py_compile.PyCompileError as e:
        fail_count += 1
        print(f'FAIL: {f} - {e}')

print(f'\n=== Total: {ok_count} OK, {fail_count} FAIL ===')
sys.exit(1 if fail_count > 0 else 0)
