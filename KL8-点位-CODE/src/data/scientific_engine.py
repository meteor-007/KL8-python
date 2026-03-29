import os
import re
from collections import defaultdict

class ScientificEngine:
    """
    点位流形科学演化引擎 (Manifold Evolution Engine)
    基于离散动力学原理，分析点位矩阵的空间稳定性与跨系统共振。
    """
    
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def load_matrix_points(self, date_str, source_type="data1"):
        """从专家文本中提取 4x4 矩阵的物理坐标点"""
        file_path = os.path.join(self.base_dir, date_str, f"{date_str}-{source_type}.txt")
        if not os.path.exists(file_path):
            return {}
        
        points = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and "矩阵" not in l]
                # 将点位解析为 (矩阵ID, 行, 列) -> 数值
                for ri, line in enumerate(lines):
                    block_idx = ri // 4
                    row_in_block = ri % 4
                    # 处理 "N1 N2 | N3 N4" 格式
                    if "|" in line:
                        parts = line.split("|")
                        left = parts[0].split()
                        right = parts[1].split()
                        # 左侧 4x4
                        for ci, val in enumerate(left):
                            if val and val.isdigit():
                                points[(block_idx, row_in_block, ci, "L")] = val.zfill(2)
                        # 右侧 4x4
                        for ci, val in enumerate(right):
                            if val and val.isdigit():
                                points[(block_idx, row_in_block, ci, "R")] = val.zfill(2)
        except Exception as e:
            print(f"[!] 科学引擎解析异常: {e}")
        return points

    def analyze_evolution(self, latest_date, prev_date):
        """执行流形演化分析：计算偏移率与共振密度"""
        results = {
            "drift_rate": 1.0,
            "resonance_nodes": [],
            "entropy_state": "高熵 (不稳定)"
        }
        
        # 加载数据
        l1 = self.load_matrix_points(latest_date, "data1")
        l2 = self.load_matrix_points(latest_date, "data2")
        p1 = self.load_matrix_points(prev_date, "data1") if prev_date else {}
        
        if not l1 or not l2:
            return results
            
        # 1. 计算共振节点 (跨系统探测一致性)
        resonance = []
        for pos, val in l1.items():
            if val == l2.get(pos):
                resonance.append(val)
        results["resonance_nodes"] = sorted(list(set(resonance)))
        
        # 2. 计算流形偏离度 (时序稳定性)
        if p1:
            matches = sum(1 for pos, val in l1.items() if val == p1.get(pos))
            results["drift_rate"] = 1.0 - (matches / len(l1)) if l1 else 1.0
        
        # 3. 评估系统熵能
        if results["drift_rate"] < 0.3:
            results["entropy_state"] = "低熵稳定态"
        elif results["drift_rate"] < 0.6:
            results["entropy_state"] = "亚稳平衡态"
        else:
            results["entropy_state"] = "高熵耗散态"
            
        return results

if __name__ == "__main__":
    # 测试代码
    engine = ScientificEngine(r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum")
    res = engine.analyze_evolution("20260325", "20260324")
    print(f"流形分析结果: {res}")
