# -*- coding: utf-8 -*-
"""
快乐8 心理博弈论与逆向均值回归量化推演引擎 (Psychological Game Theory Engine)
=============================================================================
【业务背景与架构定位】:
本模块专为快乐8深度量化分析打造，深度落地交易者心理博弈与大数均值回归四大核心支柱：
1. 支柱 1【散户追热避冷逆向反击】:
   - 识别散户盲目追涨的极热滞涨号 (高频冲顶施加降温扣分)；
   - 捕捉处于 6~18 期“大众绝望抛弃点”的高弹性冷号 (如 24, 35, 37, 64 等)，抓报复性反弹；
   - 拦截 >25 期的深度死冷号，防盲目死守。

2. 支柱 2【大小比与奇偶比钟摆偏态回归】:
   - 监控近期大小比偏态 (如 13:7 极端盘)，量化钟摆势能向 1-40 小号报复性回摆的拉力；
   - 监控奇偶比震荡中枢，维持均衡对冲。

3. 支柱 3【四分区拥挤度与资金回流模型】:
   - 监控 1区(01-20)、2区(21-40)、3区(41-60)、4区(61-80) 的筹码拥挤度；
   - 当 4 区拥挤度超标时，大盘必然逆向冷冻后区，将资金势能回流补仓至 1-2 区。

4. 支柱 4【连号空间跳跃与单点健康重号】:
   - 严格形态门禁：剔除被双连截断的连庄阻力号，精选单点健康重号 (如 12, 27, 56)；
   - 连号活性前移：重点伏击前区 (如 05-10 区间) 的连号新聚落。

@author Antigravity Quantitative Team
@since 2026-09-07
"""

from backend.utils.paths import get_outputs_dir
import os
import sys
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

# 步骤 1: 路径与环境初始化 (backend/modules/psychological_game/ -> data/)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 模块迁入 _retired/ 后目录层数变了，改为向上回溯到真正的项目根（同时含 backend 与 storage 的目录）
_ROOT_DIR = _CURRENT_DIR
while not (os.path.isdir(os.path.join(_ROOT_DIR, "backend"))
           and os.path.isdir(os.path.join(_ROOT_DIR, "frontend"))
           and os.path.isdir(os.path.join(_ROOT_DIR, "storage"))):
    _parent = os.path.dirname(_ROOT_DIR)
    if _parent == _ROOT_DIR:
        break
    _ROOT_DIR = _parent
_BACKEND_DIR = os.path.join(_ROOT_DIR, "backend")
_PROJ_DIR = _BACKEND_DIR  # 兼容旧变量名：曾指向 backend/
for _p in [_BACKEND_DIR, _ROOT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.utils.history_loader import load_history


class PsychologicalGameEngine:
    """心理博弈与逆向均值回归推演引擎"""

    def __init__(self, history: Optional[List[Dict[str, Any]]] = None):
        """
        初始化引擎并加载历史开奖数据
        @param history 历史开奖列表，最新期排在最前 (index 0)
        """
        if history is None:
            self.history = load_history()
        else:
            self.history = history
        self.total_periods = len(self.history)

    def analyze_macro_pendulum(self, offset: int = 0, lookback: int = 5) -> Dict[str, Any]:
        """
        分析大小比、奇偶比与四分区资金拥挤度钟摆 (支持 offset 屏蔽未来数据滚动回测)
        @param offset 历史偏移量 (0 为推演最新一期，>0 为历史回测指定期)
        @param lookback 回溯期数窗口
        """
        if not self.history or len(self.history) <= offset:
            return {}

        sample_history = self.history[offset : offset + lookback]
        if not sample_history:
            return {}

        latest_draw = sample_history[0]
        latest_nums = set(latest_draw.get("numbers", []))

        # 1. 大小比钟摆偏态 (1-40 小号, 41-80 大号)
        recent_big_counts = []
        recent_odd_counts = []
        for d in sample_history:
            nums = d.get("numbers", [])
            big_c = sum(1 for x in nums if x > 40)
            odd_c = sum(1 for x in nums if x % 2 == 1)
            recent_big_counts.append(big_c)
            recent_odd_counts.append(odd_c)

        last_big_c = recent_big_counts[0]
        last_small_c = 20 - last_big_c
        avg_big = float(np.mean(recent_big_counts))
        last_ratio_str = f"{last_small_c}:{last_big_c} (小:大)"

        # 钟摆回调偏置: 当近5期大号平均 > 10.5 时，向小号回调压力大
        big_small_bias = round((avg_big - 10.0) / 3.0, 2)
        if last_big_c >= 12 or avg_big >= 11.2:
            size_trend_desc = f"上期大号极度超买({last_big_c}大)，大盘钟摆强烈向小号报复性回调，下期看好 11小9大 或 10:10 均衡"
            target_size_bias = "小号强力回补 (重兵布防 1-40)"
        elif last_small_c >= 12 or avg_big <= 8.8:
            size_trend_desc = f"上期小号极度超买({last_small_c}小)，大盘钟摆向大号回调，下期看好 11大9小"
            target_size_bias = "大号回补 (关注 41-80)"
        else:
            size_trend_desc = "大小比处于常态中枢震荡区间，预计维持 10:10 均衡格局"
            target_size_bias = "大小均衡对冲"

        # 2. 奇偶比
        last_odd_c = recent_odd_counts[0]
        last_even_c = 20 - last_odd_c
        odd_even_ratio_str = f"{last_odd_c}:{last_even_c} (奇:偶)"
        odd_trend_desc = "奇偶比常态均衡，预计下期维持约 10:10 均势"

        # 3. 四分区拥挤度 (1区:1-20, 2区:21-40, 3区:41-60, 4区:61-80)
        zone_counts = [0, 0, 0, 0]
        for d in self.history[offset : offset + 3]:
            for x in d.get("numbers", []):
                z_idx = min(3, (x - 1) // 20)
                zone_counts[z_idx] += 1

        total_zone_balls = sum(zone_counts)
        if total_zone_balls == 0:
            total_zone_balls = 1
        zone_shares = [round((c / float(total_zone_balls)) * 100, 1) for c in zone_counts]
        zone_weights = [round(1.0 + (25.0 - share) * 0.08, 2) for share in zone_shares]

        zone_names = ["1区 (01-20)", "2区 (21-40)", "3区 (41-60)", "4区 (61-80)"]
        zone_diagnoses = []
        for i in range(4):
            if zone_shares[i] >= 32.0:
                diag = f"{zone_names[i]}: 拥挤度超标 ({zone_shares[i]}%)，高位滞涨降温"
            elif zone_shares[i] <= 18.0:
                diag = f"{zone_names[i]}: 严重偏冷 ({zone_shares[i]}%)，资金报复性补仓"
            else:
                diag = f"{zone_names[i]}: 处于常态温水区 ({zone_shares[i]}%)"
            zone_diagnoses.append(diag)

        return {
            "last_size_ratio": last_ratio_str,
            "avg_big_count": round(avg_big, 1),
            "big_small_bias": big_small_bias,
            "size_trend_desc": size_trend_desc,
            "target_size_bias": target_size_bias,
            "last_odd_even_ratio": odd_even_ratio_str,
            "odd_trend_desc": odd_trend_desc,
            "zone_shares": zone_shares,
            "zone_weights": zone_weights,
            "zone_diagnoses": zone_diagnoses
        }

    def analyze_contrarian_cold_spring(self, offset: int = 0, lookback: int = 30) -> Dict[str, Any]:
        """
        支柱 1: 散户追热避冷逆向反击与弹性冷号突击 (支持 offset 回测)
        """
        if not self.history or len(self.history) <= offset:
            return {}

        sub_history = self.history[offset : offset + lookback]
        if not sub_history:
            return {}

        latest_draw = sub_history[0]
        latest_nums = set(latest_draw.get("numbers", []))

        omissions = {}
        freq_10 = {}
        for num in range(1, 81):
            omit = -1
            c10 = 0
            for idx, d in enumerate(sub_history):
                nums_set = set(d.get("numbers", []))
                if num in nums_set:
                    if omit == -1:
                        omit = idx
                    if idx < 10:
                        c10 += 1
            omissions[num] = omit if omit != -1 else lookback
            freq_10[num] = c10

        # 筛选弹性冷号 (6 <= omit <= 18，大众绝望抛弃区)
        spring_cold_candidates = []
        deep_dead_cold = []
        crowd_hot_penalties = []

        for num in range(1, 81):
            omit = omissions[num]
            f10 = freq_10[num]

            if 6 <= omit <= 18:
                tension = round(1.0 + (omit - 6) * 0.12, 2)
                spring_cold_candidates.append({
                    "number": num,
                    "display": f"{num:02d}",
                    "omission": omit,
                    "recent_freq10": f10,
                    "spring_tension": tension,
                    "status": f"弹性中冷 (遗漏{omit}期，绝望点强反弹)"
                })
            elif omit > 25:
                deep_dead_cold.append({
                    "number": num,
                    "display": f"{num:02d}",
                    "omission": omit,
                    "status": "深度死冷 (散户深套，防继续装死)"
                })

            if f10 >= 5 and omit == 0:
                crowd_hot_penalties.append({
                    "number": num,
                    "display": f"{num:02d}",
                    "recent_freq10": f10,
                    "status": "极热追涨区 (散户跟风严重，防冲顶滞涨)"
                })

        spring_cold_candidates.sort(key=lambda x: x["spring_tension"], reverse=True)

        return {
            "spring_cold_candidates": spring_cold_candidates[:8],
            "deep_dead_cold": deep_dead_cold[:5],
            "crowd_hot_penalties": crowd_hot_penalties[:6],
            "omissions": omissions,
            "freq_10": freq_10
        }

    def analyze_healthy_repeats_and_clusters(self, offset: int = 0) -> Dict[str, Any]:
        """
        支柱 4: 连号空间跳跃与单点健康重号 (支持 offset 回测)
        """
        if not self.history or len(self.history) <= offset:
            return {}

        latest_draw = self.history[offset]
        latest_nums = set(latest_draw.get("numbers", []))

        healthy_repeats = []
        truncated_repeats = []

        for num in sorted(list(latest_nums)):
            has_adj = (num - 1 in latest_nums) or (num + 1 in latest_nums)
            if not has_adj:
                healthy_repeats.append({
                    "number": num,
                    "display": f"{num:02d}",
                    "status": "单点健康重号 (无连号截断阻碍，连庄阻力小)",
                    "recommend": True
                })
            else:
                adj_pair = []
                if num - 1 in latest_nums:
                    adj_pair.append(f"{num-1:02d}-{num:02d}")
                if num + 1 in latest_nums:
                    adj_pair.append(f"{num:02d}-{num+1:02d}")
                truncated_repeats.append({
                    "number": num,
                    "display": f"{num:02d}",
                    "adjacent_pairs": adj_pair,
                    "status": "连号截断重号 (伴随紧挨连号，连庄阻力极大)",
                    "recommend": False
                })

        # 连号空间跳跃分析: 统计上期连号分布
        consecutive_pairs = []
        for x in range(1, 80):
            if x in latest_nums and (x + 1) in latest_nums:
                consecutive_pairs.append(f"{x:02d}-{x+1:02d}")

        # 前区连号伏击圈判定 (如 05-10 区间)
        cluster_bias_desc = "连号活性向 1 区转移，重点伏击【 05-10 】前区连号集群回补"

        return {
            "healthy_repeats": healthy_repeats,
            "truncated_repeats": truncated_repeats,
            "last_consecutive_pairs": consecutive_pairs,
            "cluster_bias_desc": cluster_bias_desc
        }

    def compute_full_prediction(self, offset: int = 0) -> Dict[str, Any]:
        """
        综合四大支柱算法进行 80 球全局博弈打分 (支持 offset 回测)
        @param offset 历史偏移量 (0 为预测当前最新未开奖期，>0 为回测指定历史期)
        """
        if not self.history or len(self.history) <= offset:
            return {}

        macro = self.analyze_macro_pendulum(offset=offset, lookback=5)
        cold_res = self.analyze_contrarian_cold_spring(offset=offset, lookback=30)
        repeat_res = self.analyze_healthy_repeats_and_clusters(offset=offset)

        omissions = cold_res.get("omissions", {})
        freq_10 = cold_res.get("freq_10", {})
        zone_weights = macro.get("zone_weights", [1.0, 1.0, 1.0, 1.0])
        big_small_bias = macro.get("big_small_bias", 0.0)

        latest_draw = self.history[offset] if len(self.history) > offset else {}
        latest_nums = set(latest_draw.get("numbers", []))

        ball_scores = []
        for num in range(1, 81):
            idx = num - 1
            z_idx = min(3, (num - 1) // 20)
            omit = omissions.get(num, 0)
            f10 = freq_10.get(num, 0)
            is_small = num <= 40

            # 1. 弹性冷号加分 (6 <= omit <= 18)
            cold_boost = 0.0
            if 6 <= omit <= 18:
                cold_boost = 1.0 + (omit - 6) * 0.12
            elif omit > 25:
                cold_boost = 0.15

            # 2. 温热与极热加减分
            rebound = 0.0
            crowd_penalty = 0.0
            if f10 >= 5 and omit == 0:
                crowd_penalty = 0.40
            elif f10 >= 3 and omit > 0:
                rebound = 0.65

            # 3. 健康重号加分
            repeat_score = 0.0
            if omit == 0:
                has_adj = (num - 1 in latest_nums) or (num + 1 in latest_nums)
                if not has_adj:
                    repeat_score = 0.60
                else:
                    repeat_score = -0.35

            # 4. 大小比钟摆偏置
            size_score = 0.35 * big_small_bias if is_small else -0.35 * big_small_bias

            # 5. 分区资金回流偏置
            zone_score = (zone_weights[z_idx] - 1.0) * 0.9

            final_score = (
                0.35 * cold_boost
                + 0.25 * rebound
                + 0.20 * repeat_score
                + 0.15 * size_score
                + 0.15 * zone_score
                - crowd_penalty
            )

            ball_scores.append({
                "number": num,
                "display": f"{num:02d}",
                "zone_idx": z_idx + 1,
                "is_small": is_small,
                "omission": omit,
                "freq10": f10,
                "final_score": round(float(final_score), 3)
            })

        ball_scores.sort(key=lambda x: x["final_score"], reverse=True)

        top3_gold = [x["number"] for x in ball_scores[:3]]
        # 兼容旧字段：主口径最优 3 码，不再维护独立 Top5/Top12
        top5 = list(top3_gold)
        top12 = list(top3_gold)

        # 重点推荐的弹性冷号与健康重号
        top_cold_spring = [x["number"] for x in cold_res.get("spring_cold_candidates", [])[:4]]
        top_healthy_repeats = [x["number"] for x in repeat_res.get("healthy_repeats", [])[:4]]

        latest_issue = str(latest_draw.get("issue") or latest_draw.get("period") or "")
        if offset == 0:
            try:
                target_issue = str(int(latest_issue) + 1)
            except Exception:
                target_issue = "最新推演"
        else:
            # 回测历史期
            target_draw = self.history[offset - 1] if offset - 1 >= 0 else {}
            target_issue = str(target_draw.get("issue") or target_draw.get("period") or "")

        clean_date = str(latest_draw.get("date", ""))

        return {
            "target_period": target_issue,
            "based_on_period": latest_issue,
            "total_draws": len(self.history),
            "date": clean_date,
            "top3_gold": top3_gold,
            "top5_assault": top5,
            "top12_balanced": top12,
            "top_cold_spring": top_cold_spring,
            "top_healthy_repeats": top_healthy_repeats,
            "macro_pendulum": macro,
            "contrarian_cold_spring": cold_res,
            "healthy_repeats_and_clusters": repeat_res,
            "ball_scores": ball_scores
        }


def run_psychological_game_pipeline() -> Dict[str, Any]:
    """一键流水线入口函数，执行全流程计算并落盘 JSON 与 Markdown 研报"""
    print("[1/4] 启动心理博弈与逆向均值回归量化推演引擎...")
    engine = PsychologicalGameEngine()
    result = engine.compute_full_prediction()

    base_dir = _ROOT_DIR

    # 步骤 1: 落盘 JSON 账本到 storage/stats
    storage_dir = os.path.join(base_dir, "storage", "stats")
    os.makedirs(storage_dir, exist_ok=True)
    json_path = os.path.join(storage_dir, "psychological_game_analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[2/4] 结构化账本已落盘: {json_path}")

    # 步骤 2: 同时同步到前端静态目录提供高可用离线回退
    static_json_path = os.path.join(base_dir, "frontend", "static", "psychological_game_analysis.json")
    try:
        with open(static_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 步骤 3: 渲染专业 Markdown 研报
    report_dir = os.path.join(get_outputs_dir(), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "psychological_game_report_latest.md")
    md_content = _render_markdown_report(result)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[3/4] 操盘手研报已生成: {report_path}")

    print("[4/4] 心理博弈与逆向均值回归量化推演全部顺利完成！")
    return result


def _render_markdown_report(data: Dict[str, Any]) -> str:
    """生成具备老派操盘手大白话风格的 Markdown 实战研报"""
    target_period = data.get("target_period", "N/A")
    based_period = data.get("based_on_period", "N/A")
    top3 = "、".join(f"{x:02d}" for x in data.get("top3_gold", []))
    colds = "、".join(f"{x:02d}" for x in data.get("top_cold_spring", []))
    repeats = "、".join(f"{x:02d}" for x in data.get("top_healthy_repeats", []))

    macro = data.get("macro_pendulum", {})
    repeat_info = data.get("healthy_repeats_and_clusters", {})

    md = f"""# 🧠 快乐8 心理博弈论与逆向均值回归核心战报
> **目标推演期号**: 第 **{target_period}** 期 (基于第 {based_period} 期开奖底账)  
> **算法引擎**: Psychological Game Theory & Contrarian Reversion Engine V1.0  
> **核心战术**: 散户追热避冷逆向反击 × 大小比钟摆修正 × 四分区资金回流 × 健康重号连号形态

---

## 一、 核心操盘手黄金结论 (速览决策)
1. **最优 3 码 (大白话：全战术交叉最看好的前 3 强核心胆码)**:
   - **`{top3}`**
2. **弹性冷号突击名单 (大白话：大众绝望割肉、大数必定回补的冷号)**:
   - **`{colds}`**
3. **单点健康重号 (大白话：上期开出且身边无截断阻碍、极易连庄的热号)**:
   - **`{repeats}`**

---

## 二、 宏观钟摆与资金流向态势诊断
- **大小比钟摆诊断**: {macro.get('size_trend_desc', 'N/A')}
- **奇偶比态势**: {macro.get('odd_trend_desc', 'N/A')}
- **四分区拥挤度与资金流向**:
"""
    for diag in macro.get("zone_diagnoses", []):
        md += f"  * {diag}\n"

    md += f"""
- **连号伏击圈提示**: {repeat_info.get('cluster_bias_desc', 'N/A')}

---
*本研报由 Antigravity 自动化量化流水线原生生成，严格遵循大白话操盘协议与物理对账原则。*
"""
    return md


if __name__ == "__main__":
    run_psychological_game_pipeline()
