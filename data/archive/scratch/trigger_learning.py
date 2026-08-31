#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""触发闭环学习"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from learning.autonomous_learner import AutonomousLearner
from utils.history_loader import load_history

history = load_history()
learner = AutonomousLearner()

# 2026181 actual numbers
actual = [64, 30, 59, 63, 48, 38, 12, 10, 35, 76, 6, 28, 33, 65, 79, 22, 71, 42, 18, 58]
result = learner.on_new_result('2026181', actual, history)
print('Decision:', result.get('decision', 'N/A'))
print('Weights before:', result.get('weights_before', {}))
print('Weights after:', result.get('weights_after', {}))
print('Strategy mode:', result.get('strategy_mode', 'N/A'))
report = result.get('report', '')
if report:
    print('Report:', report[:800])
learner.print_diagnosis()
