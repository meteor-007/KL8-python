# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, ".")
from learning.autonomous_learner import AutonomousLearner
from core.learning_gate import gate_status

# load history
history = []
with open("kl8_history_final.txt", encoding="utf-8") as f:
    for line in f:
        line=line.strip()
        if not line: continue
        parts=dict(p.split(":",1) for p in line.split(","))
        nums=[int(x) for x in parts["numbers"].split("-")]
        history.append({"period": parts["period"], "date": parts["date"], "numbers": nums})

period = "2026194"
actual = next(h["numbers"] for h in history if h["period"]==period)
print("period", period, "actual", actual)
print("gate_before", gate_status())

learner = AutonomousLearner()
# on_new_result signature may vary - probe
import inspect
sig = inspect.signature(learner.on_new_result)
print("on_new_result sig", sig)
result = learner.on_new_result(period, actual, history)
print("RESULT", json.dumps(result, ensure_ascii=False, default=str)[:2000] if isinstance(result, dict) else result)
try:
    learner.print_diagnosis()
except Exception as e:
    print("diag err", e)
print("gate_after", gate_status())
