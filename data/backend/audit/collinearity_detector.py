import numpy as np
import logging
from typing import Dict, List, Tuple

# DEPRECATED (v3.0): 旧日报共线性预警专用，主流程不再调用。

logger = logging.getLogger("CollinearityDetector")

class CollinearityDetector:
    """
    多重共线性特征正交化阻断器 (Collinearity Orthogonalization Blocker)
    监控不同 Plan 提取的特征/打分是否高度线性相关（方差膨胀）。
    如果 Pearson 相关系数 > 0.85，抛出警告，防止白噪声由于相关特征的共振被放大。
    """
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def _extract_vector(self, scores: Dict) -> np.ndarray:
        """从特征或打分字典提取 1-80 号码的固定长度向量"""
        vec = []
        for i in range(1, 81):
            val = scores.get(i, 0.0)
            if isinstance(val, (list, tuple)):
                # 取第一个值或均值
                val = float(val[0]) if len(val) > 0 else 0.0
            vec.append(float(val))
        return np.array(vec)

    def detect(self, plan_results: Dict[str, Dict]) -> List[Tuple[str, str, float]]:
        """
        检测给定计划结果间的共线性。
        :param plan_results: 格式如 {'plan1': {1: 0.5, 2: 0.1...}, 'plan2': {...}}
        :return: 高度相关的计划对 [(planA, planB, correlation_coefficient)]
        """
        keys = list(plan_results.keys())
        n = len(keys)
        if n < 2:
            return []

        vectors = []
        for k in keys:
            vectors.append(self._extract_vector(plan_results[k]))

        warnings = []
        for i in range(n):
            for j in range(i + 1, n):
                v1 = vectors[i]
                v2 = vectors[j]
                
                std1 = np.std(v1)
                std2 = np.std(v2)
                
                # 若某个向量方差为0，跳过
                if std1 < 1e-8 or std2 < 1e-8:
                    continue
                    
                corr = np.corrcoef(v1, v2)[0, 1]
                if abs(corr) > self.threshold:
                    warnings.append((keys[i], keys[j], float(corr)))
                    logger.warning(
                        f"🚨 【多重共线性警告】 特征 {keys[i]} 与 {keys[j]} 的 Pearson相关系数达到 {corr:.4f} "
                        f"(> {self.threshold})！可能引发方差膨胀假信标！"
                    )
        return warnings
