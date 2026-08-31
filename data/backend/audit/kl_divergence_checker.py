import numpy as np
import logging
from typing import List, Dict

# DEPRECATED (v3.0): 旧日报物理熔断面板专用，主流程不再调用。

logger = logging.getLogger("KLDivergenceChecker")

class KLDivergenceChecker:
    """
    全局结构性物理突变熔断器 (KL Divergence Circuit Breaker)
    通过监控最近 10 期预测分布与实际开奖分布的 KL 散度，
    判断摇奖机硬件或系统宏观状态是否发生结构性突变（5 Sigma 级别）。
    """
    def __init__(self, history: List[Dict], window_size: int = 10, sigma_threshold: float = 5.0):
        self.history = history
        self.window_size = window_size
        self.sigma_threshold = sigma_threshold
        
    def _calculate_kl_divergence(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        计算 KL(P || Q)，P 为实际分布，Q 为理论/基线分布
        加 1e-10 防止 log(0) 崩溃
        """
        p = np.asarray(p, dtype=float)
        q = np.asarray(q, dtype=float)
        p += 1e-10
        q += 1e-10
        p /= np.sum(p)
        q /= np.sum(q)
        return float(np.sum(p * np.log(p / q)))

    def check_mutation(self) -> Dict[str, any]:
        """
        执行结构性突变检查
        :return: 包含熔断状态、当前KL散度、阈值等信息的字典
        """
        if len(self.history) < self.window_size * 2:
            return {
                "triggered": False,
                "current_kl": 0.0,
                "msg": f"历史数据不足 {self.window_size*2} 期，跳过 KL 熔断检测"
            }
            
        # 1. 构建长线基线分布 (Q)
        baseline_counts = np.zeros(80)
        baseline_hist = self.history[self.window_size:]
        for h in baseline_hist:
            for num in h['numbers']:
                baseline_counts[num - 1] += 1
        baseline_dist = (baseline_counts + 1) / (np.sum(baseline_counts) + 80) # 平滑
        
        # 2. 计算近期各窗口的 KL 散度序列用于评估均值和方差
        kl_history = []
        step = max(1, len(self.history) // 20)
        for i in range(self.window_size, len(self.history) - self.window_size, step):
            window_hist = self.history[i: i + self.window_size]
            w_counts = np.zeros(80)
            for h in window_hist:
                for num in h['numbers']:
                    w_counts[num - 1] += 1
            w_dist = (w_counts + 1) / (np.sum(w_counts) + 80)
            kl_history.append(self._calculate_kl_divergence(w_dist, baseline_dist))
            
        if len(kl_history) < 2:
            kl_mean = 0.1
            kl_std = 0.05
        else:
            kl_mean = np.mean(kl_history)
            kl_std = np.std(kl_history)
            if kl_std < 1e-5:
                kl_std = 1e-5
                
        # 3. 计算最近 10 期的实际分布 (P)
        recent_hist = self.history[:self.window_size]
        recent_counts = np.zeros(80)
        for h in recent_hist:
            for num in h['numbers']:
                recent_counts[num - 1] += 1
        recent_dist = (recent_counts + 1) / (np.sum(recent_counts) + 80)
        
        # 4. 当前 KL 散度
        current_kl = self._calculate_kl_divergence(recent_dist, baseline_dist)
        
        # 5. 计算偏离度 (Z-Score)
        z_score = (current_kl - kl_mean) / kl_std
        
        triggered = z_score > self.sigma_threshold
        
        msg = f"当前KL散度: {current_kl:.4f} (基线: {kl_mean:.4f} ± {kl_std:.4f}), Z-Score: {z_score:.2f} Sigma"
        if triggered:
            msg = f"🚨 【全局熔断触发】 {msg}！突破 {self.sigma_threshold} Sigma 临界点，检测到摇奖机物理规则产生结构性突变！"
            logger.warning(msg)
            
        return {
            "triggered": bool(triggered),
            "current_kl": current_kl,
            "z_score": z_score,
            "msg": msg
        }
