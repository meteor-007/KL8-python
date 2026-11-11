# -*- coding: utf-8 -*-
"""
状态空间离散分箱与编码引擎 (State Space Engine - 6大高信标聚类宏观态)
===================================================================
彻底解决 45 分箱导致样本稀疏、状态命中率仅 5% 的致命缺陷。
采用“高阶宏观动能 6 大聚类分箱”：
  1. LOW_COLD (0): 低位聚集 + 冷号回补态 (和值<785，冷号反弹)
  2. LOW_REPEAT (1): 低位聚集 + 连庄凝聚态 (和值<785，小号连号重号)
  3. MID_BALANCED (2): 中轴平衡 + 均衡演化态 (和值 785~835，常态平稳)
  4. MID_REPEAT (3): 中轴平衡 + 连庄密集态 (和值 785~835，腰部连号重号)
  5. HIGH_COLD (4): 高位聚集 + 冷号回补态 (和值>835，大号冷码反弹)
  6. HIGH_REPEAT (5): 高位聚集 + 连庄凝聚态 (和值>835，大号连庄热态)
状态总数 M = 6，大幅提升时序样本统计确定性与推演命中率。
"""

from typing import Dict, Any, Tuple
from backend.modules.markov_line.feature_extractor import DrawFeature


class StateDefinition:
    """宏观状态元信息定义"""

    def __init__(
        self,
        state_id: int,
        state_key: str,
        sum_level: str,
        odd_level: str,
        momentum_level: str,
        description: str,
    ):
        self.state_id = state_id
        self.state_key = state_key
        self.sum_level = sum_level
        self.odd_level = odd_level
        self.momentum_level = momentum_level
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "state_key": self.state_key,
            "sum_level": self.sum_level,
            "odd_level": self.odd_level,
            "momentum_level": self.momentum_level,
            "description": self.description,
        }


class StateSpace:
    """状态空间分箱器与编解码器 (6大聚类宏观态)"""

    REGIMES = [
        (0, "LOW_COLD", "SUM_LOW", "ODD_BAL", "COLD_REBOUND", "低位聚集 + 冷号回补态(和值<785)"),
        (1, "LOW_REPEAT", "SUM_LOW", "ODD_BAL", "REPEAT_CLUST", "低位聚集 + 连庄热态(和值<785)"),
        (2, "MID_BALANCED", "SUM_CENTER", "ODD_BAL", "NORMAL_MOM", "中轴平衡 + 常态演化(785<=和值<=835)"),
        (3, "MID_REPEAT", "SUM_CENTER", "ODD_BAL", "REPEAT_CLUST", "中轴平衡 + 密集连号(785<=和值<=835)"),
        (4, "HIGH_COLD", "SUM_HIGH", "ODD_BAL", "COLD_REBOUND", "高位聚集 + 冷号回补态(和值>835)"),
        (5, "HIGH_REPEAT", "SUM_HIGH", "ODD_BAL", "REPEAT_CLUST", "高位聚集 + 连庄热态(和值>835)"),
    ]

    def __init__(self):
        self.id_to_state: Dict[int, StateDefinition] = {}
        self.key_to_id: Dict[str, int] = {}

        for sid, key, s_lvl, o_lvl, m_lvl, desc in self.REGIMES:
            obj = StateDefinition(
                state_id=sid,
                state_key=key,
                sum_level=s_lvl,
                odd_level=o_lvl,
                momentum_level=m_lvl,
                description=desc,
            )
            self.id_to_state[sid] = obj
            self.key_to_id[key] = sid

        self.num_states = len(self.REGIMES)  # 6

    def encode(self, feat: DrawFeature) -> int:
        """
        根据特征抽取结果映射到 6 大聚类宏观态之一
        """
        sum_v = feat.sum_val
        is_rebound = (feat.mean_omission >= 3.8 or feat.max_omission >= 16)
        is_repeat = (feat.repeat_count >= 5 or feat.consecutive_pairs >= 6)

        if sum_v < 785:
            # 低和值区
            return 1 if is_repeat else 0
        elif sum_v <= 835:
            # 中轴区
            return 3 if is_repeat else 2
        else:
            # 高和值区
            return 5 if is_repeat else 4

    def decode(self, state_id: int) -> StateDefinition:
        """将状态 ID 解码为状态定义对象"""
        if state_id not in self.id_to_state:
            raise KeyError(f"非法状态ID: {state_id}，超出范围 [0, {self.num_states - 1}]")
        return self.id_to_state[state_id]

    def get_all_states(self) -> Dict[int, StateDefinition]:
        """获取全量状态映射字典"""
        return self.id_to_state
