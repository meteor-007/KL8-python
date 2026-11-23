# 彩票科学选号与缩水分析系统 —— 详细开发设计文档 (DDD)

> **标准版本**：v1.0  
> **设计依据**：系统架构设计文档 (SDD) & Gail Howard 算法体系  
> **归档位置**：`C:\D-pan\Dpanqianyi\sijing\彩票科学选号与缩水系统_详细开发设计文档(DDD).md`

---

## 1. 核心模块类与接口设计

### 1.1 基础领域模型 (Domain Models)

```python
# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import datetime

class GameType(str, Enum):
    PICK_6 = "PICK_6"      # 选6型 (双色球红球, 6/49)
    PICK_5 = "PICK_5"      # 选5型 (大乐透前区, 5/35)
    PICK_7 = "PICK_7"      # 选7型 (七乐彩)
    KENO = "KENO"          # 基诺/快乐8

@dataclass(frozen=True)
class LotteryGameSpec:
    game_id: str
    name: str
    game_type: GameType
    main_pool: int         # 主区球总数 (如 33, 49)
    main_pick: int         # 每注选号数 (如 6, 5)
    extra_pool: int = 0    # 次区球总数 (如 16, 12)
    extra_pick: int = 0    # 次区选号数 (如 1, 2)
    
    @property
    def expected_sum(self) -> float:
        return (self.main_pick * (1 + self.main_pool)) / 2.0

@dataclass
class DrawRecord:
    draw_id: str
    draw_date: datetime.date
    main_balls: List[int]
    extra_balls: List[int] = field(default_factory=list)
```

---

## 2. 核心算法实现细节

### 2.1 时序遗漏与状态更新算法 (Skip State Calculator)

```python
import numpy as np

class SkipStateTracker:
    def __init__(self, game_spec: LotteryGameSpec):
        self.spec = game_spec
        self.num_balls = game_spec.main_pool
        # 存储每个球历史以来的完整遗漏序列
        self.skip_histories: Dict[int, List[int]] = {i: [] for i in range(1, self.num_balls + 1)}
        self.current_skips: np.ndarray = np.zeros(self.num_balls + 1, dtype=int)

    def process_draw(self, draw: DrawRecord):
        hit_set = set(draw.main_balls)
        for ball in range(1, self.num_balls + 1):
            if ball in hit_set:
                # 记录本次击中时的遗漏值
                self.skip_histories[ball].append(int(self.current_skips[ball]))
                self.current_skips[ball] = 0
            else:
                self.current_skips[ball] += 1

    def get_skip_features(self, ball: int) -> Dict[str, float]:
        history = self.skip_histories[ball]
        curr = self.current_skips[ball]
        mean_skip = float(np.mean(history)) if history else float(self.spec.main_pool / self.spec.main_pick)
        median_skip = float(np.median(history)) if history else mean_skip
        
        # 判断双底/三倍底形态: 历史最后两次遗漏是否与当前遗漏接近且处于中低位
        double_bottom = False
        if len(history) >= 2:
            if abs(history[-1] - curr) <= 1 and abs(history[-2] - history[-1]) <= 1 and curr <= 6:
                double_bottom = True

        return {
            "current_skip": curr,
            "mean_skip": mean_skip,
            "median_skip": median_skip,
            "skip_deviation": curr / max(1.0, mean_skip),
            "is_double_bottom": 1.0 if double_bottom else 0.0
        }
```

---

### 2.2 最佳号码记分板评分算法 (Scoreboard Engine)

```python
class ScoreboardEngine:
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "golden_skip": 0.35,      # 0~5期黄金遗漏区
            "double_bottom": 0.25,    # 双底形态激励
            "mean_reversion": 0.20,   # 中期冷热回归动量
            "adjacent_hit": 0.20      # 相邻号/斜连号牵引
        }

    def compute_ball_score(self, ball: int, features: Dict[str, float], last_draw_balls: List[int]) -> float:
        score = 0.0
        curr_skip = features["current_skip"]
        
        # 1. 黄金遗漏评分 (0~5期遗漏获得高斯衰减高分)
        if curr_skip == 0:
            score += self.weights["golden_skip"] * 0.85  # 重号适度奖励
        elif 1 <= curr_skip <= 3:
            score += self.weights["golden_skip"] * 1.0   # 1~3期最高分
        elif 4 <= curr_skip <= 6:
            score += self.weights["golden_skip"] * 0.7
        else:
            score += self.weights["golden_skip"] * max(0.0, 1.0 - (curr_skip - 6) * 0.15)
            
        # 2. 双底/三倍底形态
        if features.get("is_double_bottom", 0.0) > 0.5:
            score += self.weights["double_bottom"] * 1.0
            
        # 3. 相邻数牵引 (上期开奖号的 ±1 邻号)
        if any(abs(ball - b) == 1 for b in last_draw_balls):
            score += self.weights["adjacent_hit"] * 1.0

        return round(score * 100.0, 2)
```

---

### 2.3 旋转矩阵生成与定胆置换引擎 (Smart Wheel Engine)

```python
class WheelTemplate:
    def __init__(self, template_id: str, pool_size: int, pick_count: int, matrix: List[List[int]], guarantee: str):
        self.template_id = template_id
        self.pool_size = pool_size          # 模板所需总号码数 L
        self.pick_count = pick_count        # 每注号码数 K
        self.matrix = matrix                # 0-indexed 相对索引矩阵
        self.guarantee = guarantee          # 保奖承诺描述 如 "5-if-5"

class SmartWheelGenerator:
    @staticmethod
    def generate(template: WheelTemplate, pool: List[int], bankers: Optional[List[int]] = None) -> List[List[int]]:
        bankers = bankers or []
        needed_free = template.pool_size - len(bankers)
        free_pool = [x for x in pool if x not in bankers]
        
        if len(free_pool) < needed_free:
            raise ValueError(f"候选号码池不足! 需 {needed_free} 个非胆码，实际提供 {len(free_pool)} 个")

        # 映射构建: 0..B-1 为胆码, B..L-1 为自由号码
        mapping = bankers + free_pool[:needed_free]
        
        tickets = []
        for row in template.matrix:
            ticket = sorted([mapping[idx] for idx in row])
            tickets.append(ticket)
            
        return tickets
```

---

### 2.4 高性能位运算多级过滤管道 (Fast Bitmask Filter Pipeline)

```python
class FastBitmaskFilter:
    def __init__(self, game_spec: LotteryGameSpec):
        self.spec = game_spec
        self.mid = game_spec.main_pool // 2
        
    def filter_batch(
        self,
        tickets: List[List[int]],
        sum_range: Tuple[int, int],
        valid_odd_counts: Tuple[int, ...],
        valid_high_counts: Tuple[int, ...],
        max_consecutive: int = 2,
        max_same_tail: int = 2
    ) -> List[List[int]]:
        valid_tickets = []
        for t in tickets:
            # 1. 和值检查
            s = sum(t)
            if not (sum_range[0] <= s <= sum_range[1]):
                continue
                
            # 2. 奇偶比检查
            odds = sum(1 for x in t if x & 1)
            if odds not in valid_odd_counts:
                continue
                
            # 3. 大小比检查
            highs = sum(1 for x in t if x > self.mid)
            if highs not in valid_high_counts:
                continue
                
            # 4. 最大连号数检查
            cons = 1
            max_cons = 1
            for i in range(len(t) - 1):
                if t[i+1] == t[i] + 1:
                    cons += 1
                    max_cons = max(max_cons, cons)
                else:
                    cons = 1
            if max_cons > max_consecutive:
                continue
                
            # 5. 同尾数检查
            tails = [x % 10 for x in t]
            if max(tails.count(tail) for tail in set(tails)) > max_same_tail:
                continue
                
            valid_tickets.append(t)
            
        return valid_tickets
```

---

## 3. RESTful API 接口设计与规范

### 3.1 `POST /api/v1/analysis/score` (计算当前期最佳号码记分板)
* **Request Body**:
```json
{
  "game_id": "ssq_red",
  "top_n": 15
}
```
* **Response Body**:
```json
{
  "code": 200,
  "data": {
    "tier_1_bankers": [8, 21],
    "tier_2_pool": [3, 7, 12, 14, 19, 23, 26, 29, 31],
    "tier_3_excluded": [2, 11, 33],
    "scoreboard": [
      {"ball": 8, "score": 92.5, "features": {"current_skip": 2, "is_double_bottom": 1}},
      {"ball": 21, "score": 88.0, "features": {"current_skip": 1, "is_double_bottom": 0}}
    ]
  }
}
```

---

### 3.2 `POST /api/v1/wheel/generate-and-filter` (生成旋转矩阵并执行多级过滤)
* **Request Body**:
```json
{
  "game_id": "ssq_red",
  "template_id": "W6-5-5-12",
  "bankers": [8],
  "pool": [3, 7, 8, 12, 14, 19, 21, 23, 26, 28, 29, 31],
  "filter_options": {
    "sum_range": [85, 145],
    "allowed_odd_counts": [2, 3, 4],
    "allowed_high_counts": [2, 3, 4],
    "max_consecutive": 2
  }
}
```
* **Response Body**:
```json
{
  "code": 200,
  "data": {
    "raw_ticket_count": 42,
    "filtered_ticket_count": 18,
    "reduction_rate": "57.14%",
    "tickets": [
      [3, 8, 12, 14, 21, 26],
      [3, 8, 14, 19, 23, 29]
    ]
  }
}
```

---

## 4. 单元测试与验证方案

| 测试用例名称 | 测试目标 | 预期结果 |
| :--- | :--- | :--- |
| `test_skip_state_tracker` | 验证多期开奖遗漏状态的累加与清零准确性 | 命中号遗漏重置为0，其余号遗漏严格+1 |
| `test_wheel_covering_guarantee` | 验证 5-if-5 矩阵在任意 5 个中奖号时的保奖覆盖度 | 遍历所有 $C(12, 5)$ 子集，保奖率 100% 达成 |
| `test_filter_edge_cases` | 验证全奇数/全大数/等差数列是否被 100% 拦截 | 拦截率 100% 无漏网 |
| `test_filter_performance` | 100,000 注组合过滤压力测试 | 执行耗时 $< 50\text{ms}$，内存占用 $< 20\text{MB}$ |
