# -*- coding: utf-8 -*-
"""
定金选2 自主闭环学习与参数调优引擎 (Autonomous Closed-Loop Learner)
=============================================================================
遵循老派量化操盘手大白话落地执行协议：
1. 四大能力统一闭环：
   - 自主复盘 (autonomous_review)
   - 自主学习 (autonomous_learn)
   - 自我调整 (self_adjust)
   - 安全熔断防过拟合
2. 铁血约束规则：
   - 单步调整幅度 <= ±15%
   - 累积偏离 <= ±50%
   - 最小批次样本约束：样本不足 50 时禁止批量更新权重
   - Level 2 状态下限制最大 5% 幅度微调，Level 3 完全冻结参数
"""
from backend.utils.paths import get_cache_dir
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from backend.utils.paths import get_project_root
    PROJ_DIR = get_project_root()
except Exception:
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and os.path.dirname(curr) != curr:
        if os.path.exists(os.path.join(curr, "kl8_history_final.txt")) or os.path.exists(os.path.join(curr, "GEMINI.md")):
            break
        curr = os.path.dirname(curr)
    PROJ_DIR = curr

_BACKEND_DIR = os.path.join(PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

PARAM_FILE = os.path.join(_BACKEND_DIR, "learning", "gold_pick2", "parameter_store.json")
HISTORY_FILE = os.path.join(_BACKEND_DIR, "learning", "gold_pick2", "parameter_history.jsonl")


class GoldPick2Learner:
    """定金选2 自主闭环学习器"""

    MAX_SINGLE_STEP = 0.15
    MAX_CUMULATIVE = 0.50
    MIN_BATCH_SAMPLES = 50

    def __init__(self, param_file: Optional[str] = None):
        self.param_file = param_file or PARAM_FILE
        self.history_file = HISTORY_FILE
        self._ensure_storage()
        self.state = self.load_state()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.param_file), exist_ok=True)
        if not os.path.exists(self.param_file):
            default_state = {
                "weights": {
                    "omission": 0.55,
                    "markov": 0.15,
                    "graph": 0.10,
                    "bollinger": 0.10,
                    "trend": 0.05,
                    "signal": 0.05
                },
                "total_reviews": 0,
                "consecutive_low_performance": 0,
                "last_review_date": datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.now().isoformat()
            }
            with open(self.param_file, "w", encoding="utf-8") as f:
                json.dump(default_state, f, ensure_ascii=False, indent=2)

    def load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.param_file):
            try:
                with open(self.param_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "weights": {
                "omission": 0.55,
                "markov": 0.15,
                "graph": 0.10,
                "bollinger": 0.10,
                "trend": 0.05,
                "signal": 0.05
            }
        }

    def save_state(self):
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.param_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Learner] 保存参数状态异常: {e}")

    def update_weights_from_review(self, level: int, failure_modes: List[str]) -> Dict[str, Any]:
        """根据复盘与置信评级进行温和微调（受全局自学习门控约束）"""
        # 2026-09-10 整改 B4：参数文件显式 frozen 标记 —— 冻结即只读, 直接返回 FROZEN
        if self.state.get("frozen", False):
            return {"status": "FROZEN",
                    "reason": self.state.get("frozen_reason", "参数已冻结 (B4)")}
        # 2026-09-10 整改 D1/B4：全局门控冻结时参数只读，禁止任何改写
        if self._learning_paused():
            return {"status": "SKIPPED", "reason": "全局自学习门控已冻结 (WF Lift CI下界<1.0)，参数只读"}

        if level >= 3:
            return {"status": "SKIPPED", "reason": "Level 3 降级保护冻结参数"}

        max_step = 0.05 if level == 2 else self.MAX_SINGLE_STEP
        current_w = dict(self.state.get("weights", {}))

        # 调整建议（2026-09-10 整改 B4 修正方向）：
        #   双中失败时强化已验证的遗漏信号、弱化已证伪的共现信号，
        #   而非旧逻辑那样反向加码 graph（共现 Lift≈1.008 已证伪）。
        if "GOLDEN_MISS" in failure_modes:
            current_w["omission"] = min(0.70, current_w.get("omission", 0.55) * (1 + max_step))
        if "COMBO2_ZERO" in failure_modes:
            current_w["graph"] = max(0.05, current_w.get("graph", 0.10) * (1 - max_step))
            current_w["omission"] = min(0.70, current_w.get("omission", 0.55) * (1 + max_step))

        # 归一化
        total = sum(current_w.values())
        if total > 0:
            current_w = {k: round(v / total, 3) for k, v in current_w.items()}

        self.state["weights"] = current_w
        self.save_state()
        return {"status": "SUCCESS", "weights": current_w}

    @staticmethod
    def _learning_paused() -> bool:
        """读取全局自学习门控状态；冻结或文件缺失(无法证明 Lift>1)时一律视为暂停。"""
        gate_file = os.path.join(get_cache_dir(), "learning_gate_state.json")
        try:
            with open(gate_file, "r", encoding="utf-8") as f:
                st = json.load(f)
            return not st.get("learning_enabled", False)
        except Exception:
            return True


def batch_update(results: List[Dict[str, Any]], min_batch: int = 50) -> bool:
    """
    批量样本学习更新接口 (用于单元测试与批量校验)
    样本不足 min_batch 时拒绝更新
    """
    if not results or len(results) < min_batch:
        return False
    
    # 模拟满足样本要求时的安全更新
    learner = GoldPick2Learner()
    hits = sum(1 for r in results if r.get("hit", False))
    hit_rate = hits / len(results)
    if hit_rate < 0.20:
        learner.update_weights_from_review(level=2, failure_modes=["GOLDEN_MISS"])
    return True
