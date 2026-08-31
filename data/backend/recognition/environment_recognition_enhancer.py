# -*- coding: utf-8 -*-
"""环境识别增强模块 — 迁移至 recognition/ 子树"""
import collections
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple, Any

ENVIRONMENT_CLASSES = {
    0: {'name': '热号爆发期', 'desc': '热号集中', 'weights': {'MK': 0.3, 'EF': 0.4, 'RW': 0.3}},
    1: {'name': '冷号反弹期', 'desc': '冷号反弹', 'weights': {'MK': 0.2, 'EF': 0.5, 'RW': 0.3}},
    2: {'name': '平衡震荡期', 'desc': '分布均匀', 'weights': {'MK': 0.15, 'EF': 0.42, 'RW': 0.42}},
    3: {'name': '趋势加速期', 'desc': '趋势加速', 'weights': {'MK': 0.4, 'EF': 0.3, 'RW': 0.3}},
    4: {'name': '混沌随机期', 'desc': '规律混乱', 'weights': {'MK': 0.25, 'EF': 0.25, 'RW': 0.5}}
}

class EnvironmentRecognizer:
    def __init__(self, n_clusters=5):
        self.n_clusters = n_clusters
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.scaler = StandardScaler()
        self.fitted = False

    def _extract_features(self, history):
        """提取环境特征向量"""
        features = []
        for i in range(len(history) - 4):
            window = history[i:i + 5]
            f = []
            # 热号密度
            counter = collections.Counter(n for h in window for n in h['numbers'])
            f.append(sum(1 for c in counter.values() if c >= 3) / 80.0)
            # 冷号密度
            f.append(sum(1 for n in range(1, 81) if n not in counter) / 80.0)
            # 区间熵
            zc = [0] * 8
            for h in window:
                for n in h['numbers']: zc[(n - 1) // 10] += 1
            total = sum(zc)
            if total > 0:
                probs = [z / total for z in zc if z > 0]
                ent = -sum(p * np.log(p) for p in probs)
                f.append(ent / np.log(8))
            else:
                f.append(0.5)
            # 均值
            all_nums = [n for h in window for n in h['numbers']]
            f.append(np.mean(all_nums) / 80.0 if all_nums else 0.5)
            # 标准差
            f.append(np.std(all_nums) / 80.0 if all_nums else 0.5)
            features.append(f)
        return np.array(features) if features else np.zeros((1, 5))

    def fit(self, history):
        features = self._extract_features(history)
        if len(features) < self.n_clusters:
            self.fitted = False
            return
        features = self.scaler.fit_transform(features)
        self.kmeans.fit(features)
        self.fitted = True

    def predict(self, history):
        if not self.fitted:
            return (2, '平衡震荡期', 0.5, ENVIRONMENT_CLASSES[2])
        features = self._extract_features(history[-6:])
        if len(features) == 0:
            return (2, '平衡震荡期', 0.5, ENVIRONMENT_CLASSES[2])
        features = self.scaler.transform(features)
        label = self.kmeans.predict(features[-1:])[0]
        label = min(label, 4)
        distances = self.kmeans.transform(features[-1:])[0]
        confidence = 1.0 - (distances[label] / (distances.sum() + 1e-8))
        env = ENVIRONMENT_CLASSES.get(label, ENVIRONMENT_CLASSES[2])
        return (label, env['name'], float(confidence), env)

def enhance_environment_recognition(auto_report_module):
    import types
    original_method = auto_report_module.PredictorEngine.generate_report

    def enhanced_generate_report(self):
        try:
            from recognition.simplified_env_recognition import recognize_environment
            env_class, env_name, confidence, config = recognize_environment(self.dc.history)
            print(f"\n[环境识别] {env_name} (置信度:{confidence:.2f})")
            self.current_env_config = config
        except Exception as e:
            print(f"[环境识别] 失败: {e}")
        return original_method(self)

    auto_report_module.PredictorEngine.generate_report = enhanced_generate_report
    return auto_report_module
