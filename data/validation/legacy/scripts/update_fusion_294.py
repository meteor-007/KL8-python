# -*- coding: utf-8 -*-
import sys

with open("scripts/fusion_engine_294.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace evaluate_all_balls function completely
start_marker = "def evaluate_all_balls(expert_data: ExtractedExpertData) -> List[BallEvaluation]:"
end_marker = "def select_orthogonal_candidates("
start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

new_eval_code = '''def evaluate_all_balls(expert_data: ExtractedExpertData) -> List[BallEvaluation]:
    """
    步骤 3: 结合多源数据（点位图、重边冷高概率、历史同出协力矩阵、Top配对与专家背书）进行全息动态加权评分
    """
    points_set = set(expert_data.points_293)
    repeat_set = set(expert_data.dw_repeat_high)
    edge_set = set(expert_data.dw_edge_high)
    cold_set = set(expert_data.dw_cold_high)
    top_pairs_set = set((p[0], p[1]) for p in expert_data.top_pairs[:100])
    co_mat = expert_data.co_matrix

    evaluations: List[BallEvaluation] = []

    for num in range(1, TOTAL_BALL_COUNT + 1):
        tags: List[str] = []
        score: float = 0.0

        # 特征1: 20枚核心点位基础权重 (+3.5)
        in_pts = num in points_set
        if in_pts:
            score += 3.5
            tags.append("20点位")

        # 特征2: 均值回归反弹下的重码动力学 (+3.0)
        in_rep = num in repeat_set
        if in_rep:
            score += 3.0
            tags.append("重号高概")

        # 特征3: 均值回归反弹下的边码动力学 (+2.5)
        in_edg = num in edge_set
        if in_edg:
            score += 2.5
            tags.append("边号高概")

        # 特征4: 重点关注冷号反弹动力学 (+2.5)
        in_cld = num in cold_set
        if in_cld:
            score += 2.5
            tags.append("关注冷号")

        # 特征5: 点位同出协力中心度 (来自图表15的81x81同出矩阵)
        if co_mat and points_set:
            co_sum = sum(co_mat[num][p] for p in points_set if p != num)
            co_avg = co_sum / len(points_set)
            score += (co_avg - 120.0) * 0.1
            tags.append(f"协力{co_avg:.1f}")

        # 特征6: 历史 Top 配对增益 (来自图表14选2)
        pair_m = sum(1 for p in points_set if (min(num, p), max(num, p)) in top_pairs_set)
        if pair_m > 0:
            score += min(2.5, pair_m * 0.8)
            tags.append(f"配对x{pair_m}")

        # 特征7: 强杀号过滤防守（点位与高概号码豁免杀号）
        is_dk = (num in expert_data.double_kill_set) and (not in_pts) and (not in_rep) and (not in_edg) and (not in_cld)
        is_sk = (num in expert_data.union_kill_set) and (not in_pts) and (not in_rep) and (not in_edg) and (not in_cld) and (not is_dk)

        if is_dk:
            score -= 7.5
            tags.append("⚠️双杀回避")
        elif is_sk:
            score -= 1.8
            tags.append("单杀防守")

        zone_idx = (num - 1) // 10 + 1
        evaluations.append(
            BallEvaluation(
                number=num,
                score=round(score, 2),
                in_points=in_pts,
                in_repeat_high=in_rep,
                in_edge_high=in_edg,
                in_cold_high=in_cld,
                triplet_count=pair_m,
                weighted_triplet_score=round(score, 2),
                in_zhaodan_top20=(pair_m > 0),
                is_double_kill=is_dk,
                is_single_kill=is_sk,
                zone_index=zone_idx,
                recommendation_level="普通",
                feature_tags=tags,
            )
        )

    evaluations.sort(key=lambda x: x.score, reverse=True)
    for idx, e in enumerate(evaluations, 1):
        e.rank = idx
        if idx == 1:
            e.recommendation_level = "全场至尊金胆"
        elif idx <= 2:
            e.recommendation_level = "黄金搭档"
        elif idx <= 5:
            e.recommendation_level = "荣耀主力"
        elif idx <= 10:
            e.recommendation_level = "稳健实战"
        elif idx <= 20:
            e.recommendation_level = "围大底优选"
        elif e.is_double_kill:
            e.recommendation_level = "极危双杀号"

    return evaluations


'''

text = text[:start_idx] + new_eval_code + text[end_idx:]

# 2. Update select_pyramid_triplets to incorporate pairwise co-occurrence synergy
start_trip = "def select_pyramid_triplets("
end_trip = "def generate_commercial_excel("
start_trip_idx = text.find(start_trip)
end_trip_idx = text.find(end_trip)

new_trip_code = '''def select_pyramid_triplets(
    expert_data: ExtractedExpertData, evaluations: List[BallEvaluation]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    步骤 4: 结合单码评分与同出协力矩阵，立体筛选三元组矩阵（T1核心高共振 + T2空间正交防御）
    """
    eval_map = {e.number: e for e in evaluations}
    co_mat = expert_data.co_matrix

    scored_triplets = []
    for trip in expert_data.all_triplets:
        nums = sorted(list(trip))
        if any(eval_map[n].is_double_kill for n in nums):
            continue

        t_scores = sum(eval_map[n].score for n in nums)
        # 加上两两历史同出协同分
        pair_co = 0.0
        if co_mat:
            pair_co = (co_mat[nums[0]][nums[1]] + co_mat[nums[1]][nums[2]] + co_mat[nums[0]][nums[2]]) * 0.05
        total_score = t_scores + pair_co
        zones = sorted(list(set(eval_map[n].zone_index for n in nums)))

        scored_triplets.append({
            "triplet": nums,
            "total_score": round(total_score, 2),
            "avg_score": round(total_score / 3.0, 2),
            "zones": zones,
            "has_point": any(eval_map[n].in_points for n in nums),
            "nums_str": "-".join(f"{n:02d}" for n in nums),
        })

    seen = set()
    unique_triplets = []
    for st in sorted(scored_triplets, key=lambda x: x["total_score"], reverse=True):
        key = tuple(st["triplet"])
        if key not in seen:
            seen.add(key)
            unique_triplets.append(st)

    t1_core = unique_triplets[:4]

    t2_defense = []
    t1_covered_nums = set(n for item in t1_core for n in item["triplet"])
    for item in unique_triplets[4:]:
        overlap = set(item["triplet"]) & t1_covered_nums
        if len(overlap) <= 1:
            t2_defense.append(item)
            if len(t2_defense) >= 4:
                break

    if len(t2_defense) < 4:
        t2_defense = unique_triplets[4:8]

    return t1_core, t2_defense


'''

text = text[:start_trip_idx] + new_trip_code + text[end_trip_idx:]

# 3. Update main startup log to 2026294
text = text.replace('启动 2026293期', '启动 2026294期')

with open("scripts/fusion_engine_294.py", "w", encoding="utf-8") as f:
    f.write(text)

print("scripts/fusion_engine_294.py rewritten successfully!")
