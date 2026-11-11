# -*- coding: utf-8 -*-
"""
快乐8 - 上期号码下期跟随统计排名引擎 (70多期窗口实战版)
=========================================================
【大白话架构说明】：
根据上一期开出的 20 个开奖号码，翻看最近 70 多期的大账本：
查查每一次当昨天开出这 20 个号时，明天谁最容易屁颠屁颠跟着出来！
生成类似 Excel/方方格子透视表样式的【重复项】与【重复计数】排行榜，
并自动高亮识别“★上期重号（连庄回头客，对应用户红笔打勾号）”与“强力新跟班”。

【2026-09-24 统计口径修正 (重要)】
旧版把分母当成 `Σ_t |上期∩draw_t|`(示例 343)，据此做二项检验会**制造假显著**：
    1码版真实算式是  count_y = Σ_t w_t · 1{y ∈ draw_{t+1}},  w_t = |上期 ∩ draw_t|
    但 1{y ∈ draw_{t+1}} 在同一个转移 t 内只掷一次骰子 —— **独立试验只有 T 个转移对(约70)**，
    不是 Σw(343)。用 343 当 n 会把标准差压小 ~2.3 倍（18.82 → 8.02），p 值被严重低估。
    实测: 旧口径下 14 个号"通过 BH-FDR"，改用精确加权伯努利检验后 **0 个号显著**。
因此现在:
    - 1码版用**精确 Poisson-Binomial 分布**算 p 值(按 w_t 分组卷积), 并给出 Wilson CI 与 BH-q;
    - 2码版的试验数天然就是 pair_occ(逐转移计一次)，n=pair_occ 正确，同样补 p/CI/BH-q;
    - 输出同时保留原始【重复计数】(计数字段不变, 只是不再声称它是概率优势)。
口径底线: **未过 BH-FDR 的号码不得作为下注依据**。
"""
import os
import re
import sys
import json
import argparse
from math import comb
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple

# 保证控制台与文件输出中文不乱码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_FILE = os.path.join(PROJ_DIR, "storage", "raw", "kl8_history_final.txt")
OUTPUT_DIR = os.path.join(PROJ_DIR, "storage", "outputs", "reports")
JSON_DIR = os.path.join(PROJ_DIR, "storage", "outputs", "follow_rank")

# 单码随机基线: 每期从 80 码里开 20 码 -> 任一号码下期出现的概率 = 20/80
BASELINE = 0.25

# 1码版取账本口径的 Top N (与全系统"最优3码"主口径对齐, 便于横向复盘)
LEDGER_TOP_N = 3


# ══════════════════════════════════════════════════════════════════════════
#  统计工具: 精确检验 + 区间 + 多重比较校正
# ══════════════════════════════════════════════════════════════════════════

def _wilson_lo(phat: float, n: int, z: float = 1.96) -> float:
    """Wilson 置信区间下界 (n=0 时返回 0.0)。"""
    if n <= 0:
        return 0.0
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (center - half) / denom)


def _exact_binomial_p(n: int, k: int, p: float = BASELINE) -> float:
    """P(X >= k), X ~ Binomial(n, p)。"""
    if n <= 0:
        return 1.0
    return sum(comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def _weighted_null_dist(weights: List[int], p: float = BASELINE) -> Dict[int, float]:
    """count = Σ_t w_t · B_t (B_t ~ Bernoulli(p) 独立) 的**精确**分布。

    按权重分组做卷积: 权重 w 出现 c 次 -> 该组贡献 w * Binomial(c, p)。
    """
    group = Counter(w for w in weights if w > 0)
    dist = {0: 1.0}
    for w, c in sorted(group.items()):
        bino = {k * w: comb(c, k) * (p ** k) * ((1 - p) ** (c - k)) for k in range(c + 1)}
        new: Dict[int, float] = {}
        for s1, p1 in dist.items():
            for s2, p2 in bino.items():
                new[s1 + s2] = new.get(s1 + s2, 0.0) + p1 * p2
        dist = new
    return dist


def _exact_weighted_p(weights: List[int], observed: int, p: float = BASELINE) -> float:
    """P(count >= observed) —— 加权伯努利精确尾概率。

    边界防守: 没有任何转移权重(样本为空)时返回 1.0(不显著)。
    若不防这一手, 空分布的尾概率会算成 0.0, 反而让全部号码"变成显著"。
    """
    if not weights:
        return 1.0
    dist = _weighted_null_dist(weights, p)
    return min(1.0, sum(prob for s, prob in dist.items() if s >= observed))


def _bh_fdr(pairs: List[Tuple[Any, float]]) -> Dict[Any, float]:
    """Benjamini-Hochberg FDR 校正 -> {key: q}。pairs = [(key, p), ...]"""
    n = len(pairs)
    if n == 0:
        return {}
    ordered = sorted(pairs, key=lambda x: x[1])
    q: Dict[Any, float] = {}
    prev = 1.0
    for i in range(n - 1, -1, -1):
        key, p = ordered[i]
        prev = min(prev, p * n / (i + 1))
        q[key] = min(1.0, prev)
    return q


def _verdict(q: float, p: float) -> str:
    if q < 0.05:
        return "✓FDR显著"
    if p < 0.05:
        return "边缘(p<0.05,q未过)"
    return "未显著"


def load_draws(file_path: str) -> List[Dict[str, Any]]:
    """加载开奖数据并按期号升序排序"""
    draws = []
    if not os.path.exists(file_path):
        print(f"找不到数据文件: {file_path}")
        return []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line)
            if m:
                nums = [int(x) for x in m.group(3).split("-") if x.isdigit()]
                if len(nums) == 20:
                    draws.append({
                        "period": int(m.group(2)),
                        "date": m.group(1),
                        "nums": set(nums),
                        "list": sorted(nums)
                    })
    draws.sort(key=lambda d: d["period"])
    return draws


def calculate_follow_ranking(draws: List[Dict[str, Any]], window_size: int = 70, target_idx: int = -1) -> Dict[str, Any]:
    """
    计算基于上期开奖号码在历史样本中的下期跟随排名
    :param draws: 升序开奖历史列表
    :param window_size: 回溯期数窗口，默认 70 期; None 或 <=0 表示用全量历史
    :param target_idx: 锚定基准期的索引，-1 表示以最新一期为上期
    :return: 统计汇总字典
    """
    # 全量历史: 把窗口折成"全部可用转移", 之后再走同一套切片逻辑
    if window_size is None or window_size <= 0:
        window_size = len(draws) - 1
    # 切片契约: 需要 window_size+1 个期数才能构成 window_size 个转移对 (t -> t+1)
    # (旧守卫写成 +2, 比实际需求多要 1 期, 全量时必然触发"期数不足")
    if target_idx == -1:
        if len(draws) < window_size + 1:
            raise ValueError(f"开奖历史期数不足: 总数 {len(draws)}, 需求至少 {window_size + 1}")
    else:
        window_size = min(window_size, max(0, target_idx))
        if window_size < 1:
            raise ValueError("锚定基准期太靠前, 无法构成任何转移对")

    # 基准上期
    base_draw = draws[target_idx]
    base_period = base_draw["period"]
    base_date = base_draw["date"]
    base_nums = base_draw["nums"]
    base_nums_list = base_draw["list"]

    # 目标预测期（即下一期）
    next_period = base_period + 1

    # 截取样本窗口：在基准期之前 window_size 期的转移对 (t -> t+1)
    # 保证严格无未来函数（只使用基准期及之前的开奖对）
    if target_idx == -1:
        sample_draws = draws[-window_size-1:]
    else:
        sample_draws = draws[target_idx - window_size : target_idx + 1]

    # follow_matrix[x][y] = 历史期 t 开出 x，下一期 t+1 开出 y 的总次数
    follow_matrix = defaultdict(Counter)
    num_appearances = Counter()
    # transition_weights[t] = |上期20码 ∩ 第t期|，即该转移对 y 的计数权重 w_t
    # 关键: 独立试验数是 len(transition_weights)(≈70)，不是 sum(transition_weights)
    transition_weights: List[int] = []
    base_set = set(base_nums)

    for t in range(len(sample_draws) - 1):
        cur_nums = sample_draws[t]["nums"]
        nxt_nums = sample_draws[t+1]["nums"]
        transition_weights.append(len(base_set & set(cur_nums)))
        for x in cur_nums:
            num_appearances[x] += 1
            for y in nxt_nums:
                follow_matrix[x][y] += 1

    # 统计口径 1: 上期 20 码跟随总频次 (重复计数)
    total_follow_counts = Counter()
    # 统计口径 2: 每个号码 y 是被上期哪几个号码带出来的（支撑明细）
    supporter_map = defaultdict(list)

    for x in base_nums:
        for y, cnt in follow_matrix[x].items():
            total_follow_counts[y] += cnt
            supporter_map[y].append((x, cnt))

    # 按跟随频次（重复计数）从大到小降序排列
    total_base_balls_drawn = sum(num_appearances[x] for x in base_nums)
    ordered = total_follow_counts.most_common(80)

    # 精确检验: count_y = Σ_t w_t·B_t, 逐号算精确尾概率, 再做 BH-FDR 多重比较校正
    raw_ps = [(num, _exact_weighted_p(transition_weights, cnt)) for num, cnt in ordered]
    bh_q = _bh_fdr(raw_ps)
    p_map = dict(raw_ps)

    ranking = []
    for rank, (num, cnt) in enumerate(ordered, start=1):
        is_repeat = (num in base_set)
        # 找出上期 20 码中，带出该号码最频繁的 Top 3 引路人
        top_supporters = sorted(supporter_map[num], key=lambda item: item[1], reverse=True)[:3]
        supporter_desc = "、".join([f"{sx:02d}({sc}次)" for sx, sc in top_supporters])

        # 加权条件出现率 = 计数 / 权重和 (旧版把它误当概率并乘以4, 实为 Lift 的百分数)
        cond_rate = (cnt / total_base_balls_drawn) if total_base_balls_drawn else 0.0
        p_val = p_map.get(num, 1.0)
        q_val = bh_q.get(num, 1.0)

        ranking.append({
            "rank": rank,
            "number": num,
            "num_str": f"{num:02d}",
            "follow_count": cnt,
            "is_repeat": is_repeat,
            "type_tag": "★连庄重号(回头客)" if is_repeat else "强力新跟班",
            "supporter_desc": supporter_desc,
            "cond_rate": cond_rate,
            "lift": (cond_rate / BASELINE) if total_base_balls_drawn else 0.0,
            "wilson_lo": _wilson_lo(cond_rate, total_base_balls_drawn),
            "p_value": p_val,
            "bh_q": q_val,
            "verdict": _verdict(q_val, p_val),
        })

    significant = [it["num_str"] for it in ranking if it["bh_q"] < 0.05]

    return {
        "base_period": base_period,
        "base_date": base_date,
        "base_nums": base_nums_list,
        "next_period": next_period,
        "window_size": window_size,
        "sample_start_period": sample_draws[0]["period"],
        "sample_end_period": sample_draws[-2]["period"],
        "total_base_appearances": total_base_balls_drawn,
        "effective_trials": len(transition_weights),
        "transition_weights_sum": sum(transition_weights),
        "baseline": BASELINE,
        "significant_numbers": significant,
        "ranking": ranking,
    }


def export_ranking_to_excel(result: Dict[str, Any], output_path: str) -> str:
    """
    将分析结果导出为专业 Excel 表格（复刻用户截图格式：重复项 | 重复计数）
    带有单元格边框、居中对齐、重号高亮标注
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"70期跟随排名_{result['next_period']}"

    # 样式准备
    font_header = Font(name="Microsoft YaHei", size=11, bold=True, color="000000")
    font_bold = Font(name="Microsoft YaHei", size=10, bold=True)
    font_normal = Font(name="Microsoft YaHei", size=10)
    font_repeat = Font(name="Microsoft YaHei", size=10, bold=True, color="C00000")

    fill_header = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_repeat = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # 淡黄高亮重号
    fill_top5 = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")   # 绿色高亮前五

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')

    # 写入报表说明
    ws.cell(row=1, column=1, value="快乐8 上期号码下期跟随排名统计 (70期大盘记忆)").font = Font(name="Microsoft YaHei", size=14, bold=True)
    ws.cell(row=2, column=1, value=f"基准上期: 第 {result['base_period']} 期 ({result['base_date']}) | 目标预测: 第 {result['next_period']} 期 | 样本跨度: 过去 {result['window_size']} 期").font = font_normal
    ws.cell(row=3, column=1, value=f"上期开奖 20 码: {' '.join(f'{x:02d}' for x in result['base_nums'])}").font = font_bold

    # 写入表头（第 5 行，前两列严格按照用户截图的「重复项」与「重复计数」）
    headers = ["重复项", "重复计数", "排名", "条件出现率", "Lift", "Wilson下界",
               "p值", "BH-q", "显著性判定", "属性标签", "上期重号标记", "主要引路人(上期带出最多号)"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=5, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    # 写入数据行
    for r_idx, item in enumerate(result["ranking"], start=6):
        c1 = ws.cell(row=r_idx, column=1, value=item["num_str"])
        c2 = ws.cell(row=r_idx, column=2, value=item["follow_count"])
        c3 = ws.cell(row=r_idx, column=3, value=item["rank"])
        c4 = ws.cell(row=r_idx, column=4, value=round(item.get("cond_rate", 0.0) * 100, 2))
        c5 = ws.cell(row=r_idx, column=5, value=round(item.get("lift", 0.0), 3))
        c6 = ws.cell(row=r_idx, column=6, value=round(item.get("wilson_lo", 0.0) * 100, 2))
        c7 = ws.cell(row=r_idx, column=7, value=round(item.get("p_value", 1.0), 4))
        c8 = ws.cell(row=r_idx, column=8, value=round(item.get("bh_q", 1.0), 3))
        c9 = ws.cell(row=r_idx, column=9, value=item.get("verdict", ""))
        c10 = ws.cell(row=r_idx, column=10, value=item["type_tag"])
        c11 = ws.cell(row=r_idx, column=11, value="✔ 重号" if item["is_repeat"] else "")
        c12 = ws.cell(row=r_idx, column=12, value=item["supporter_desc"])

        # 设置样式
        for cell in [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11]:
            cell.alignment = align_center
            cell.border = thin_border
            cell.font = font_normal
        c12.alignment = align_left
        c12.border = thin_border
        c12.font = font_normal

        # 特殊高亮
        if item["is_repeat"]:
            c1.font = font_repeat
            c11.font = font_repeat
            c11.fill = fill_repeat
        if item["rank"] <= 5:
            c1.fill = fill_top5
            c2.fill = fill_top5
        # 过 BH-FDR 才给绿色
        if item.get("bh_q", 1.0) < 0.05:
            c9.fill = fill_top5
            c9.font = font_bold

    # 统计口径说明 (放在数据下方, 防止被当成概率优势)
    note_row = 6 + len(result["ranking"]) + 1
    ws.cell(row=note_row, column=1,
            value="口径: 条件出现率=计数/权重和; 独立试验数=%s(转移对); 随机基线 25%%; "
                  "p值为精确加权伯努利尾概率; BH-q<0.05 才算显著 —— 未过者不可作为下注依据。"
                  % result.get("effective_trials", "N/A")).font = font_normal

    # 设置列宽
    for col, w in zip("ABCDEFGHIJKL", [10, 12, 8, 12, 8, 12, 9, 8, 18, 20, 14, 34]):
        ws.column_dimensions[col].width = w

    wb.save(output_path)
    return output_path


def calculate_pair_follow_ranking(draws: List[Dict[str, Any]], num_a: int, num_b: int, window_size: int = 500) -> Dict[str, Any]:
    """
    计算双号 (A, B) 历史同时开出时，下一期各个号码的跟随频次（严格按重复计数倒序排列）

    窗口口径: 默认 **500 期**(2026-09-24 定)。双号同出是低频事件, 70 期窗口样本常常只有个位数
    (示例 `12-74` 70期仅 8 次), 统计功效几乎为零, 故 2码单独放宽到 500 期; 1码版维持 70 期。
    `window_size=None` 或 `<=0` 表示用全量历史。
    """
    sample_draws = draws if (window_size is None or window_size <= 0) else draws[-window_size:]
    pair_occ = 0
    occ_a = 0
    occ_b = 0
    follow_cnt = Counter()

    for t in range(len(sample_draws) - 1):
        cur_s = sample_draws[t]["nums"]
        nxt_s = sample_draws[t + 1]["nums"]
        has_a = (num_a in cur_s)
        has_b = (num_b in cur_s)
        if has_a:
            occ_a += 1
        if has_b:
            occ_b += 1
        if has_a and has_b:
            pair_occ += 1
            for y in nxt_s:
                follow_cnt[y] += 1

    ranking = []
    last_nums = sample_draws[-1]["nums"]
    for y in range(1, 81):
        cnt = follow_cnt[y]
        rate = (cnt / pair_occ) if pair_occ else 0.0
        is_repeat = (y in [num_a, num_b] or y in last_nums)
        ranking.append({
            "rank": 0,
            "number": y,
            "num_str": f"{y:02d}",
            "follow_count": cnt,
            "is_repeat": is_repeat,
            "cond_rate": rate,
            "lift": (rate / BASELINE) if pair_occ else 0.0,
            "wilson_lo": _wilson_lo(rate, pair_occ),
            "p_value": _exact_binomial_p(pair_occ, cnt),
            "type_tag": "★连庄重号" if is_repeat else "新号跟出",
            "supporter_desc": f"双号({num_a:02d},{num_b:02d})同出带出"
        })

    # 按重复计数倒序排
    ranking.sort(key=lambda item: (-item["follow_count"], item["number"]))
    for r, item in enumerate(ranking, 1):
        item["rank"] = r

    # 2码版的试验数天然正确: 每个"双号同出"的转移对记一次 -> n = pair_occ
    q_map = _bh_fdr([(it["number"], it["p_value"]) for it in ranking])
    for item in ranking:
        item["bh_q"] = q_map.get(item["number"], 1.0)
        item["verdict"] = _verdict(item["bh_q"], item["p_value"])

    return {
        "num_a": num_a,
        "num_b": num_b,
        "occ_a": occ_a,
        "occ_b": occ_b,
        "pair_occ": pair_occ,
        "total_draws": len(sample_draws),
        "window_size": window_size,
        "baseline": BASELINE,
        "significant_numbers": [it["num_str"] for it in ranking if it["bh_q"] < 0.05],
        "ranking": ranking
    }


def main():
    parser = argparse.ArgumentParser(description="快乐8 上期号码/双号下期跟随统计排名工具")
    parser.add_argument("--window", type=int, default=70,
                        help="1码模式回溯统计期数 (默认 70 期; 填 0 表示全量历史)")
    parser.add_argument("--pair", nargs=2, type=int, default=None, help="统计双号同时开出后的下期跟随 (例如 --pair 2 10)")
    parser.add_argument("--pair-window", type=int, default=500,
                        help="2码模式回溯统计期数 (默认 500 期 —— 双号同出低频, 70 期样本太少; 填 0 表示全量历史)")
    parser.add_argument("--excel", action="store_true", default=True, help="是否导出 Excel 表格")
    args = parser.parse_args()

    draws = load_draws(HISTORY_FILE)
    if not draws:
        print("错误：未能加载到任何开奖数据！")
        return

    if args.pair:
        na, nb = args.pair
        res = calculate_pair_follow_ranking(draws, na, nb, window_size=args.pair_window)
        win_txt = f"窗口 {res['window_size']} 期" if res.get("window_size") else "全量历史"
        print(f"\n" + "=" * 96)
        print(f" 🧬【双号({na:02d}, {nb:02d})同出下期跟随排行榜】({win_txt}, 实取 {res['total_draws']} 期开奖)")
        print(f" 号码 {na:02d} 出号: {res['occ_a']} 次 | 号码 {nb:02d} 出号: {res['occ_b']} 次 | 双号同时开出: {res['pair_occ']} 次 (独立试验数)")
        print("=" * 96)
        print(f"| {'排名':^4} | {'号':^4} | {'重复计数':^8} | {'条件率':^8} | {'Lift':^6} | {'Wilson下界':^10} | {'p值':^8} | {'BH-q':^7} | {'判定':^18} |")
        print("|" + "-" * 94 + "|")
        for item in res["ranking"][:20]:
            print(f"| {item['rank']:^4d} | {item['num_str']:^4} | {item['follow_count']:^8d} |"
                  f" {item['cond_rate'] * 100:>7.1f}% | {item['lift']:^6.2f} | {item['wilson_lo'] * 100:>9.1f}% |"
                  f" {item['p_value']:^8.4f} | {item['bh_q']:^7.3f} | {item['verdict']:^18} |")
        sig = res["significant_numbers"]
        print(f"\n 通过 BH-FDR(q<0.05): {' '.join(sig) if sig else '无 —— 本期无统计显著跟随号'}")
        print(" 口径底线: 计数只是「出现过几次」, 不构成概率优势; 未过 BH-FDR 不得作为下注依据。")
        return

    res = calculate_follow_ranking(draws, window_size=args.window)

    print(f"\n" + "=" * 104)
    print(f" 🧬【上期号码下期跟随排行榜】(第 {res['base_period']} 期 -> 第 {res['next_period']} 期)")
    print(f" 上期开奖20码: {res['base_nums']}")
    print(f" 样本范围: 过去 {res['window_size']} 期历史转移（第 {res['sample_start_period']} 期 ~ 第 {res['sample_end_period']} 期）")
    print(f" 独立试验数(转移对) T={res['effective_trials']} | 权重和 Σw={res['transition_weights_sum']} "
          f"(旧口径误把 Σw 当试验数 → 会制造假显著)")
    print("=" * 104)
    print(f"| {'排名':^4} | {'号':^4} | {'重复计数':^8} | {'条件率':^8} | {'Lift':^6} | {'Wilson下界':^10} | {'p值':^8} | {'BH-q':^7} | {'判定':^18} | {'最大引路人':<22} |")
    print("|" + "-" * 102 + "|")

    for item in res["ranking"][:25]:
        print(f"| {item['rank']:^4d} | {item['num_str']:^4} | {item['follow_count']:^8d} |"
              f" {item['cond_rate'] * 100:>7.1f}% | {item['lift']:^6.2f} | {item['wilson_lo'] * 100:>9.1f}% |"
              f" {item['p_value']:^8.4f} | {item['bh_q']:^7.3f} | {item['verdict']:^18} | {item['supporter_desc']:<22} |")

    sig = res["significant_numbers"]
    print(f"\n 通过 BH-FDR(q<0.05): {' '.join(sig) if sig else '无 —— 本期无统计显著跟随号'}")
    print(" 口径底线: 计数只是「出现过几次」, 不构成概率优势; 未过 BH-FDR 不得作为下注依据。")

    # 导出 Excel
    excel_path = os.path.join(OUTPUT_DIR, f"follow_ranking_period_{res['next_period']}_{args.window}windows.xlsx")
    export_ranking_to_excel(res, excel_path)
    print(f"\n[OK] 完整 80 码跟随排名 Excel 文件已生成: {excel_path}")

    # 按期落盘 JSON 产物, 供 daily_review 收割器记账与复盘
    os.makedirs(JSON_DIR, exist_ok=True)
    top = res["ranking"][:LEDGER_TOP_N]
    artifact = {
        "module_code": "follow_rank",
        "module_name": "跟随统计推演 (1码×70期窗口)",
        "target_period": str(res["next_period"]),
        "base_period": str(res["base_period"]),
        "base_date": res["base_date"],
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "window_size": res["window_size"],
        "effective_trials": res["effective_trials"],
        "baseline": res["baseline"],
        "top3_gold": [it["number"] for it in top],
        "top5_gold": [it["number"] for it in res["ranking"][:5]],
        "top12_elite": [it["number"] for it in res["ranking"][:12]],
        "significant_numbers": res["significant_numbers"],
        "is_significant": bool(res["significant_numbers"]),
        "evidence_note": (
            "跟随计数为加权计数(上期重叠加权), 精确加权伯努利检验后%s; "
            "独立试验数=%d(转移对), 随机基线25%%。" % (
                "有号通过 BH-FDR" if res["significant_numbers"] else "**无号通过 BH-FDR**",
                res["effective_trials"],
            )
        ),
        "ranking": res["ranking"],
        "source_file": excel_path,
    }
    json_path = os.path.join(JSON_DIR, f"follow_rank_{res['next_period']}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
    print(f"[OK] 按期 JSON 产物已落盘: {json_path}")


if __name__ == "__main__":
    main()
