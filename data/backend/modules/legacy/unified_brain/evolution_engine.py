# -*- coding: utf-8 -*-
"""
evolution_engine.py — 快乐8 统一主脑真自进化引擎 (Unified Brain True Parameter Evolution Engine)
================================================================================================
【根据真实开奖残差与样本外实战表现，执行参数自适应优化与90条口诀规则赛马】：
  1. Focal Loss 焦点残差驱动：基于上一期真实开奖 20 码与主脑概率场残差，定量评估系统预测误差；
  2. 物理参数连续梯度自适应：高斯核宽 sigma (空间聚类)、时序半衰率 lambda (时序动量) 动态调优；
  3. 90条口诀规则库动态赛马 (Rule Race)：
     - 黄金激活态 (Lift >= 1.40x): 赋权 1.25x (能打胜仗，重用晋升)；
     - 达标稳定态 (1.00x <= Lift < 1.40x): 维持基准 1.00x；
     - 观察降权态 (0.50x <= Lift < 1.00x): 降权至 0.60x；
     - 静音淘汰态 (Lift < 0.50x 或 0命中): 一票静音 0.00x (屡战屡败，打入冷宫)；
  4. 状态持久化与代数总账本 (backend/config/unified_brain_params.json & storage/evolution/unified_evolution_ledger.json)；
  5. 老派量化操盘手大白话全景报告输出。
"""
from __future__ import annotations
from backend.utils.paths import get_outputs_dir

import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Set, Any, Tuple, Optional, Union

import numpy as np

from .feature_extractors import NUM_TOTAL, load_historical_draws, _get_draw_nums, _get_draw_period, _get_draw_date
from .unified_brain import UnifiedDecisionBrain, BRAIN_OUTPUT_DIR
from .loss_and_backprop import (
    calculate_focal_loss,
    calculate_spatial_dispersion,
    calculate_repeat_count,
    adapt_hyperparameters
)

# 路径常量定义
# 模块迁入 _retired/ 后目录层数变了，改为向上回溯到真正的项目根（同时含 backend / frontend / storage）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
while not (os.path.isdir(os.path.join(_BASE_DIR, "backend"))
           and os.path.isdir(os.path.join(_BASE_DIR, "frontend"))
           and os.path.isdir(os.path.join(_BASE_DIR, "storage"))):
    _parent = os.path.dirname(_BASE_DIR)
    if _parent == _BASE_DIR:
        break
    _BASE_DIR = _parent
EVOLUTION_STORE_FILE = os.path.join(_BASE_DIR, "backend", "config", "unified_brain_params.json")
EVOLUTION_LEDGER_FILE = os.path.join(_BASE_DIR, "storage", "evolution", "unified_evolution_ledger.json")
REPORTS_DIR = os.path.join(get_outputs_dir(), "reports")

os.makedirs(os.path.dirname(EVOLUTION_STORE_FILE), exist_ok=True)
os.makedirs(os.path.dirname(EVOLUTION_LEDGER_FILE), exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# =====================================================================
# 1. 90 条口诀离散规则实战赛马追踪器 (RuleRaceTracker)
# =====================================================================

class RuleRaceTracker:
    """
    90 条顺口溜与离散规则库动态赛马机制 (Rule Race Tracker)
    大白话：优胜劣汰赛马制！谁近期实战带号准就重用晋升（加权），谁总是瞎猜就打入冷宫（降权甚至静音淘汰）。
    """

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or self._get_default_rules_path()
        self.rules = self._load_rules(self.rules_path)

    def _get_default_rules_path(self) -> str:
        candidates = [
            os.path.join(_BASE_DIR, "backend", "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(_BASE_DIR, "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(os.getcwd(), "backend", "modules", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(_BASE_DIR, "backend", "core", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(_BASE_DIR, "core", "formula_jingle", "rules", "口诀表_stats.json"),
            os.path.join(os.getcwd(), "backend", "core", "formula_jingle", "rules", "口诀表_stats.json"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    def _load_rules(self, path: str) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("rules", {})
        except Exception:
            return {}

    def evaluate_rules(
        self,
        history_draws: List[Any],
        target_period: int,
        window: int = 30
    ) -> Tuple[Dict[str, float], Dict[str, Any], List[str]]:
        """
        基于最近 window 期真实开奖评估 90 条口诀的样本外命中率与提升度 (Lift)
        :param history_draws: 历史开奖数据列表
        :param target_period: 待预测目标期号
        :param window: 滚动考察窗口 (默认 30 期)
        :return: (rule_weights, rule_stats, rationales)
                 - rule_weights: {"1": 1.25, "2": 1.0, "3": 0.0, ...}
                 - rule_stats: 统计汇总字典
                 - rationales: 大白话赛马日志
        """
        valid_draws = [d for d in history_draws if _get_draw_period(d) < int(target_period)]
        if not valid_draws or not self.rules:
            return {}, {"total_rules": 0}, []

        hist_eval = valid_draws[-window:] if len(valid_draws) >= window else valid_draws
        n_eval = len(hist_eval)

        # 统计每条规则在 hist_eval 窗口内的触发次数与命中次数
        rule_results: Dict[str, Dict[str, Any]] = {}

        for rid, rule_info in self.rules.items():
            trigger = set(rule_info.get("trigger", []))
            predict = set(rule_info.get("predict", []))
            baseline = float(rule_info.get("baseline", 0.060127))

            trig_count = 0
            hit_count = 0
            single_hit_count = 0

            # 遍历历史评估窗口中的转移 (从 t-1 到 t)
            for t in range(1, n_eval):
                prev_nums = set(_get_draw_nums(hist_eval[t - 1]))
                cur_nums = set(_get_draw_nums(hist_eval[t]))

                if trigger and trigger.issubset(prev_nums):
                    trig_count += 1
                    hits_in_cur = len(predict & cur_nums)
                    if hits_in_cur == len(predict):
                        hit_count += 1
                    if hits_in_cur > 0:
                        single_hit_count += 1

            # 计算提升度与动态赋权
            if trig_count == 0:
                # 本考察期内未触发，采用历史 OOF 基线
                lift_oof = float(rule_info.get("lift_oof", 1.0))
                weight = 1.0
                status = "UNTRIGGERED"
                lift_val = lift_oof
            else:
                # 实际出击命中率
                hit_rate = hit_count / float(trig_count)
                # 使用成对全中或单号命中的综合提升度
                pair_lift = hit_rate / max(1e-4, baseline)
                single_rate = single_hit_count / float(trig_count)
                single_lift = single_rate / 0.448  # 选2中1的理论基准约 44.8%
                lift_val = round(max(pair_lift, single_lift * 0.8), 2)

                if lift_val >= 1.40:
                    status = "GOLD_ACTIVE"
                    weight = min(1.50, round(1.0 + 0.25 * (lift_val - 1.0), 2))
                elif lift_val >= 1.00:
                    status = "ACTIVE"
                    weight = 1.00
                elif lift_val >= 0.50:
                    status = "WEAKENED"
                    weight = 0.60
                else:
                    status = "MUTED"
                    weight = 0.00

            rule_results[str(rid)] = {
                "rule_id": str(rid),
                "trigger": list(trigger),
                "predict": list(predict),
                "triggers": trig_count,
                "hits": hit_count,
                "single_hits": single_hit_count,
                "lift": lift_val,
                "status": status,
                "weight": weight
            }

        # 整理统计与权重字典
        rule_weights: Dict[str, float] = {rid: res["weight"] for rid, res in rule_results.items()}
        promoted = [r for r in rule_results.values() if r["status"] == "GOLD_ACTIVE"]
        active = [r for r in rule_results.values() if r["status"] in ("ACTIVE", "UNTRIGGERED")]
        demoted = [r for r in rule_results.values() if r["status"] == "WEAKENED"]
        muted = [r for r in rule_results.values() if r["status"] == "MUTED"]

        # 排序提取明星晋升规则与淘汰冷宫规则
        promoted_sorted = sorted(promoted, key=lambda x: x["lift"], reverse=True)
        muted_sorted = sorted(muted, key=lambda x: x["triggers"], reverse=True)

        rule_stats = {
            "total_rules": len(rule_results),
            "promoted_count": len(promoted),
            "active_count": len(active),
            "demoted_count": len(demoted),
            "muted_count": len(muted),
            "promoted_rules": [r["rule_id"] for r in promoted_sorted[:10]],
            "muted_rules": [r["rule_id"] for r in muted_sorted[:10]],
            "window_evaluated": n_eval
        }

        # 大白话操盘手赛马日志
        rationales = [
            f"📜 90条口诀规则赛马 (近{n_eval}期样本外实测): "
            f"🟢 晋升重用 {len(promoted)} 条 (黄金激活态 1.25x), "
            f"🟡 达标稳定 {len(active)} 条, "
            f"🟠 观察降权 {len(demoted)} 条 (降至 0.6x), "
            f"🔴 静音淘汰 {len(muted)} 条 (打入冷宫 0.0x)"
        ]

        if promoted_sorted:
            top_p = promoted_sorted[0]
            rationales.append(
                f"   · 🌟 明星头马口诀 #{top_p['rule_id']} (触发 {top_p['trigger']} ➔ 预测 {top_p['predict']}) 实测 Lift={top_p['lift']:.2f}x，晋升赋权 {top_p['weight']}x"
            )

        if muted_sorted:
            top_m = muted_sorted[0]
            if top_m["triggers"] > 0:
                rationales.append(
                    f"   · ❄️ 屡战屡败口诀 #{top_m['rule_id']} (触发 {top_m['trigger']} {top_m['triggers']}次无建树)，执行一票静音 0.0x"
                )

        return rule_weights, rule_stats, rationales


# =====================================================================
# 2. 统一决策主脑自进化总引擎 (UnifiedBrainEvolutionEngine)
# =====================================================================

class UnifiedBrainEvolutionEngine:
    """
    统一决策主脑真实残差反向自进化引擎 (Unified Master Brain True Evolution Engine)
    大白话：操盘主脑的自我纠偏与反思进化系统。
    每天 22:00 同步开奖后，计算上一期预测残差损失，自适应更新空间核宽 sigma、时序衰减 lambda 与 90 条口诀赛马权重。
    """

    def __init__(self, data_root: Optional[str] = None):
        self.data_root = data_root or _BASE_DIR
        self.brain = UnifiedDecisionBrain(self.data_root)
        self.race_tracker = RuleRaceTracker()
        self.params = self._load_params()

    def _load_params(self) -> Dict[str, Any]:
        """加载主脑进化持久化参数文件"""
        if os.path.exists(EVOLUTION_STORE_FILE):
            try:
                with open(EVOLUTION_STORE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # 默认自进化基底参数
        return {
            "generation": 1,
            "architecture": "Unified Quantum State-Space Decision Brain v5.0",
            "last_calibrated_at": datetime.now().isoformat(),
            "target_period": 2026234,
            "sigma": 2.50,            # 空间高斯核宽 (安全边界 1.50 ~ 3.50)
            "lambda_decay": 0.95,     # 时序半衰衰减率 (安全边界 0.85 ~ 0.98)
            "temperature": 1.00,      # 玻尔兹曼温度 (0.80 ~ 1.50)
            "kill_size": 15,          # 硬雷区规模 (12 ~ 18)
            "last_loss": 0.0,
            "rule_weights": {},
            "rule_stats": {
                "total_rules": 90,
                "promoted_count": 0,
                "active_count": 90,
                "demoted_count": 0,
                "muted_count": 0
            },
            "calibration_log": []
        }

    def _save_params(self):
        """持久化保存最新代数自进化参数"""
        try:
            with open(EVOLUTION_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.params, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存主脑进化参数失败: {e}")

    def _append_ledger(self, entry: Dict[str, Any]):
        """将进化事件记录到统一进化总账本 (E5 整改: 按 target_period 原地去重, 杜绝同一期号重复累加)"""
        ledger = []
        if os.path.exists(EVOLUTION_LEDGER_FILE):
            try:
                with open(EVOLUTION_LEDGER_FILE, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []

        target_p = entry.get("target_period")
        updated = False
        if target_p is not None:
            for idx, item in enumerate(ledger):
                if item.get("target_period") == target_p:
                    ledger[idx] = entry
                    updated = True
                    break

        if not updated:
            ledger.append(entry)

        if len(ledger) > 100:
            ledger = ledger[-100:]

        try:
            with open(EVOLUTION_LEDGER_FILE, "w", encoding="utf-8") as f:
                json.dump(ledger, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存主脑进化总账本失败: {e}")

    def run_nightly_calibration(
        self,
        target_period: int,
        window: int = 30
    ) -> Dict[str, Any]:
        """
        执行夜间真实残差反向参数校准与规则赛马自进化全流程
        :param target_period: 当前待解算的目标期号 (例如 2026234)
        :param window: 规则赛马考察的历史期数窗口 (默认 30 期)
        :return: 当代自进化记录字典 (EvolutionStepResult Contract)
        """
        prev_period = int(target_period) - 1
        history = self.brain.feature_layer.draws
        prev_draw = self.brain.feature_layer.get_draw_by_period(prev_period)

        if not prev_draw:
            if history:
                prev_draw = history[-1]
                prev_period = int(prev_draw["period"])

        actual_nums = sorted(prev_draw["nums"]) if prev_draw else []
        actual_set = set(actual_nums)

        # 1. 尝试读取上一期已持久化的主脑概率场预测
        prev_json = os.path.join(BRAIN_OUTPUT_DIR, f"unified_decision_{prev_period}.json")
        prev_probs = None
        if os.path.exists(prev_json):
            try:
                with open(prev_json, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    prev_probs = np.array(
                        [float(d["probabilities"].get(str(i + 1), 0.0)) for i in range(NUM_TOTAL)],
                        dtype=np.float64
                    )
            except Exception:
                prev_probs = None

        if prev_probs is None:
            # 现场快速回溯重算上一期的先验概率场
            cur_sigma = float(self.params.get("sigma", 2.50))
            cur_lambda = float(self.params.get("lambda_decay", 0.95))
            cur_kill = int(self.params.get("kill_size", 15))
            prev_res = self.brain.solve_period(
                prev_period,
                sigma=cur_sigma,
                lambda_decay=cur_lambda,
                kill_size=cur_kill,
                rule_weights=self.params.get("rule_weights", None)
            )
            prev_probs = np.array(
                [float(prev_res["probabilities"].get(str(i + 1), 0.0)) for i in range(NUM_TOTAL)],
                dtype=np.float64
            )

        # 2. 计算上一期对账 Focal Loss 焦点残差损失
        focal_loss = calculate_focal_loss(
            predicted_probs=prev_probs,
            actual_draw=actual_nums,
            gamma=2.0,
            eps=1e-7
        )

        # 3. 提取历史两期，执行空间核宽 sigma 与时序衰减 lambda 反向自适应微调
        hist_before_prev = self.brain.feature_layer.get_history_before(prev_period, window=1)
        prev_prev_nums = hist_before_prev[0]["nums"] if hist_before_prev else None

        old_params = {
            "sigma": float(self.params.get("sigma", 2.50)),
            "lambda_decay": float(self.params.get("lambda_decay", 0.95)),
            "temperature": float(self.params.get("temperature", 1.00)),
            "kill_size": int(self.params.get("kill_size", 15))
        }

        new_params_dict, param_rationales = adapt_hyperparameters(
            current_params=old_params,
            actual_nums=actual_nums,
            prev_nums=prev_prev_nums,
            focal_loss=focal_loss,
            sigma_bounds=(1.50, 3.50),
            lambda_bounds=(0.85, 0.98),
            sigma_step=0.05,
            lambda_step=0.01
        )

        # 4. 执行 90 条口诀规则库实战赛马 (Rule Race)
        rule_weights, rule_stats, rule_rationales = self.race_tracker.evaluate_rules(
            history_draws=history,
            target_period=target_period,
            window=window
        )

        # 5. 代数晋升与更新
        current_gen = int(self.params.get("generation", 1))
        next_gen = current_gen + 1
        all_rationales = param_rationales + rule_rationales

        self.params["generation"] = next_gen
        self.params["target_period"] = int(target_period)
        self.params["sigma"] = new_params_dict["sigma"]
        self.params["lambda_decay"] = new_params_dict["lambda_decay"]
        self.params["last_loss"] = focal_loss
        self.params["last_calibrated_at"] = datetime.now().isoformat()
        self.params["rule_weights"] = rule_weights
        self.params["rule_stats"] = rule_stats
        self.params["calibration_log"] = all_rationales

        # 6. 持久化参数与总账本
        self._save_params()

        evolution_entry = {
            "generation": next_gen,
            "target_period": int(target_period),
            "prev_period_evaluated": prev_period,
            "focal_loss": focal_loss,
            "actual_draw": actual_nums,
            "sigma": new_params_dict["sigma"],
            "lambda_decay": new_params_dict["lambda_decay"],
            "temperature": old_params["temperature"],
            "kill_size": old_params["kill_size"],
            "old_params": old_params,
            "new_params": new_params_dict,
            "rule_stats": rule_stats,
            "promoted_rules": rule_stats.get("promoted_rules", []),
            "muted_rules": rule_stats.get("muted_rules", []),
            "rationales": all_rationales,
            "calibrated_at": self.params["last_calibrated_at"]
        }

        self._append_ledger(evolution_entry)
        self._generate_evolution_report_md(evolution_entry)

        return evolution_entry

    def run_rolling_evolution(
        self,
        n_periods: int = 10,
        window: int = 30
    ) -> List[Dict[str, Any]]:
        """
        滚动多期自进化模拟与压力测试 (Multi-Period Rolling Evolution)
        :param n_periods: 回溯滚动的总期数
        :param window: 规则赛马窗口
        :return: 每一代进化结果列表
        """
        draws = self.brain.feature_layer.draws
        if len(draws) < n_periods + 5:
            return []

        results = []
        target_draws = draws[-n_periods:]

        for d in target_draws:
            p = _get_draw_period(d)
            res = self.run_nightly_calibration(target_period=p, window=window)
            results.append(res)

        return results

    def _generate_evolution_report_md(self, entry: Dict[str, Any]):
        """生成最新自进化操盘手研报"""
        report_file = os.path.join(REPORTS_DIR, "evolution_report_latest.md")
        rule_stats = entry.get("rule_stats", {})

        lines = [
            f"# 🧬 快乐8 统一主脑真自进化模型第 {entry['generation']} 代演进报告",
            f"> 目标期号: {entry.get('target_period')} | 演进时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 架构: **纯物理态统一主脑 (Focal Loss 残差自学习)**",
            "",
            "## 📉 1. 上期对账与残差损失 (专查没猜中的硬骨头)",
            f"- **对账期号**: 第 `{entry.get('prev_period_evaluated')}` 期",
            f"- **开奖 20 码**: `{' '.join(str(x).zfill(2) for x in entry.get('actual_draw', []))}`",
            f"- **Focal Loss 焦点残差损失**: **`{entry.get('focal_loss')}`** (定量表征全局概率场偏差程度)",
            "",
            "## ⚙️ 2. 物理算子参数自适应微调 (大白话因果说明)",
            f"- 🌌 **空间高斯核宽 $\\sigma$ (看开奖扎堆还是分散)**: `{entry.get('old_params', {}).get('sigma', 2.5)}` ➔ **`{entry.get('sigma')}`**",
            f"- ⏱️ **时序动量衰减率 $\\lambda$ (看昨天的号灵不灵)**: `{entry.get('old_params', {}).get('lambda_decay', 0.95)}` ➔ **`{entry.get('lambda_decay')}`**",
            "",
            "## 📜 3. 90 条经典口诀实战赛马总览 (优胜劣汰赛马制)",
            f"- 🟢 **黄金激活态 (晋升赋权 1.25x)**: `{rule_stats.get('promoted_count', 0)}` 条",
            f"- 🟡 **达标稳定态 (基准赋权 1.00x)**: `{rule_stats.get('active_count', 0)}` 条",
            f"- 🟠 **观察降权态 (降权赋权 0.60x)**: `{rule_stats.get('demoted_count', 0)}` 条",
            f"- 🔴 **静音淘汰态 (一票静音 0.00x)**: `{rule_stats.get('muted_count', 0)}` 条",
            "",
            "### 💡 本代自进化决策理由全景清单:",
        ]

        for r in entry.get("rationales", []):
            lines.append(f"- {r}")

        lines.extend([
            "",
            "---",
            "> 📌 本进化账本已自动同步写入 `storage/evolution/unified_evolution_ledger.json` 与参数配置文件 `backend/config/unified_brain_params.json`。"
        ])

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            print(f"⚠️ 保存进化研报失败: {e}")
