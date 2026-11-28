# -*- coding: utf-8 -*-
"""
选2 专属决策引擎 (Pair Selection Engine)
========================================
核心使命：
从多维度子模块中抽取“专有 2 码”，通过双元共现矩阵 (Lift)、杀号一票否决、
排斥力检测与多维共振打分，收敛出【全场唯一最优 1 组选2】。

架构分层：
1. 模块双码提取层 (Sub-module Dual Extraction)：
   - EF: 能量双子星 (能量中心 + 物理/能量近邻)
   - RW: 冷热弹簧搭档 (临界回补冷号 + 激活温热号)
   - FO: 特征状元榜眼 (综合得分前二 + 互斥性检测)
   - Deep: 连体婴黄金搭档 (历史共现 Lift 最高搭档)
   - PurePool: 纯净金银双胆 (纯净池综合前二)
2. 安全与排斥力过滤层 (Safety & Anti-Cannibalization Filter)：
   - 杀号一票否决 (KillSeeker / 防守码过滤)
   - 相克排斥检测 (近50期同出为0拦截)
3. 全局共振收敛打分层 (Global Synergy Scoring)：
   - 单码实力 + 双元共现 Lift + 模块提名共振度
   - 输出 No.1 冠军组合与大白话归因
"""

import math
import collections
import itertools
from typing import Dict, List, Set, Tuple, Any, Optional


class PairSelector:
    """快乐8 极简选2决策收敛引擎"""

    def __init__(self, history: List[Dict[str, Any]], points_map: Optional[Dict[str, Set[int]]] = None):
        self.history = history
        self.points_map = points_map or {}
        self.total_periods = len(history)
        self._init_cooccurrence_matrix()

    def _init_cooccurrence_matrix(self):
        """预计算历史全量与近100期双元共现频率与 Lift 矩阵"""
        self.single_counts_total = collections.Counter()
        self.pair_counts_total = collections.Counter()
        self.single_counts_100 = collections.Counter()
        self.pair_counts_100 = collections.Counter()
        self.single_counts_50 = collections.Counter()
        self.pair_counts_50 = collections.Counter()

        n_total = len(self.history)
        recent_100 = self.history[:100]
        recent_50 = self.history[:50]

        # 全量统计
        for h in self.history:
            nums = sorted(h['numbers'])
            for n in nums:
                self.single_counts_total[n] += 1
            for pair in itertools.combinations(nums, 2):
                self.pair_counts_total[pair] += 1

        # 近100期统计
        for h in recent_100:
            nums = sorted(h['numbers'])
            for n in nums:
                self.single_counts_100[n] += 1
            for pair in itertools.combinations(nums, 2):
                self.pair_counts_100[pair] += 1

        # 近50期统计 (用于排斥力检测)
        for h in recent_50:
            nums = sorted(h['numbers'])
            for n in nums:
                self.single_counts_50[n] += 1
            for pair in itertools.combinations(nums, 2):
                self.pair_counts_50[pair] += 1

    def get_pair_key(self, a: int, b: int) -> Tuple[int, int]:
        """统一返回有序二元组 (min, max)"""
        return (min(a, b), max(a, b))

    def compute_pair_synergy(self, a: int, b: int) -> Dict[str, Any]:
        """计算任意两号码的共现与协同指标"""
        pair = self.get_pair_key(a, b)
        n100 = min(100, len(self.history))
        n50 = min(50, len(self.history))
        n_tot = max(1, len(self.history))

        c_tot = self.pair_counts_total.get(pair, 0)
        c_100 = self.pair_counts_100.get(pair, 0)
        c_50 = self.pair_counts_50.get(pair, 0)

        s_a_100 = self.single_counts_100.get(a, 0)
        s_b_100 = self.single_counts_100.get(b, 0)
        s_a_50 = self.single_counts_50.get(a, 0)
        s_b_50 = self.single_counts_50.get(b, 0)
        s_a_tot = self.single_counts_total.get(a, 0)
        s_b_tot = self.single_counts_total.get(b, 0)

        # 理论独立同出期望: 快乐8每期开20个，随机双中基准 = (20/80)*(19/79) ≈ 0.0601267
        base_pair_prob = 0.0601267

        # 近100期经验 Lift
        exp_cooccur_100 = (s_a_100 / n100) * (s_b_100 / n100) if n100 > 0 else base_pair_prob
        obs_cooccur_100 = c_100 / n100 if n100 > 0 else 0
        lift_100 = (obs_cooccur_100 / exp_cooccur_100) if exp_cooccur_100 > 1e-6 else 1.0

        # 全量 Lift
        exp_cooccur_tot = (s_a_tot / n_tot) * (s_b_tot / n_tot) if n_tot > 0 else base_pair_prob
        obs_cooccur_tot = c_tot / n_tot if n_tot > 0 else 0
        lift_tot = (obs_cooccur_tot / exp_cooccur_tot) if exp_cooccur_tot > 1e-6 else 1.0

        # 互斥/排斥性检验: 如果近50期两号各自开出≥7次，但同出为0，判定为严重排斥(Cannibalized)
        is_mutually_exclusive = False
        if n50 >= 30 and s_a_50 >= 7 and s_b_50 >= 7 and c_50 == 0:
            is_mutually_exclusive = True

        return {
            'pair': pair,
            'count_100': c_100,
            'count_total': c_tot,
            'lift_100': round(lift_100, 3),
            'lift_total': round(lift_tot, 3),
            'is_mutually_exclusive': is_mutually_exclusive,
            'obs_prob_100': round(obs_cooccur_100, 4),
        }

    # ═══════════════════════════════════════════════════════════════
    #  各子模块专有 2 码提取逻辑
    # ═══════════════════════════════════════════════════════════════

    def extract_ef_pair(self, ef_scores: Dict[int, float]) -> Optional[Dict[str, Any]]:
        """
        1. 隐能量场 EF: 【能量双子星】
        逻辑：选取能量峰值 No.1 号码，并在能量高分前 10 中寻找同区域/强协同的搭档
        """
        if not ef_scores:
            return None
        sorted_ef = sorted(ef_scores.items(), key=lambda x: x[1], reverse=True)
        top1 = sorted_ef[0][0]

        best_partner = None
        best_score = -1.0

        for num, sc in sorted_ef[1:10]:
            syn = self.compute_pair_synergy(top1, num)
            if syn['is_mutually_exclusive']:
                continue
            # 能量空间距离加权: 距离在 1~8 之间的具有同区扎堆能量
            dist = abs(top1 - num)
            spatial_bonus = 1.25 if dist <= 8 else 1.0
            score = (sc + ef_scores[top1]) * syn['lift_100'] * spatial_bonus
            if score > best_score:
                best_score = score
                best_partner = num

        if not best_partner and len(sorted_ef) > 1:
            best_partner = sorted_ef[1][0]

        pair = self.get_pair_key(top1, best_partner)
        return {
            'module': 'EF_EnergyField',
            'label': '能量双子星',
            'pair': pair,
            'core_ball': top1,
            'partner_ball': best_partner,
            'reason': f"能量中心{top1:02d}与其高能邻域搭档{best_partner:02d}扎堆共振 (近100期Lift={self.compute_pair_synergy(pair[0], pair[1])['lift_100']}x)",
        }

    def extract_rw_pair(self, rw_scores: Dict[int, float]) -> Optional[Dict[str, Any]]:
        """
        2. 遗漏回补 RW: 【冷热弹簧搭档】
        逻辑：1个临界回补极限冷号 + 1个刚解冻处于二次回暖期的温热号，冷热对冲
        """
        if not rw_scores:
            return None

        # 计算当前各号最新遗漏步长
        current_omissions = {}
        if self.history:
            for num in range(1, 81):
                om = 0
                for h in self.history:
                    if num in h['numbers']:
                        break
                    om += 1
                current_omissions[num] = om

        # 候选冷号（遗漏 4~12 期，且 RW 评分高）
        cold_candidates = [n for n, om in current_omissions.items() if 4 <= om <= 12 and n in rw_scores]
        cold_candidates.sort(key=lambda n: rw_scores.get(n, 0), reverse=True)

        # 候选温热回暖号（遗漏 0~2 期，且 RW 评分高）
        warm_candidates = [n for n, om in current_omissions.items() if om <= 2 and n in rw_scores]
        warm_candidates.sort(key=lambda n: rw_scores.get(n, 0), reverse=True)

        cold_pick = cold_candidates[0] if cold_candidates else (sorted(rw_scores.items(), key=lambda x: x[1], reverse=True)[0][0])
        
        # 挑选与 cold_pick 搭配最好的 warm_pick
        best_warm = None
        best_lift = -1.0
        for w in warm_candidates:
            if w == cold_pick:
                continue
            syn = self.compute_pair_synergy(cold_pick, w)
            if syn['is_mutually_exclusive']:
                continue
            if syn['lift_100'] > best_lift:
                best_lift = syn['lift_100']
                best_warm = w

        if not best_warm:
            sorted_rw = sorted(rw_scores.items(), key=lambda x: x[1], reverse=True)
            best_warm = sorted_rw[1][0] if len(sorted_rw) > 1 else (cold_pick % 80 + 1)

        pair = self.get_pair_key(cold_pick, best_warm)
        return {
            'module': 'RW_Omission',
            'label': '冷热弹簧搭档',
            'pair': pair,
            'core_ball': cold_pick,
            'partner_ball': best_warm,
            'reason': f"临界回补冷号{cold_pick:02d}(遗漏{current_omissions.get(cold_pick, 0)}期) + 温态回暖号{best_warm:02d}冷热对冲",
        }

    def extract_fo_pair(self, fo_scores: Dict[int, float]) -> Optional[Dict[str, Any]]:
        """
        3. 特征优化主模块 FO: 【特征状元榜眼】
        逻辑：多维综合得分 No.1 与 No.2，若互斥则由 No.3 顺延替补
        """
        if not fo_scores:
            return None
        sorted_fo = sorted(fo_scores.items(), key=lambda x: x[1], reverse=True)
        top1 = sorted_fo[0][0]

        best_top2 = None
        for n, _ in sorted_fo[1:5]:
            syn = self.compute_pair_synergy(top1, n)
            if not syn['is_mutually_exclusive']:
                best_top2 = n
                break
        if not best_top2 and len(sorted_fo) > 1:
            best_top2 = sorted_fo[1][0]

        pair = self.get_pair_key(top1, best_top2)
        return {
            'module': 'FO_FeatureRank',
            'label': '特征状元榜眼',
            'pair': pair,
            'core_ball': top1,
            'partner_ball': best_top2,
            'reason': f"全维度综合评分状元{top1:02d}与榜眼{best_top2:02d}强强联合",
        }

    def extract_deep_pair(self, deep_picks: List[int], deep_consensus: List[int]) -> Optional[Dict[str, Any]]:
        """
        4. 深层关联挖掘 Deep: 【连体婴黄金搭档】
        逻辑：在深层爆发候选集 (final_picks / cross_consensus) 中，挑选历史共现 Lift 最高的一对连体婴
        """
        pool = list(set(deep_picks + deep_consensus))
        if len(pool) < 2:
            top_pairs = sorted(self.pair_counts_100.items(), key=lambda x: x[1], reverse=True)
            if top_pairs:
                pair = top_pairs[0][0]
                return {
                    'module': 'Deep_Association',
                    'label': '连体婴黄金搭档',
                    'pair': pair,
                    'core_ball': pair[0],
                    'partner_ball': pair[1],
                    'reason': f"历史高频共现搭档{pair[0]:02d}-{pair[1]:02d} (近100期同出{top_pairs[0][1]}次)",
                }
            return None

        best_pair = None
        best_lift = -1.0

        for a, b in itertools.combinations(pool, 2):
            syn = self.compute_pair_synergy(a, b)
            if syn['is_mutually_exclusive']:
                continue
            score = syn['lift_100'] * (1.0 + math.log1p(syn['count_100']))
            if score > best_lift:
                best_lift = score
                best_pair = (a, b)

        if not best_pair:
            best_pair = (pool[0], pool[1])

        pair = self.get_pair_key(best_pair[0], best_pair[1])
        syn = self.compute_pair_synergy(pair[0], pair[1])
        return {
            'module': 'Deep_Association',
            'label': '连体婴黄金搭档',
            'pair': pair,
            'core_ball': pair[0],
            'partner_ball': pair[1],
            'reason': f"深层规则共识连体婴{pair[0]:02d}-{pair[1]:02d} (近100期同出{syn['count_100']}次, Lift={syn['lift_100']}x)",
        }

    def extract_pure_pool_pair(self, pure_pool_scored: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        5. 纯净池定胆 PurePool: 【纯净金银双胆】
        逻辑：纯净池中结合规则分与 LR 概率最高的金胆(No.1)与银胆(No.2)
        """
        if not pure_pool_scored:
            return None
        sorted_pure = sorted(
            pure_pool_scored,
            key=lambda x: (x.get('lr_prob', 0) * 10.0 + x.get('score', 0)),
            reverse=True
        )
        if len(sorted_pure) < 2:
            return None

        n1 = sorted_pure[0]['number']
        n2 = None
        for item in sorted_pure[1:]:
            cand = item['number']
            syn = self.compute_pair_synergy(n1, cand)
            if not syn['is_mutually_exclusive']:
                n2 = cand
                break
        if not n2:
            n2 = sorted_pure[1]['number']

        pair = self.get_pair_key(n1, n2)
        syn = self.compute_pair_synergy(pair[0], pair[1])
        return {
            'module': 'PurePool_Scorer',
            'label': '纯净金银双胆',
            'pair': pair,
            'core_ball': pair[0],
            'partner_ball': n2,
            'reason': f"纯净池金胆{n1:02d}与银胆{n2:02d} (LR综合胜率最高, Lift={syn['lift_100']}x)",
        }

    # ═══════════════════════════════════════════════════════════════
    #  全局最优 1 组选2 综合收敛算法
    # ═══════════════════════════════════════════════════════════════

    def select_optimal_pick2(
        self,
        ef_scores: Optional[Dict[int, float]] = None,
        rw_scores: Optional[Dict[int, float]] = None,
        fo_scores: Optional[Dict[int, float]] = None,
        pure_pool_scored: Optional[List[Dict[str, Any]]] = None,
        deep_picks: Optional[List[int]] = None,
        deep_kills: Optional[List[int]] = None,
        deep_consensus: Optional[List[int]] = None,
        kill_numbers: Optional[List[int]] = None,
        high_conf_kills: Optional[List[int]] = None,
        b3_final5: Optional[List[int]] = None,
        trinity_top5: Optional[List[int]] = None,
        trinity_top12: Optional[List[int]] = None,
        recent_recommended_pairs: Optional[List[Tuple[int, int]]] = None,
    ) -> Dict[str, Any]:
        """
        综合多模块候选、双元共现 Lift、杀号一票否决、防死守冷冻熔断与共振加分，
        评选出全场唯一的【No.1 选2黄金搭档】以及【1胆3拖/1胆4拖资金对冲配单】。
        """
        ef_scores = ef_scores or {}
        rw_scores = rw_scores or {}
        fo_scores = fo_scores or {}
        pure_pool_scored = pure_pool_scored or []
        deep_picks = deep_picks or []
        deep_kills = deep_kills or []
        deep_consensus = deep_consensus or []
        kill_numbers = set(kill_numbers or [])
        high_conf_kills = set(high_conf_kills or [])
        b3_final5 = b3_final5 or []
        trinity_top5 = trinity_top5 or []
        trinity_top12 = trinity_top12 or []

        # 杀号红线
        absolute_kills = high_conf_kills | set(deep_kills[:2])
        warning_kills = kill_numbers | set(deep_kills)

        # 近期推荐对集合 (用于防死守冷冻换马机制)
        recent_pairs_set = set()
        if recent_recommended_pairs:
            for rp in recent_recommended_pairs:
                if rp and len(rp) == 2:
                    recent_pairs_set.add(self.get_pair_key(rp[0], rp[1]))

        # 1. 抽取 各大子模块专属 2 码
        module_pairs = []
        p_ef = self.extract_ef_pair(ef_scores)
        if p_ef: module_pairs.append(p_ef)

        p_rw = self.extract_rw_pair(rw_scores)
        if p_rw: module_pairs.append(p_rw)

        p_fo = self.extract_fo_pair(fo_scores)
        if p_fo: module_pairs.append(p_fo)

        p_deep = self.extract_deep_pair(deep_picks, deep_consensus)
        if p_deep: module_pairs.append(p_deep)

        p_pure = self.extract_pure_pool_pair(pure_pool_scored)
        if p_pure: module_pairs.append(p_pure)

        # 2. 汇总候选对与额外注入高Lift对
        candidate_pairs = {}
        single_nominations = collections.Counter()

        for mp in module_pairs:
            pair = mp['pair']
            single_nominations[pair[0]] += 1
            single_nominations[pair[1]] += 1
            if pair not in candidate_pairs:
                candidate_pairs[pair] = {
                    'pair': pair,
                    'nominated_by': [mp['label']],
                    'primary_reason': mp['reason'],
                }
            else:
                candidate_pairs[pair]['nominated_by'].append(mp['label'])

        # 3. 补充共振号码交叉
        core_hot_pool = list(set(b3_final5 + trinity_top5 + deep_picks[:3] + deep_consensus))
        for a, b in itertools.combinations(core_hot_pool, 2):
            pair = self.get_pair_key(a, b)
            if pair not in candidate_pairs:
                candidate_pairs[pair] = {
                    'pair': pair,
                    'nominated_by': ['多维共振交叉'],
                    'primary_reason': f"多维共振金胆{a:02d}与{b:02d}交叉组合",
                }

        # 4. 全局打分决胜
        kline_risk_map = {}
        try:
            if len(self.history) >= 100 and candidate_pairs:
                from backend.modules.kline_pick2.kline_engine import get_kline_risk_map
                kline_risk_map = get_kline_risk_map(list(candidate_pairs.keys()))
        except Exception:
            kline_risk_map = {}

        scored_candidates = []
        for pair, meta in candidate_pairs.items():
            a, b = pair
            syn = self.compute_pair_synergy(a, b)

            if a in absolute_kills or b in absolute_kills:
                continue

            kill_penalty = 1.0
            if a in warning_kills: kill_penalty *= 0.5
            if b in warning_kills: kill_penalty *= 0.5

            if syn['is_mutually_exclusive']:
                continue

            single_strength = (
                ef_scores.get(a, 0) + ef_scores.get(b, 0) +
                rw_scores.get(a, 0) * 1.5 + rw_scores.get(b, 0) * 1.5 +
                fo_scores.get(a, 0) * 0.05 + fo_scores.get(b, 0) * 0.05
            )

            nom_bonus = len(meta['nominated_by']) * 1.5 + (single_nominations[a] + single_nominations[b]) * 0.3
            lift_score = syn['lift_100'] * 2.0 + (syn['lift_total'] - 1.0) * 1.0
            count_bonus = math.log1p(syn['count_100']) * 0.8

            # 防死守冷冻熔断 (Cooldown / Anti-Streak): 连续推荐未全中则大幅降权强行换马
            is_cooling = pair in recent_pairs_set
            cooldown_penalty = 0.15 if is_cooling else 1.0

            # K 线形态与反向排雷系数
            kl_info = kline_risk_map.get(pair, {})
            kline_factor = 1.0
            kl_note = ""
            if kl_info.get("has_toxic"):
                kline_factor = 0.75
                kl_note = f" [K线反向避坑: {','.join(kl_info.get('toxic_signals', []))}]"
            elif kl_info.get("has_positive"):
                kline_factor = 1.15
                kl_note = f" [K线蓄势共振: {','.join(kl_info.get('positive_signals', []))}]"

            total_synergy_score = (single_strength * 0.4 + nom_bonus * 1.2 + lift_score * 1.8 + count_bonus) * kill_penalty * cooldown_penalty * kline_factor

            reason_text = meta['primary_reason'] + kl_note
            if is_cooling:
                reason_text += " [防死守冷冻中: 触发连推降权换马]"

            scored_candidates.append({
                'pair': pair,
                'score': round(total_synergy_score, 4),
                'lift_100': syn['lift_100'],
                'count_100': syn['count_100'],
                'count_total': syn['count_total'],
                'obs_prob_100': syn['obs_prob_100'],
                'nominated_by': meta['nominated_by'],
                'reason': reason_text,
                'is_cooling': is_cooling,
            })

        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        if scored_candidates:
            champion = scored_candidates[0]
        else:
            # 动态高频共现保底：绝不写死静态 (12, 24)，从近100期动态挖掘安全高频搭档
            sorted_pairs = sorted(self.pair_counts_100.items(), key=lambda x: x[1], reverse=True)
            fallback_pair = None
            for p_tuple, cnt in sorted_pairs:
                p_ordered = self.get_pair_key(p_tuple[0], p_tuple[1])
                if p_ordered[0] in absolute_kills or p_ordered[1] in absolute_kills:
                    continue
                if p_ordered in recent_pairs_set:
                    continue
                fallback_pair = p_ordered
                break
            if not fallback_pair:
                cand_pool = [x for x in (trinity_top5 or b3_final5 or [1, 2]) if x not in absolute_kills]
                fallback_pair = self.get_pair_key(cand_pool[0], cand_pool[1]) if len(cand_pool) >= 2 else (1, 2)

            syn_fb = self.compute_pair_synergy(fallback_pair[0], fallback_pair[1])
            champion = {
                'pair': fallback_pair,
                'score': 1.0,
                'lift_100': syn_fb.get('lift_100', 1.0),
                'count_100': syn_fb.get('count_100', 0),
                'count_total': syn_fb.get('count_total', 0),
                'obs_prob_100': syn_fb.get('obs_prob_100', 0.06),
                'nominated_by': ['动态高频共现保底'],
                'reason': f"系统安全保底黄金搭档{fallback_pair[0]:02d}-{fallback_pair[1]:02d} (近100期同出{syn_fb.get('count_100', 0)}次, Lift={syn_fb.get('lift_100', 1.0)}x)",
                'is_cooling': False,
            }

        hedge_pair = None
        for cand in scored_candidates[1:]:
            if cand['pair'][0] not in champion['pair'] and cand['pair'][1] not in champion['pair']:
                hedge_pair = cand
                break

        # 5. 资金管理优化：生成【1胆3拖 / 1胆4拖】对冲配单 (以大带小)
        p0, p1 = champion['pair']
        sc0 = ef_scores.get(p0, 0) + rw_scores.get(p0, 0) * 1.5 + fo_scores.get(p0, 0) * 0.05
        sc1 = ef_scores.get(p1, 0) + rw_scores.get(p1, 0) * 1.5 + fo_scores.get(p1, 0) * 0.05
        banker_ball = p0 if sc0 >= sc1 else p1

        # 候选拖码池：优先从 trinity_top12、trinity_top5、core_hot_pool 中选取与 banker 协同最高的伴侣码
        drag_candidate_pool = list(dict.fromkeys(
            (trinity_top12 or []) + (trinity_top5 or []) + core_hot_pool
        ))
        drag_candidates = [
            x for x in drag_candidate_pool 
            if x != banker_ball and x not in absolute_kills
        ]

        scored_drags = []
        for cand in drag_candidates:
            syn_d = self.compute_pair_synergy(banker_ball, cand)
            if syn_d['is_mutually_exclusive']:
                continue
            drag_sc = syn_d['lift_100'] * 2.0 + math.log1p(syn_d['count_100']) * 0.8
            scored_drags.append({
                'ball': cand,
                'score': drag_sc,
                'lift': syn_d['lift_100'],
                'count_100': syn_d['count_100']
            })
        scored_drags.sort(key=lambda x: x['score'], reverse=True)
        top4_drags = [d['ball'] for d in scored_drags[:4]]
        if len(top4_drags) < 4:
            for cand in range(1, 81):
                if cand != banker_ball and cand not in top4_drags and cand not in absolute_kills:
                    top4_drags.append(cand)
                if len(top4_drags) >= 4:
                    break

        dantuo_plan = {
            'banker': banker_ball,
            'drags_3': top4_drags[:3],
            'drags_4': top4_drags[:4],
            'combos_3': [self.get_pair_key(banker_ball, d) for d in top4_drags[:3]],
            'combos_4': [self.get_pair_key(banker_ball, d) for d in top4_drags[:4]],
            'cost_3_drag': 6,
            'cost_4_drag': 8,
            'payout_per_hit': 19,
            'net_profit_3_drag': 13,
            'net_profit_4_drag': 11,
            'rationale': f"以高确定性金胆 {banker_ball:02d} 为锚点，带动底仓 4 个高协同温热拖码 {top4_drags[:4]}，4注8元，拖中任一码即斩获19元净赚11元",
        }

        return {
            'optimal_pick2': champion['pair'],
            'champion_details': champion,
            'hedge_pick2': hedge_pair['pair'] if hedge_pair else None,
            'hedge_details': hedge_pair,
            'module_pairs': module_pairs,
            'all_scored_pairs': scored_candidates[:5],
            'dantuo_plan': dantuo_plan,
            'theoretical_baseline': '6.01%',
            'expected_lift': f"{champion['lift_100']:.2f}x",
        }
