"""
KillSeeker V1.0 - kill number prediction system.
Core: lower engine score = less likely to appear = high confidence kill.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
import numpy as np

from core.similarity_matcher import SimilarityResult
from core.density_detector import DensityResult
from core.pattern_recognizer import PatternResult
from core.curve_analyzer import CurveResult
from core.markov_engine import MarkovResult, MarkovEngine
from config.model_config import KillConfig


@dataclass
class KillPrediction:
    period: str
    high_conf_kills: List[int]
    mid_conf_kills: List[int]
    low_conf_kills: List[int]
    all_kills: List[int]
    safe_numbers: List[int]
    engine_contributions: Dict[str, float]
    kill_confidence: float


class KillPredictor:
    """低分杀号预测器。defense_config/history 已废弃，保留 kwargs 兼容旧调用。"""

    def __init__(self, kill_config=None, markov_config=None, defense_config=None,
                 history=None, **_ignored):
        self.kill_config = kill_config or KillConfig()
        self.weights = dict(self.kill_config.engine_weights)
        self.markov_engine = MarkovEngine(markov_config)

    def predict(self, period, sim_result, density_result, pattern_result, curve_result,
                markov_result=None, history=None):
        self.weights = dict(self.kill_config.engine_weights)
        # pattern 权重为 0 时跳过形态信号，避免噪声与无效计算
        if self.weights.get("pattern", 0.0) <= 0:
            pattern_result = None

        signals = self._collect_signals(sim_result, density_result, pattern_result,
                                        curve_result, markov_result)
        scores = self._score_numbers(signals)
        sorted_by_low = sorted(scores.keys(), key=lambda x: scores[x])
        high_kills = self._select_kills_with_balance(
            sorted_by_low, self.kill_config.high_conf_kill_count)
        mid_kills = self._select_kills_with_balance(
            [n for n in sorted_by_low if n not in high_kills],
            self.kill_config.mid_conf_kill_count)
        low_kills = self._select_kills_with_balance(
            [n for n in sorted_by_low if n not in high_kills and n not in mid_kills],
            self.kill_config.low_conf_kill_count)
        all_kills = high_kills + mid_kills + low_kills
        safe_numbers = list(reversed(sorted_by_low))[: self.kill_config.safe_count]
        kill_confidence = self._calc_kill_confidence(scores, all_kills)
        contributions = self._compute_contributions(all_kills, signals)
        return KillPrediction(
            period=period, high_conf_kills=high_kills, mid_conf_kills=mid_kills,
            low_conf_kills=low_kills, all_kills=all_kills, safe_numbers=safe_numbers,
            engine_contributions=contributions, kill_confidence=kill_confidence)

    def _collect_signals(self, sim_result, density_result, pattern_result, curve_result,
                         markov_result=None):
        signals = {}
        sim_signal = {}
        max_freq = max(sim_result.subsequent_freq.values()) if sim_result.subsequent_freq else 1.0
        for num in range(1, 81):
            freq = sim_result.subsequent_freq.get(num, 0.0)
            sim_signal[num] = freq / max(max_freq, 1e-8)
        signals["similarity"] = sim_signal
        density_signal = {}
        for num in range(1, 81):
            row = (num - 1) // 10
            col = (num - 1) % 10
            density_signal[num] = float(density_result.density_map[row, col])
        signals["density"] = density_signal
        if pattern_result is None:
            pattern_signal = {num: 0.0 for num in range(1, 81)}
        elif pattern_result.fill_ratio > 0.3:
            pattern_signal = {}
            for num in range(1, 81):
                row = (num - 1) // 10
                col = (num - 1) % 10
                dist = np.sqrt((row - 3.5) ** 2 + (col - 4.5) ** 2)
                tpl_score = pattern_result.top3_templates[0][1] if pattern_result.top3_templates else 0.5
                pattern_signal[num] = max(0, 1.0 - dist / 5.0) * tpl_score
        else:
            pattern_signal = {num: 0.5 for num in range(1, 81)}
        signals["pattern"] = pattern_signal
        curve_signal = {}
        for num in range(1, 81):
            info = curve_result.layer1_data.get(num, {})
            omission = info.get("current_omission", 0)
            freq = info.get("rolling_freq", 0)
            state = info.get("markov_state", "W")
            max_omission = max(50, omission + 1)
            revert_signal = 1.0 - omission / max_omission
            freq_signal = min(freq / 10.0, 1.0)
            state_signal = {"H": 1.0, "W": 0.7, "C": 0.4, "X": 0.2}.get(state, 0.5)
            decade = (num - 1) // 10
            zone_key = f"zone_{decade}"
            zone_series = curve_result.layer2_data.get(zone_key, [])
            if len(zone_series) >= 5:
                recent5 = np.array(zone_series[:5], dtype=float)
                slope = recent5[0] - recent5[-1]
                trend_signal = float(np.clip(0.5 + slope * 0.1, 0.0, 1.0))
            else:
                trend_signal = 0.5
            curve_signal[num] = (revert_signal * 0.40 + freq_signal * 0.25
                                  + state_signal * 0.15 + trend_signal * 0.20)
        signals["curve"] = curve_signal
        # 引擎5: 马尔可夫链（权重 0 或未提供时用中性 0.5，不参与评分）
        if self.weights.get("markov", 0.0) > 0 and markov_result is not None:
            signals["markov"] = self.markov_engine.to_signal(markov_result)
        else:
            signals["markov"] = {num: 0.5 for num in range(1, 81)}
        return signals

    def _score_numbers(self, signals):
        scores = {}
        for num in range(1, 81):
            s = 0.0
            for engine, signal in signals.items():
                s += self.weights.get(engine, 0.0) * signal.get(num, 0.0)
            scores[num] = s
        return scores

    def _select_kills_with_balance(self, sorted_low, count):
        selected = []
        decade_count = [0] * 8
        max_per_decade = self.kill_config.max_kill_per_decade
        for num in sorted_low:
            if len(selected) >= count:
                break
            decade = (num - 1) // 10
            if decade_count[decade] < max_per_decade:
                selected.append(num)
                decade_count[decade] += 1
        # 兜底：主循环可能因 max_per_decade 配额而凑不满 count，
        # 兜底补号同样尊重 max_per_decade（跳过已满区间），
        # 避免破坏十年区间均衡约束（旧实现直接追加会超配额）。
        if len(selected) < count:
            for num in sorted_low:
                if len(selected) >= count:
                    break
                if num in selected:
                    continue
                decade = (num - 1) // 10
                if decade_count[decade] < max_per_decade:
                    selected.append(num)
                    decade_count[decade] += 1
        return selected

    def _calc_kill_confidence(self, scores, kills):
        if not kills:
            return 0.0
        kill_avg = np.mean([scores[n] for n in kills])
        all_avg = np.mean(list(scores.values()))
        all_std = np.std(list(scores.values()))
        if all_std == 0:
            return 0.5
        z = (all_avg - kill_avg) / all_std
        return float(np.clip(0.5 + z * 0.15, 0.1, 0.95))

    def _compute_contributions(self, kills, signals):
        contributions = {}
        for engine, signal in signals.items():
            total = sum(signal.get(num, 0.0) for num in kills)
            contributions[engine] = float(total * self.weights.get(engine, 0.0))
        total_c = sum(contributions.values())
        if total_c > 0:
            contributions = {k: v / total_c for k, v in contributions.items()}
        return contributions
