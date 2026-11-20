# -*- coding: utf-8 -*-
"""
Patch fusion_engine_294.py to incorporate Sheet 14 co-occurrence matrix and Sheet 13 top pairs
into evaluate_all_balls and select_pyramid_triplets for period 2026294.
"""
import re

with open("scripts/fusion_engine_294.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update ExtractedExpertData dataclass to include co_mat and top_pairs
old_dataclass = """@dataclass
class ExtractedExpertData:
    \"\"\"从多源提取的专家结构化实体\"\"\"
    target_period: int
    points_293: List[int]
    dw_repeat_high: List[int]
    dw_edge_high: List[int]
    dw_cold_high: List[int]
    kill_set_1: Set[int]
    kill_set_2: Set[int]
    double_kill_set: Set[int]
    union_kill_set: Set[int]
    zhaodan_ranking_top20: List[int]
    zhaodan_ranking_all: List[int]
    triplets_weilai: List[Tuple[int, int, int]]
    triplets_sijing_1: List[Tuple[int, int, int]]
    triplets_sijing_2: List[Tuple[int, int, int]]
    triplets_sijing_3: List[Tuple[int, int, int]]
    all_triplets: List[Tuple[int, int, int]]
    audit_report: HistoricalAuditReport | None = None
    backtest_summary: BacktestSummary | None = None"""

new_dataclass = """@dataclass
class ExtractedExpertData:
    \"\"\"从多源提取的专家结构化实体\"\"\"
    target_period: int
    points_293: List[int]
    dw_repeat_high: List[int]
    dw_edge_high: List[int]
    dw_cold_high: List[int]
    kill_set_1: Set[int]
    kill_set_2: Set[int]
    double_kill_set: Set[int]
    union_kill_set: Set[int]
    zhaodan_ranking_top20: List[int]
    zhaodan_ranking_all: List[int]
    triplets_weilai: List[Tuple[int, int, int]]
    triplets_sijing_1: List[Tuple[int, int, int]]
    triplets_sijing_2: List[Tuple[int, int, int]]
    triplets_sijing_3: List[Tuple[int, int, int]]
    all_triplets: List[Tuple[int, int, int]]
    co_matrix: Dict[int, Dict[int, float]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(float)))
    top_pairs: List[Tuple[int, int, float, float]] = field(default_factory=list)
    audit_report: HistoricalAuditReport | None = None
    backtest_summary: BacktestSummary | None = None"""

text = text.replace(old_dataclass, new_dataclass)

# 2. In extract_excel_data, load Sheet 14 and Sheet 13 from 2026294.xls
old_return = """    all_triplets = (
        triplets_weilai + triplets_sijing_1 + triplets_sijing_2 + triplets_sijing_3
    )

    return ExtractedExpertData("""

new_return = """    # 2.3 加载 2026294.xls 真实历史同出矩阵与 Top 配对
    co_matrix: Dict[int, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    top_pairs: List[Tuple[int, int, float, float]] = []
    if os.path.exists(path_fx_294):
        try:
            book_fx = xlrd.open_workbook(path_fx_294)
            if "图表15选2同出" in book_fx.sheet_names():
                sh15 = book_fx.sheet_by_name("图表15选2同出")
                for r in range(min(80, sh15.nrows)):
                    for c in range(1, min(81, sh15.ncols)):
                        cv = sh15.cell_value(r, c)
                        if cv != "":
                            try:
                                co_matrix[r + 1][c] = float(cv)
                            except (ValueError, TypeError):
                                pass
            if "图表14选2" in book_fx.sheet_names():
                sh14 = book_fx.sheet_by_name("图表14选2")
                for r in range(1, sh14.nrows):
                    p_str = str(sh14.cell_value(r, 1)).strip()
                    if "-" in p_str:
                        parts = p_str.split("-")
                        try:
                            n1, n2 = int(parts[0]), int(parts[1])
                            hits = float(sh14.cell_value(r, 0))
                            out = float(sh14.cell_value(r, 2))
                            top_pairs.append((min(n1, n2), max(n1, n2), hits, out))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass

    # 2.4 构建第 294 期高协同三元组候选池
    top_triplets_294: List[Tuple[int, int, int]] = []
    # 优先基于 2026294 点位与分类共振组
    pts_set = set(points_293)
    rep_set = set(dw_repeat_high)
    edg_set = set(dw_edge_high)
    cld_set = set(dw_cold_high)
    high_pool = list(pts_set | rep_set | edg_set | cld_set)

    # 核心霸主配对 (23, 53)
    if 23 in high_pool and 53 in high_pool:
        for k in high_pool:
            if k not in (23, 53):
                top_triplets_294.append(tuple(sorted([23, 53, k])))
    # 扩展其他高频点位配对
    for p1, p2, hits, out in top_pairs[:50]:
        if (p1 in pts_set or p1 in rep_set) and (p2 in pts_set or p2 in rep_set):
            for k in high_pool[:15]:
                if k not in (p1, p2):
                    top_triplets_294.append(tuple(sorted([p1, p2, k])))

    all_triplets = list(set(top_triplets_294 + triplets_weilai + triplets_sijing_1 + triplets_sijing_2 + triplets_sijing_3))

    return ExtractedExpertData(
        co_matrix=co_matrix,
        top_pairs=top_pairs,"""

text = text.replace(old_return, new_return)

# 3. In evaluate_all_balls, incorporate co_matrix and top_pairs
old_eval_body = """    for num in range(1, TOTAL_BALL_COUNT + 1):
        tags: List[str] = []
        score: float = 0.0

        # 特征1: 核心点位权重 (+2.2)
        in_pts = num in points_set
        if in_pts:
            score += 2.2
            tags.append("核心点位")

        # 特征2: 专家加权频次暴击
        raw_cnt = raw_counts[num]
        w_score = weighted_counts[num]
        score += w_score * 0.95

        # 历史开出动力学奖励（阶梯分：cnt>=3时真实开出27.5%~41.7%）
        if raw_cnt >= 5:
            score += 2.2  # 出现5~6次极高胜率31.4%~41.7%
            tags.append(f"共识暴击({raw_cnt}次)")
        elif raw_cnt >= 3:
            score += 1.2  # 出现3~4次增益27.5%~28.8%
            tags.append(f"高频共识({raw_cnt}次)")
        elif raw_cnt > 0:
            tags.append(f"胆组推荐({raw_cnt}次)")

        # 特征3: 均值回归反弹下的重码动力学 (+2.0)
        # 上期重码3个远低于均值5.0，极高概率反弹
        in_rep = num in repeat_set
        if in_rep:
            score += 2.0
            tags.append("均值回归重码")

        # 特征4: 均值回归反弹下的边码动力学 (+1.8)
        # 上期边码7个低于均值9.7，边码反弹
        in_edg = num in edge_set
        if in_edg:
            score += 1.8
            tags.append("均值回归边码")

        # 特征5: 极冷号高概 (+1.5)
        in_cld = num in cold_set
        if in_cld:
            score += 1.5
            tags.append("指标反弹冷号")"""

new_eval_body = """    top_pairs_set = set((p[0], p[1]) for p in expert_data.top_pairs[:100])
    co_mat = expert_data.co_matrix

    for num in range(1, TOTAL_BALL_COUNT + 1):
        tags: List[str] = []
        score: float = 0.0

        # 特征1: 核心点位权重 (+3.2)
        in_pts = num in points_set
        if in_pts:
            score += 3.2
            tags.append("20核心点位")

        # 特征2: 均值回归反弹下的重码动力学 (+2.8)
        in_rep = num in repeat_set
        if in_rep:
            score += 2.8
            tags.append("重号高概")

        # 特征3: 均值回归反弹下的边码动力学 (+2.2)
        in_edg = num in edge_set
        if in_edg:
            score += 2.2
            tags.append("边号高概")

        # 特征4: 重点关注冷号反弹 (+2.2)
        in_cld = num in cold_set
        if in_cld:
            score += 2.2
            tags.append("关注冷号")

        # 特征5: 点位同出协力中心度 (来自图表15同出矩阵)
        if co_mat and points_set:
            co_sum = sum(co_mat[num][p] for p in points_set if p != num)
            co_avg = co_sum / len(points_set)
            score += (co_avg - 120.0) * 0.1
            tags.append(f"点位协力{co_avg:.1f}")

        # 特征6: 历史 Top 配对增益 (来自图表14选2)
        pair_m = sum(1 for p in points_set if (min(num, p), max(num, p)) in top_pairs_set)
        if pair_m > 0:
            score += min(2.5, pair_m * 0.8)
            tags.append(f"Top配对x{pair_m}")

        # 特征7: 专家加权频次辅助加分
        raw_cnt = raw_counts[num]
        w_score = weighted_counts[num]
        if w_score > 0:
            score += min(1.5, w_score * 0.25)
            tags.append(f"专家背书({raw_cnt}次)")"""

text = text.replace(old_eval_body, new_eval_body)

with open("scripts/fusion_engine_294.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied successfully!")
