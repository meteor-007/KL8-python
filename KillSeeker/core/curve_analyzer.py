"""
MorphoSeeker V1.0 — 引擎4: 曲线分析器
三层曲线体系: 单号走势 + 区间指标 + 形态特征
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

from core.data_loader import KL8Draw
from config.model_config import CurveConfig


@dataclass
class CurveResult:
    """曲线分析结果"""
    layer1_data: Dict[int, Dict]    # 号码→{omission, freq, state}（参与评分）
    layer2_data: Dict[str, List]    # 指标名→时序数据（参与评分）
    layer3_data: Dict[str, List]    # 特征名→时序数据（未接入评分，恒为 {}）
    anomaly_points: List[Dict]      # [{period, layer, metric, z_score}]（仅展示，未接入评分）
    trend_forecast: Dict[str, List] # 指标→外推3期（未接入评分，恒为 {}）
    dominant_period: float          # FFT主周期（仅展示，未接入评分）


class CurveAnalyzer:
    """引擎4: 曲线分析器"""

    def __init__(self, config: Optional[CurveConfig] = None):
        self.config = config or CurveConfig()

    def analyze(self, history: List[KL8Draw]) -> CurveResult:
        """
        三层曲线分析

        Args:
            history: 历史开奖数据(≤T)

        Returns:
            CurveResult
        """
        # Layer 1: 单号走势
        layer1 = self._compute_layer1(history)

        # Layer 2: 区间指标
        layer2 = self._compute_layer2(history)

        # 异常点检测（仅展示，未接入评分）
        anomalies = self._detect_anomalies(layer2, history)

        # FFT主周期（仅展示，未接入评分）
        dominant_period = self._compute_fft_period(layer2.get("sum_value", []))

        return CurveResult(
            layer1_data=layer1,
            layer2_data=layer2,
            # layer3_data / trend_forecast 未接入评分，不再计算
            # （原 _compute_layer3/_forecast_trends 计算昂贵但结果无人消费，已移除）
            layer3_data={},
            anomaly_points=anomalies,
            trend_forecast={},
            dominant_period=dominant_period,
        )

    def _compute_layer1(self, history: List[KL8Draw]) -> Dict[int, Dict]:
        """Layer 1: 单号走势(80条线) (V3.1修复: 遗漏计算逻辑纠正)"""
        result = {}
        for num in range(1, 81):
            # V3.1修复: 正确计算当前遗漏
            # history按期号降序(最新在前)，从最新期开始数遗漏
            current_omission = 0
            for draw in history:
                if num in draw.numbers:
                    break  # 找到最近一次出现，遗漏停止累加
                current_omission += 1
            
            # 遗漏值序列(历史遗漏值，用于统计)
            omission_series = []
            omission = 0
            for draw in reversed(history):  # 从最旧期开始
                if num in draw.numbers:
                    omission_series.append(omission)
                    omission = 0
                else:
                    omission += 1

            # 滚动频率(近30期)
            recent_draws = history[:self.config.rolling_freq_window]
            freq = sum(1 for d in recent_draws if num in d.numbers)

            # 马尔可夫状态
            state = self._markov_state(current_omission)

            result[num] = {
                "current_omission": current_omission,
                # omission_series 按期序从旧到新排列（reversed(history) 从最旧期开始），
                # 最近50个在末尾 → 用 [-50:]；旧实现 [:50] 取的是最旧50个（方向错误）
                "omission_series": omission_series[-50:],  # 保留最近50个
                "rolling_freq": freq,
                "markov_state": state,
            }
        return result

    @staticmethod
    def _markov_state(omission: int) -> str:
        """马尔可夫状态判定"""
        if omission <= 3:
            return "H"  # 热
        elif omission <= 8:
            return "W"  # 温
        elif omission <= 15:
            return "C"  # 冷
        else:
            return "X"  # 极冷

    def _compute_layer2(self, history: List[KL8Draw]) -> Dict[str, List]:
        """Layer 2: 区间指标"""
        sum_values = []
        spans = []
        ac_values = []
        zone_counts = {f"zone_{i}": [] for i in range(8)}

        for draw in history:
            sum_values.append(draw.sum_value)
            spans.append(draw.span)
            ac_values.append(self._compute_ac(draw.numbers))
            for i, c in enumerate(draw.zone_counts):
                zone_counts[f"zone_{i}"].append(c)

        result = {
            "sum_value": sum_values,
            "span": spans,
            "ac_value": ac_values,
        }
        result.update(zone_counts)
        return result

    @staticmethod
    def _compute_ac(numbers: List[int]) -> int:
        """计算AC值(号码复杂度)"""
        diffs = set()
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                diffs.add(abs(numbers[j] - numbers[i]))
        return len(diffs) - (len(numbers) - 1)

    def _detect_anomalies(
        self, layer2: Dict[str, List], history: List[KL8Draw]
    ) -> List[Dict]:
        """Z-score异常点检测

        注意：layer2 时序按 history 顺序（降序），即 index 0 = 最新期
        所以 arr[i] 对应 history[i]
        """
        anomalies = []
        for metric, values in layer2.items():
            if len(values) < 10:
                continue
            arr = np.array(values[:50], dtype=float)  # 最近50期
            mean = arr.mean()
            std = arr.std()
            if std == 0:
                continue
            for i, v in enumerate(arr[:10]):  # 检查最近10期
                z = (v - mean) / std
                if abs(z) > self.config.z_score_threshold:
                    period_idx = min(i, len(history) - 1)
                    anomalies.append({
                        "period": history[period_idx].period,
                        "layer": 2,
                        "metric": metric,
                        "z_score": float(z),
                        "value": float(v),
                    })
        return anomalies

    def _compute_fft_period(self, values: List) -> float:
        """FFT频谱分析主周期 (V3.1: 过滤过短周期)"""
        if len(values) < self.config.fft_min_periods:
            return 0.0
        arr = np.array(values[:100], dtype=float)
        arr = arr - arr.mean()
        # 窗口函数
        window = np.hanning(len(arr))
        arr = arr * window
        fft_vals = np.abs(np.fft.rfft(arr))
        if len(fft_vals) < 2:
            return 0.0
        # 排除直流分量
        fft_vals[0] = 0
        # V3.1: 排除过短周期(周期<3期的频率分量无意义)
        # 频率索引 i 对应周期 = N/i，周期<3 → i > N/3
        n = len(arr)
        min_period = 3
        max_freq_idx = n // min_period  # 超过此索引的周期都<3期
        fft_vals_filtered = fft_vals.copy()
        if max_freq_idx < len(fft_vals_filtered):
            fft_vals_filtered[max_freq_idx:] = 0
        
        dominant_freq_idx = np.argmax(fft_vals_filtered)
        if dominant_freq_idx == 0:
            return 0.0
        return float(n / dominant_freq_idx)
