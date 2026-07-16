from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from config.model_config import ModelConfig
from core.data_loader import KL8Draw
from core.road_mapper import road_of

Road = Tuple[int, int, int]


class NumberScorer:
    """按预测分路权重 + 遗漏/冷热 分层推荐/杀号。"""

    def __init__(self, draws: Sequence[KL8Draw], cfg: ModelConfig):
        self.draws = list(draws)
        self.cfg = cfg

    def _omit_map(self) -> Dict[int, int]:
        """距上次出现的期数；从未出现则用 len(draws)。"""
        last_seen = {n: None for n in range(1, 81)}
        for i, d in enumerate(self.draws):
            for n in d.numbers:
                last_seen[n] = i
        n_draws = len(self.draws)
        omit = {}
        for n in range(1, 81):
            if last_seen[n] is None:
                omit[n] = n_draws
            else:
                omit[n] = n_draws - 1 - last_seen[n]
        return omit

    def _freq_map(self, window: int = 100) -> Dict[int, float]:
        recent = self.draws[-window:] if self.draws else []
        if not recent:
            return {n: 0.0 for n in range(1, 81)}
        counts = {n: 0 for n in range(1, 81)}
        for d in recent:
            for n in d.numbers:
                counts[n] += 1
        denom = float(len(recent))
        return {n: counts[n] / denom for n in range(1, 81)}

    def score(
        self,
        predicted_road: Road,
        ml_proba: Optional[Dict[int, float]] = None,
    ) -> dict:
        omit = self._omit_map()
        freq = self._freq_map(self.cfg.window_short)
        max_omit = max(omit.values()) or 1

        rec_scores: Dict[int, float] = {}
        kill_scores: Dict[int, float] = {}

        for n in range(1, 81):
            r = road_of(n)
            road_w = predicted_road[r] / 20.0
            omit_n = omit[n] / max_omit
            freq_n = freq[n]
            ml = 0.0
            if ml_proba and n in ml_proba:
                ml = ml_proba[n]

            # 推荐：高分路权重 + 适中遗漏回补 + 非过热
            rec = road_w * 0.55 + omit_n * 0.25 + (1.0 - min(freq_n, 1.0)) * 0.15 + ml * 0.3
            # 杀号：低分路权重 + 过热/刚开出
            kill = (1.0 - road_w) * 0.55 + (1.0 - omit_n) * 0.25 + freq_n * 0.15 - ml * 0.2

            rec_scores[n] = rec
            kill_scores[n] = kill

        # 推荐按分降序，稳定用号码升序打破平局
        ranked_rec = sorted(rec_scores.keys(), key=lambda n: (-rec_scores[n], n))
        need_rec = self.cfg.rec_high + self.cfg.rec_mid + self.cfg.rec_low
        picked_rec = ranked_rec[:need_rec]
        rec_high = picked_rec[: self.cfg.rec_high]
        rec_mid = picked_rec[self.cfg.rec_high : self.cfg.rec_high + self.cfg.rec_mid]
        rec_low = picked_rec[
            self.cfg.rec_high + self.cfg.rec_mid : need_rec
        ]

        rec_set = set(picked_rec)
        # 杀号从剩余低推荐分（高 kill 分）取
        ranked_kill = sorted(
            (n for n in range(1, 81) if n not in rec_set),
            key=lambda n: (-kill_scores[n], n),
        )
        need_kill = self.cfg.kill_high + self.cfg.kill_mid
        picked_kill = ranked_kill[:need_kill]
        kill_high = picked_kill[: self.cfg.kill_high]
        kill_mid = picked_kill[self.cfg.kill_high : need_kill]

        return {
            "rec_high": rec_high,
            "rec_mid": rec_mid,
            "rec_low": rec_low,
            "kill_high": kill_high,
            "kill_mid": kill_mid,
            "scores_rec": rec_scores,
            "scores_kill": kill_scores,
        }
