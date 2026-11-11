# -*- coding: utf-8 -*-
"""CoreServiceMixin: dashboard/matrix/history/prediction and shared helpers"""
from __future__ import annotations

import os
import sys
import re
import json
import glob
import math
import logging
import collections
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir,
    get_project_root, data_path, get_storage_dir, _ensure_project_path,
)

logger = logging.getLogger("k8quant.service")


# 命中热力榜结果缓存：key = (n, latest_period)，当日同 n 不再重复计算
_hit_leaderboard_cache: Dict[Any, Any] = {}

# 全模块预测全景大盘缓存：key = (target_period, latest_draw_period)
_all_modules_overview_cache: Dict[Any, Any] = {}


class CoreServiceMixin:
    _FRESHNESS_DIRS = [
        # (key, 标注名, 相对目录, 文件名前缀, 文件名后缀)
        ("aggregation",   "汇总复盘",     "outputs/aggregation",  "aggregation_",              ".json"),
        ("unified_brain", "统一主脑决策", "outputs/unified_brain", "unified_decision_report_",  ".md"),
        ("sixteen",       "16期中热",     "outputs/reports",      "sixteen_analysis_report_",  ".md"),
        ("gold_pick2",    "定金选2",      "outputs/gold_pick2",   "定金选2预测_",               ".txt"),
        ("predictions",   "LSTM研报落盘", "outputs/predictions",  "prediction_",               ".txt"),
    ]

    _FRESHNESS_FILES = [
        ("master_review", "全模块复盘账", "storage/reviews/master_review_ledger.json"),
        ("evolution",     "进化门禁账",   "storage/evolution/evolution_ledger.json"),
        ("self_learning", "自学习状态",   "cache/self_learning_state.json"),
        ("paper_trading", "模拟盘台账",   "cache/paper_trading.jsonl"),
        ("daily_state",   "每日运行状态", "cache/daily_run_state.json"),
    ]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """获取大盘核心量化指标快照（供 AI 操盘顾问提取背景上下文）"""
        pred = self.get_latest_prediction() or {}
        sys_stat = self.get_system_status() or {}
        return {
            "latest_period": pred.get("period", sys_stat.get("target_period", "未知期号")),
            "latest_date": pred.get("date", sys_stat.get("target_date", "未知日期")),
            "consensus_core": {"golden_core": pred.get("top5_gold", [])},
            "recommended_5": pred.get("hidden_energy_5", []),
            "top12": pred.get("top12_pool", []),
            "overview_snapshot": {
                "golden_pair": pred.get("golden_pair", []),
                "golden_pair_reason": pred.get("golden_pair_reason", ""),
                "weights_plain": pred.get("weights_plain", "")
            }
        }

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态、最新期号与基础指标"""
        history = self.load_history(limit=5)
        latest_history = history[0] if history else None
        
        target_p = None
        if latest_history and str(latest_history["period"]).isdigit():
            target_p = str(int(latest_history["period"]) + 1)
        else:
            target_p = "2026232"
        
        # 查找最新报告
        reports = self.get_report_list()
        latest_report_meta = reports[0] if reports else None
        
        return {
            "status": "ONLINE",
            "system_name": "K8-Quant 智能量化决策系统",
            "version": "v5.0 Cyber Edition",
            "latest_draw_period": latest_history["period"] if latest_history else "N/A",
            "latest_draw_date": latest_history["date"] if latest_history else "N/A",
            "latest_draw_numbers": latest_history["numbers"] if latest_history else [],
            "target_period": target_p,
            "target_date": datetime.now().strftime("%Y-%m-%d"),
            "beacon_status": "NORMAL (正常运行)",
            "circuit_breaker": "ACTIVE (监控中)",
            "timestamp": datetime.now().isoformat()
        }

    def load_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """从 kl8_history_final.txt 加载历史开奖数据"""
        # 快乐8 标准质数池 (1 既非质也非合)
        _PRIMES = {
            2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
            31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79,
        }
        results = []
        if not os.path.exists(self.history_file):
            # 备用从 storage/raw/kl8_history_final.txt 读取
            raw_f = os.path.join(get_storage_dir(), "raw", "kl8_history_final.txt")
            if os.path.exists(raw_f):
                self.history_file = raw_f
            else:
                return results

        with open(self.history_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith("date:"):
                    continue
                try:
                    parts = line.split(",")
                    date_val = parts[0].replace("date:", "").strip()
                    period_val = parts[1].replace("period:", "").strip()
                    nums_str = parts[2].replace("numbers:", "").strip()
                    nums = [int(x) for x in nums_str.split("-") if x.isdigit()]
                    road0 = sum(1 for x in nums if x % 3 == 0)
                    road1 = sum(1 for x in nums if x % 3 == 1)
                    road2 = sum(1 for x in nums if x % 3 == 2)
                    prime_c = sum(1 for x in nums if x in _PRIMES)
                    comp_c = sum(1 for x in nums if x not in _PRIMES and x != 1)
                    has_01 = 1 in nums
                    results.append({
                        "date": date_val,
                        "period": period_val,
                        "numbers": nums,
                        "sum": sum(nums),
                        "odd_count": sum(1 for x in nums if x % 2 != 0),
                        "even_count": sum(1 for x in nums if x % 2 == 0),
                        "road0": road0,
                        "road1": road1,
                        "road2": road2,
                        "road_ratio": f"{road0}:{road1}:{road2}",
                        "prime_count": prime_c,
                        "composite_count": comp_c,
                        "prime_ratio": f"{prime_c}:{comp_c}",
                        "has_01": has_01,
                        "raw": line
                    })
                except Exception:
                    continue

        # 按期号降序排序
        results.sort(key=lambda x: int(x["period"]) if x["period"].isdigit() else 0, reverse=True)
        return results[:limit] if limit > 0 else results

    def get_history_paginated(self, page: int = 1, page_size: int = 20, period_query: str = "") -> Dict[str, Any]:
        """分页与条件检索历史开奖库"""
        all_data = self.load_history(limit=0)
        if period_query:
            all_data = [d for d in all_data if period_query in d["period"] or period_query in d["date"]]
        
        total = len(all_data)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_data[start:end]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
            "items": items
        }

    def get_report_list(self) -> List[Dict[str, Any]]:
        """获取 reports 目录下所有的每日分析报告"""
        search_dirs = [self.reports_dir, os.path.join(get_storage_dir(), "reports")]
        report_list = []
        seen_files = set()

        for r_dir in search_dirs:
            if not os.path.exists(r_dir):
                continue
            pattern = os.path.join(r_dir, "daily_analysis_report_*.md")
            files = glob.glob(pattern)
            for file_path in files:
                basename = os.path.basename(file_path)
                if basename in seen_files:
                    continue
                seen_files.add(basename)
                m = re.search(r"daily_analysis_report_(\d{8})\.md", basename)
                if m:
                    date_str = m.group(1)
                    formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                    target_period = "N/A"
                    is_honest = False
                    caliber_version = "v1.0 历史归档"
                    caliber_desc = "历史旧口径（未收缩对账）"
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as rf:
                            head = rf.read(2000)
                            pm = re.search(r"目标期号[\*：:\s]*(\d+)", head)
                            if pm:
                                target_period = pm.group(1)
                            if "v3.0" in head or "诚实实战口径" in head or int(date_str) >= 20260910:
                                is_honest = True
                                caliber_version = "v3.0 诚实口径"
                                caliber_desc = "100期收缩榜 · 零编造门禁"
                    except Exception:
                        pass
                    report_list.append({
                        "date": formatted_date,
                        "raw_date": date_str,
                        "period": target_period,
                        "filename": basename,
                        "path": file_path,
                        "is_honest_caliber": is_honest,
                        "caliber_version": caliber_version,
                        "caliber_desc": caliber_desc
                    })
        
        report_list.sort(key=lambda x: x["raw_date"], reverse=True)
        return report_list

    def _compute_live_prediction(self, history: List[Dict[str, Any]], n: int = 50) -> Dict[str, Any]:
        """基于最新 n 期开奖历史，实时计算一组兜底推荐（金胆/候选/黄金搭档/熵值等）。

        用途：当没有当日研判报告、或报告某字段缺失/解析失败时，
        用真实历史数据现场计算，保证页面数字随最新开奖动态刷新，
        而不是永远停留在同一组硬编码默认值。
        """
        # 2026-09-10 数据诚信整改：无历史时不再填 [0,0] 假搭档、假 radar_data、假 Lift=1.0；
        # 一律留空并显式标注 data_missing，由前端展示"数据缺失"。
        empty = {
            "period": "N/A",
            "golden_pair": [],
            "golden_pair_reason": "历史数据不足，请先同步开奖数据并运行全流程推演",
            "top5_gold": [],
            "top12_pool": [],
            "golden_core": [],
            "hidden_energy_5": [],
            "sub_pairs": [],
            "weights": {"EF": 0.4, "RW": 0.3, "FO": 0.3},
            "weights_plain": "蹭热度(EF) 40% + 抓冷门(RW) 30% + 找周期(FO) 30%",
            "weights_source": "静态默认值(0.40/0.30/0.30)，非自学习产出",
            "pure_pool": [],
            "shannon_entropy": 0.0,
            "golden_pair_score": None,
            "golden_pair_lift": None,
            "golden_pair_cooc": None,
            "risk_status": "NORMAL (数据待同步，建议正常配置)",
            "data_missing": True,
            "data_provenance": "无可用历史，字段留空占位；不含编造号码或统计量"
        }

        draws = history[:n]
        if not draws:
            return empty

        latest = draws[0]
        period = str(latest.get("period", "N/A"))
        date = latest.get("date", datetime.now().strftime("%Y-%m-%d"))
        target_period = str(int(period) + 1) if period.isdigit() else period

        # 近 n 期频次 + 遗漏统计
        freq = collections.Counter()
        last_seen = {}
        for idx, draw in enumerate(draws):
            for num in draw.get("numbers", []):
                freq[num] += 1
                last_seen[num] = idx  # 越靠前越新

        max_freq = max(freq.values()) if freq else 1
        draw_count = len(draws)
        omission = {num: last_seen.get(num, draw_count) for num in range(1, 81)}
        max_omit = max(omission.values()) or 1

        # 综合评分 = 热度(近n期频次归一化) * 0.5 + 冷度(遗漏归一化) * 0.5
        scores = {}
        for num in range(1, 81):
            f_score = freq.get(num, 0) / max_freq
            o_score = 1.0 - (omission[num] / max_omit)
            scores[num] = 0.5 * f_score + 0.5 * o_score

        def top_k(k):
            return [num for num, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]]

        top5 = top_k(5)
        top12 = top_k(12)
        core = top_k(3)
        # 不足 2 码时留空，不用 0 占位冒充号码（0 会被前端渲染成 "00" 假球）
        pair = top5[:2] if len(top5) >= 2 else []

        sub_pairs = []
        if len(top5) >= 2 and len(top12) >= 2:
            sub_pairs = [
                {"name": "能量双子星 (EF 蹭热度)", "pair": [top5[0], top12[1]], "tag": f"实时高频中心{top5[0]}与候选{top12[1]}共振"},
                {"name": "冷热弹簧搭档 (RW 抓冷门)", "pair": [top12[0], top5[-1]], "tag": "实时遗漏冷号与温态回暖号对冲"},
                {"name": "特征状元榜眼 (FO 找周期)", "pair": top5[:2], "tag": "实时综合评分状元与榜眼联合"},
            ]

        # 现场熵值（基于近 n 期号码频次分布）
        total = sum(freq.values()) or 1
        probs = [(freq.get(k, 0) / total) for k in range(1, 81)]
        probs = [p for p in probs if p > 0]
        entropy = -sum(p * math.log2(p) for p in probs) if probs else 0.0

        has_pair = len(pair) == 2
        return {
            "period": target_period,
            "date": date,
            "golden_pair": pair,
            "golden_pair_reason": (f"实时频率+遗漏共振金胆{pair[0]}与{pair[1]}交叉组合 (离线研判报告待更新)"
                                   if has_pair else "未解析到当期研判报告，且历史样本不足以生成选2搭档"),
            "top5_gold": top5,
            "top12_pool": top12,
            "golden_core": core,
            "hidden_energy_5": top5,
            "sub_pairs": sub_pairs,
            "weights": {"EF": 0.4, "RW": 0.3, "FO": 0.3},
            "weights_plain": "蹭热度(EF) 40% + 抓冷门(RW) 30% + 找周期(FO) 30%",
            "weights_source": "静态默认值(0.40/0.30/0.30)，非自学习产出",
            "pure_pool": top12[:5],
            "shannon_entropy": round(entropy, 4),
            "golden_pair_score": round(scores[pair[0]] + scores[pair[1]], 2) if has_pair else None,
            # 该组合未做历史回测，Lift / 共现增益不编造（原实现恒填 1.0 与 0）
            "golden_pair_lift": None,
            "golden_pair_cooc": (sum(1 for d in draws if pair[0] in d.get("numbers", []) and pair[1] in d.get("numbers", []))
                                 if has_pair else None),
            "risk_status": "NORMAL (信标稳定，建议正常配置)",
            "data_missing": False,
            "data_provenance": "无当日研判报告，号码由近期频率+遗漏实时计算；权重为静态默认值，非自学习产出"
        }

    def get_latest_prediction(self) -> Dict[str, Any]:
        """解析最新的预测研判报告，提取 Top 5 / 12、定金选2、黄金搭档与各维度信息。

        修复要点：
        1. 报告字段常被 Markdown 加粗包裹（如 **黄金搭档**：`55 - 61`），旧正则的
           「字段名[：:]」无法命中（中间隔着 **），导致长期回退到硬编码默认值；
           这里先规范化文本（剥离 ** 与 ` ，统一全角冒号），再用更精准的正则解析。
        2. 缺失或解析失败的字段，用基于实时历史的 _compute_live_prediction 结果兜底，
           保证数字随最新开奖动态更新，而不再是永远不变的默认号。
        """
        history = self.load_history(limit=50)
        live = self._compute_live_prediction(history)
        default_pred = {
            "period": live["period"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "golden_pair": live["golden_pair"],
            "golden_pair_reason": live["golden_pair_reason"],
            "top5_gold": live["top5_gold"],
            "top12_pool": live["top12_pool"],
            "golden_core": live["golden_core"],
            "hidden_energy_5": live["hidden_energy_5"],
            "sub_pairs": live["sub_pairs"],
            "weights": live["weights"],
            "weights_plain": live["weights_plain"],
            "weights_source": live["weights_source"],
            "pure_pool": live["pure_pool"],
            "shannon_entropy": live["shannon_entropy"],
            "golden_pair_score": live["golden_pair_score"],
            "golden_pair_lift": live["golden_pair_lift"],
            "golden_pair_cooc": live["golden_pair_cooc"],
            "risk_status": live["risk_status"],
            "data_missing": live["data_missing"],
            "data_provenance": live["data_provenance"]
        }

        reports = self.get_report_list()
        if not reports:
            return default_pred

        latest_report_file = reports[0]["path"]
        try:
            with open(latest_report_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 规范化：剥离 Markdown 加粗 ** 与行内反引号 ` ，统一全角冒号为半角
            norm = content.replace('**', '').replace('`', '').replace('：', ':')

            pred = default_pred.copy()
            pred["date"] = reports[0]["date"]

            def parse_list(pattern):
                m = re.search(pattern, norm)
                if not m:
                    return None
                vals = [int(x.strip()) for x in m.group(1).split(',') if x.strip().isdigit()]
                return vals if vals else None

            # 目标期号
            m_period = re.search(r"目标期号:\s*(\d+)", norm)
            if m_period:
                pred["period"] = m_period.group(1)

            # 极简选2 黄金搭档（取首个「黄金搭档: X - Y」推荐行）
            m_pair = re.search(r"黄金搭档:\s*(\d+)\s*[-—–]\s*(\d+)", norm)
            if m_pair:
                pred["golden_pair"] = [int(m_pair.group(1)), int(m_pair.group(2))]

            # 黄金搭档推荐理由（用报告原文，避免与解析出的号码不一致）
            m_reason = re.search(r"核心推荐理由:\s*([^\n]+)", norm)
            if m_reason:
                pred["golden_pair_reason"] = m_reason.group(1).strip()
            elif len(pred["golden_pair"]) == 2 and all(x > 0 for x in pred["golden_pair"]):
                pred["golden_pair_reason"] = f"多维共振金胆{pred['golden_pair'][0]}与{pred['golden_pair'][1]}交叉组合"

            # 黄金搭档 协同分 / Lift
            m_score = re.search(r"综合协同分:\s*([\d\.]+)", norm)
            if m_score:
                pred["golden_pair_score"] = float(m_score.group(1))
            m_lift = re.search(r"历史共现增益\s*\(Lift\):\s*([\d\.]+)\s*x", norm)
            if m_lift:
                pred["golden_pair_lift"] = float(m_lift.group(1))
            m_cooc = re.search(r"近100期同出\s*(\d+)\s*次", norm)
            if m_cooc:
                pred["golden_pair_cooc"] = int(m_cooc.group(1))

            # Top 5 / Top 12
            v = parse_list(r"极秘\s*Top\s*5:\s*\[(.*?)\]")
            if v:
                pred["top5_gold"] = v
            v = parse_list(r"极秘\s*Top\s*12:\s*\[(.*?)\]")
            if v:
                pred["top12_pool"] = v

            # Golden Core
            v = parse_list(r"高频共振集群:\s*\[(.*?)\]")
            if v:
                pred["golden_core"] = v

            # Hidden Energy 5
            v = parse_list(r"最终推荐\s*\(5\s*码\):\s*\[(.*?)\]")
            if v:
                pred["hidden_energy_5"] = v

            # 权重
            m_weights = re.search(r"动态模型赋权:\s*EF:([\d\.]+)\s*RW:([\d\.]+)\s*FO:([\d\.]+)", norm)
            if m_weights:
                pred["weights"] = {
                    "EF": float(m_weights.group(1)),
                    "RW": float(m_weights.group(2)),
                    "FO": float(m_weights.group(3))
                }
                pred["weights_plain"] = f"蹭热度(EF) {int(pred['weights']['EF']*100)}% + 抓冷门(RW) {int(pred['weights']['RW']*100)}% + 找周期(FO) {int(pred['weights']['FO']*100)}%"

            # 纯净池
            v = parse_list(r"纯净池号码:\s*\[(.*?)\]")
            if v:
                pred["pure_pool"] = v

            # 熵值
            m_entropy = re.search(r"系统当前熵值:\s*([\d\.]+)", norm)
            if m_entropy:
                pred["shannon_entropy"] = float(m_entropy.group(1))

            return pred
        except Exception:
            return default_pred

    def get_matrix_80_stats(self) -> Dict[str, Any]:
        """
        计算 1-80 号码全景态势数据：
        - 遗漏期数 (RW 抓冷门)
        - 近30期出现频次 (EF 蹭热度)
        - 尾数与分区
        - 综合能级评分 (0-100)
        - 标签 (金胆/候选/爆发热码/极冷回补/中性)
        """
        history = self.load_history(limit=50)
        pred = self.get_latest_prediction()
        top5_set = set(pred.get("top5_gold", []))
        top12_set = set(pred.get("top12_pool", []))
        pair_set = set(pred.get("golden_pair", []))
        he5_set = set(pred.get("hidden_energy_5", []))

        # 计算每个号码的当前遗漏与频次
        omissions = {i: 0 for i in range(1, 81)}
        freq_30 = {i: 0 for i in range(1, 81)}
        recent_draws = history[:30] if len(history) >= 30 else history

        # 计算近30期频次
        for d in recent_draws:
            for num in d["numbers"]:
                if 1 <= num <= 80:
                    freq_30[num] += 1

        # 计算当前遗漏
        for num in range(1, 81):
            omiss = 0
            for d in history:
                if num in d["numbers"]:
                    break
                omiss += 1
            omissions[num] = omiss

        # 自适应冷/热候选集：剔除已被预测集占用的号码后，按遗漏/频次排序取 top ~15%，
        # 阈值随数据分布自适应，避免固定阈值在不同数据下失衡（“只有几个/太多”）。
        pred_occupied = top5_set | pair_set | top12_set | he5_set
        n_ptr = max(5, int(round(80 * 0.15)))  # 约 12 个
        cold_rank = sorted((n for n in range(1, 81) if n not in pred_occupied), key=lambda n: omissions[n], reverse=True)
        hot_rank = sorted((n for n in range(1, 81) if n not in pred_occupied), key=lambda n: freq_30[n], reverse=True)
        cold_candidates = set(cold_rank[:n_ptr])
        hot_candidates = set(hot_rank[:n_ptr])
        # 当前档位对应的实际阈值（供前端展示与筛选一致性）
        cold_threshold = omissions[cold_rank[n_ptr - 1]] if len(cold_rank) >= n_ptr else max(omissions.values())
        hot_threshold = freq_30[hot_rank[n_ptr - 1]] if len(hot_rank) >= n_ptr else max(freq_30.values())

        # 构建 1-80 号码矩阵卡片
        matrix_list = []
        for num in range(1, 81):
            freq = freq_30.get(num, 0)
            omiss = omissions.get(num, 0)
            
            # 计算综合能级得分 (0-100)
            heat_score = (freq / 30.0) * 50  # 频次占比
            rebound_score = min(omiss * 3.5, 35)  # 遗漏回补分
            composite_energy = round(heat_score + rebound_score + (15 if num in top5_set else (8 if num in top12_set else 0)), 1)
            composite_energy = min(composite_energy, 99.9)

            # 确定标签与层级（优先级：金胆 > 黄金搭档 > 重点候选 > 隐动能5 > 极冷 > 极热 > 平稳）
            if num in top5_set:
                tag = "金胆核心"
                category = "gold_top5"
                tag_color = "gold"
            elif num in pair_set:
                tag = "黄金搭档"
                category = "golden_pair"
                tag_color = "gold"
            elif num in top12_set:
                tag = "重点备选"
                category = "top12_candidate"
                tag_color = "cyan"
            elif num in he5_set:
                tag = "隐动能5"
                category = "hidden_energy"
                tag_color = "emerald"
            elif num in cold_candidates:
                tag = f"憋了{omiss}期 (冷)"
                category = "cold_rebound"
                tag_color = "purple"
            elif num in hot_candidates:
                tag = f"30期开{freq}次 (热)"
                category = "hot_energy"
                tag_color = "crimson"
            else:
                tag = "平稳状态"
                category = "neutral"
                tag_color = "gray"

            zone = 1 if num <= 20 else (2 if num <= 40 else (3 if num <= 60 else 4))
            tail = num % 10

            matrix_list.append({
                "number": num,
                "display": f"{num:02d}",
                "energy": composite_energy,
                "omission": omiss,
                "freq_30": freq,
                "zone": zone,
                "tail": tail,
                "tag": tag,
                "tag_color": tag_color,
                "category": category,
                "is_top5": num in top5_set,
                "is_top12": num in top12_set,
                "is_pair": num in pair_set
            })

        # 尾数统计 (0-9)
        tail_counts = {i: 0 for i in range(10)}
        latest_draw = history[0]["numbers"] if history else []
        for n in latest_draw:
            tail_counts[n % 10] += 1

        tail_stats = []
        for t in range(10):
            c = tail_counts[t]
            tail_stats.append({
                "tail": t,
                "count": c,
                "status": "全灭 (强烈补偿)" if c == 0 else ("过热" if c >= 4 else "正常")
            })

        # 四分区统计
        zone_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for n in latest_draw:
            z = 1 if n <= 20 else (2 if n <= 40 else (3 if n <= 60 else 4))
            zone_counts[z] += 1

        return {
            "matrix": matrix_list,
            "tail_stats": tail_stats,
            "zone_stats": [
                {"zone": "一区 (01-20)", "count": zone_counts[1], "ratio": f"{zone_counts[1]/20:.1%}" if latest_draw else None},
                {"zone": "二区 (21-40)", "count": zone_counts[2], "ratio": f"{zone_counts[2]/20:.1%}" if latest_draw else None},
                {"zone": "三区 (41-60)", "count": zone_counts[3], "ratio": f"{zone_counts[3]/20:.1%}" if latest_draw else None},
                {"zone": "四区 (61-80)", "count": zone_counts[4], "ratio": f"{zone_counts[4]/20:.1%}" if latest_draw else None}
            ],
            "total_count": 80,
            "summary": {
                "top5_count": sum(1 for c in matrix_list if c["category"] == "gold_top5"),
                "top12_count": sum(1 for c in matrix_list if c["category"] == "top12_candidate"),
                "pair_count": sum(1 for c in matrix_list if c["category"] == "golden_pair"),
                "hidden_count": sum(1 for c in matrix_list if c["category"] == "hidden_energy"),
                "cold_count": sum(1 for c in matrix_list if c["category"] == "cold_rebound"),
                "hot_count": sum(1 for c in matrix_list if c["category"] == "hot_energy"),
                "neutral_count": sum(1 for c in matrix_list if c["category"] == "neutral"),
                "cold_threshold": cold_threshold,
                "hot_threshold": hot_threshold
            }
        }

    def get_history_trends(self, limit: int = 30) -> Dict[str, Any]:
        """获取最近 30 期的开奖走势与命中率复盘折线数据"""
        reports = self.get_report_list()
        report_map = {r["date"]: r["path"] for r in reports}
        history = self.load_history(limit=limit)
        
        periods = []
        dates = []
        top5_hits = []
        top12_hits = []
        draw_sums = []
        odd_ratios = []

        for item in reversed(history):
            p = item["period"]
            d = item["date"]
            nums = item["numbers"]
            periods.append(p)
            dates.append(d)
            draw_sums.append(sum(nums))
            odd_count = sum(1 for x in nums if x % 2 != 0)
            odd_ratios.append(round(odd_count / len(nums), 2) if nums else 0.5)

            # 尝试从当期历史报告中匹配命中数
            t5_hit = None
            t12_hit = None
            if d in report_map:
                try:
                    with open(report_map[d], "r", encoding="utf-8", errors="ignore") as f:
                        c_text = f.read(2000)
                        m5 = re.search(r"Top5\s*命中\s*`?(\d+)/5`?", c_text)
                        if m5:
                            t5_hit = int(m5.group(1))
                        m12 = re.search(r"Top12\s*命中\s*`?(\d+)/12`?", c_text)
                        if m12:
                            t12_hit = int(m12.group(1))
                except Exception:
                    pass
            top5_hits.append(t5_hit)
            top12_hits.append(t12_hit)

        _v5 = [x for x in top5_hits if x is not None]
        _v12 = [x for x in top12_hits if x is not None]
        return {
            "periods": periods,
            "dates": dates,
            "top5_hits": top5_hits,
            "top12_hits": top12_hits,
            "draw_sums": draw_sums,
            "odd_ratios": odd_ratios,
            "avg_top5_hit": round(sum(_v5) / len(_v5), 2) if _v5 else None,
            "avg_top12_hit": round(sum(_v12) / len(_v12), 2) if _v12 else None
        }

    def get_number_detail(self, num: int) -> Dict[str, Any]:
        """获取单个号码的近 30 期详细走势、搭档关联度与多维形态特征"""
        if not (1 <= num <= 80):
            return {"error": "Invalid number"}

        history = self.load_history(limit=50)
        draws_appearance = []
        for item in history[:30]:
            is_in = num in item["numbers"]
            draws_appearance.append({
                "period": item["period"],
                "date": item["date"],
                "hit": is_in
            })

        # 计算最常同时开出的搭档 Top 5 (Co-occurrence)
        pair_counts = collections.Counter()
        for item in history:
            if num in item["numbers"]:
                for other in item["numbers"]:
                    if other != num:
                        pair_counts[other] += 1

        top_buddies = []
        for other, count in pair_counts.most_common(5):
            top_buddies.append({
                "number": other,
                "co_count": count,
                "lift": round((count / max(len(history), 1)) / (20/80 * 20/80), 2)
            })

        primes = {
            2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
            53, 59, 61, 67, 71, 73, 79,
        }
        zone = 1 if num <= 20 else (2 if num <= 40 else (3 if num <= 60 else 4))
        road = num % 3
        if num == 1:
            prime_kind, prime_label = "neither", "非质非合"
        elif num in primes:
            prime_kind, prime_label = "prime", "质数"
        else:
            prime_kind, prime_label = "composite", "合数"

        # 近30期遗漏（从最新往回数，未开出的连续期数）
        omission = 0
        for item in history:
            if num in item["numbers"]:
                break
            omission += 1

        return {
            "number": num,
            "display": f"{num:02d}",
            "zone": zone,
            "tail": num % 10,
            "road": road,
            "road_label": f"{road}路",
            "prime_kind": prime_kind,
            "prime_label": prime_label,
            "odd_even": "奇数" if num % 2 else "偶数",
            "omission": omission,
            "appearances_30": draws_appearance,
            "total_hits_30": sum(1 for x in draws_appearance if x["hit"]),
            "top_buddies": top_buddies,
        }

    def get_lottery_trends(self, limit: int = 100) -> Dict[str, Any]:
        """
        获取开奖号码走势图数据（严格按开奖日期/期号升序展示）：
        - limit: 展示历史期数，默认 100 期
        - 包含每期的 80 码出号命中标记与动态累积遗漏值
        - 包含选定 N 期内 1-80 号码的出现次数、平均遗漏、最大遗漏、最大连出
        - 包含和值、奇偶比、四大区间出号数等量化指标
        """
        if limit <= 0:
            limit = 100
        
        warmup = 100
        total_need = limit + warmup
        all_raw = self.load_history(limit=total_need)
        if not all_raw:
            return {"draws": [], "ball_stats": [], "summary": {}}
        
        # 整体按期号升序排序 (从旧到新，即早 -> 晚)
        all_asc = sorted(all_raw, key=lambda x: int(x["period"]) if x["period"].isdigit() else 0)
        
        # 逐期正向推进计算 1-80 号码的精确遗漏值
        curr_omiss = {n: 0 for n in range(1, 81)}
        
        warmup_count = max(0, len(all_asc) - limit)
        for d in all_asc[:warmup_count]:
            hit_set = set(d["numbers"])
            for n in range(1, 81):
                if n in hit_set:
                    curr_omiss[n] = 0
                else:
                    curr_omiss[n] += 1
                    
        target_draws = all_asc[warmup_count:]
        
        draw_items = []
        freq_map = {n: 0 for n in range(1, 81)}
        max_omiss_map = {n: 0 for n in range(1, 81)}
        consec_map = {n: 0 for n in range(1, 81)}
        max_consec_map = {n: 0 for n in range(1, 81)}
        
        for d in target_draws:
            nums = sorted(d["numbers"])
            hit_set = set(nums)
            
            period_omissions = [0] * 80
            
            for n in range(1, 81):
                if n in hit_set:
                    curr_omiss[n] = 0
                    freq_map[n] += 1
                    consec_map[n] += 1
                    if consec_map[n] > max_consec_map[n]:
                        max_consec_map[n] = consec_map[n]
                    period_omissions[n - 1] = 0
                else:
                    curr_omiss[n] += 1
                    consec_map[n] = 0
                    period_omissions[n - 1] = curr_omiss[n]
                    
                if curr_omiss[n] > max_omiss_map[n]:
                    max_omiss_map[n] = curr_omiss[n]
            
            # 计算四大区间分布
            z1 = sum(1 for x in nums if x <= 20)
            z2 = sum(1 for x in nums if 21 <= x <= 40)
            z3 = sum(1 for x in nums if 41 <= x <= 60)
            z4 = sum(1 for x in nums if x >= 61)
            
            odd_c = sum(1 for x in nums if x % 2 != 0)
            even_c = 20 - odd_c
            sum_val = sum(nums)
            
            draw_items.append({
                "period": d["period"],
                "date": d["date"],
                "numbers": nums,
                "omissions": period_omissions,
                "sum": sum_val,
                "odd_count": odd_c,
                "even_count": even_c,
                "zone_counts": [z1, z2, z3, z4]
            })
            
        # 计算 80 码的汇总统计指标
        ball_stats = []
        total_p = len(draw_items)
        for n in range(1, 81):
            hits = freq_map[n]
            avg_omiss = round((total_p - hits) / (hits + 1), 1) if (hits + 1) > 0 else total_p
            ball_stats.append({
                "number": n,
                "display": f"{n:02d}",
                "zone": 1 if n <= 20 else (2 if n <= 40 else (3 if n <= 60 else 4)),
                "tail": n % 10,
                "frequency": hits,
                "frequency_rate": round(hits / total_p * 100, 1) if total_p > 0 else 0,
                "max_omission": max_omiss_map[n],
                "avg_omission": avg_omiss,
                "max_consecutive": max_consec_map[n],
                "current_omission": curr_omiss[n]
            })
            
        summary = {
            "total_periods": total_p,
            "start_period": draw_items[0]["period"] if draw_items else "",
            "end_period": draw_items[-1]["period"] if draw_items else "",
            "start_date": draw_items[0]["date"] if draw_items else "",
            "end_date": draw_items[-1]["date"] if draw_items else "",
            "avg_sum": round(sum(d["sum"] for d in draw_items) / total_p, 1) if total_p > 0 else 0,
            "min_sum": min((d["sum"] for d in draw_items), default=0),
            "max_sum": max((d["sum"] for d in draw_items), default=0),
        }

        # 实时生成走势图三大操盘实战大白话研判指南 (根据最新真实开奖动态计算)
        tactics = self._generate_live_tactics(draw_items, ball_stats)
        
        return {
            "draws": draw_items,
            "ball_stats": ball_stats,
            "summary": summary,
            "tactics": tactics
        }

    def _generate_live_tactics(self, draw_items: List[Dict[str, Any]], ball_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """根据真实开奖实时生成走势图三大操盘实战大白话研判指南"""
        if not draw_items:
            return {
                "target_period": "",
                "hot_momentum": "暂无历史开奖数据，请检查开奖源同步情况。",
                "cold_omission": "暂无历史开奖数据，请检查开奖源同步情况。",
                "neighbor_diagonal": "暂无历史开奖数据，请检查开奖源同步情况。"
            }
        
        last_d = draw_items[-1]
        last_p = str(last_d.get("period", ""))
        last_nums = sorted(last_d.get("numbers", []))
        last_set = set(last_nums)
        
        # 1. 冷热势头 (连号与热码)
        streaks = {}
        for n in last_nums:
            c = 1
            for d in reversed(draw_items[:-1]):
                if n in d.get("numbers", []):
                    c += 1
                else:
                    break
            streaks[n] = c
        hot_streaks = sorted([(n, c) for n, c in streaks.items() if c >= 2], key=lambda x: x[1], reverse=True)
        
        recent_5 = draw_items[-5:]
        recent_counts = {}
        for d in recent_5:
            for n in d.get("numbers", []):
                recent_counts[n] = recent_counts.get(n, 0) + 1
        top_recent_list = [f"{n:02d}" for n, cnt in sorted(recent_counts.items(), key=lambda x: x[1], reverse=True) if cnt >= 3 and n in last_set][:4]
        top_recent_str = "、".join(top_recent_list)
        
        if hot_streaks:
            streak_desc = "、".join([f"{n:02d}号(连出{c}期)" for n, c in hot_streaks[:3]])
            hot_text = f"第 {last_p} 期开出后：当前连庄爆发热码为【{streak_desc}】，正处爆发期，热势未退前适合顺势跟进；近5期高频活跃的还有【{top_recent_str}】。"
        else:
            hot_text = f"第 {last_p} 期开出后盘面分布相对均衡，暂无连出2期以上的极端连庄号。近5期相对活跃的号码为【{top_recent_str}】，可重点防守温热回补。"
            
        # 2. 抓冷门回补 (极限遗漏)
        omiss_list = sorted([(s["number"], s["current_omission"]) for s in ball_stats], key=lambda x: x[1], reverse=True)
        top_cold = omiss_list[:3]
        cold_desc = "、".join([f"{n:02d}号(已遗漏{om}期)" for n, om in top_cold])
        cold_text = f"截至第 {last_p} 期：全盘憋得最久的极端冷号为【{cold_desc}】。实战法则：根据“风水轮流转”（大白话：均值回归），冷号遗漏达到两位数后反弹势能骤增，今晚适合挑1~2个防守冷门回补！"
        
        # 3. 看邻居与斜连线
        diagonals = []
        if len(draw_items) >= 2:
            prev_d = draw_items[-2]
            prev_set = set(prev_d.get("numbers", []))
            for p in sorted(prev_set):
                if p + 1 in last_set and p + 2 <= 80:
                    diagonals.append(f"前天{p:02d} ➔ 昨晚{p+1:02d} ➔ 顺势指引【{p+2:02d}】")
                if p - 1 in last_set and p - 2 >= 1:
                    diagonals.append(f"前天{p:02d} ➔ 昨晚{p-1:02d} ➔ 顺势指引【{p-2:02d}】")
                    
        diag_sample = "；".join(diagonals[:2]) if diagonals else "当前暂无单步斜对角线"
        
        # 挑出昨晚 2 个代表性关键号的左右邻居
        key_balls = []
        for d in diagonals[:2]:
            for num_cand in last_nums:
                if f"昨晚{num_cand:02d}" in d and num_cand not in key_balls:
                    key_balls.append(num_cand)
        if len(key_balls) < 2:
            for n, c in hot_streaks:
                if n not in key_balls:
                    key_balls.append(n)
                if len(key_balls) >= 2:
                    break
        if len(key_balls) < 2:
            for n in last_nums:
                if n not in key_balls:
                    key_balls.append(n)
                if len(key_balls) >= 2:
                    break
                    
        neigh_desc = "、".join([f"昨晚开出{k:02d}号(重点盯防左右邻居 {max(1, k-1):02d} 与 {min(80, k+1):02d})" for k in key_balls[:2]])
        neigh_text = f"{neigh_desc}；同时走势图正走出清晰的爬楼梯斜连线：{diag_sample}。实战法则：将此类斜连落点与邻号打包，是抓【选2/选3】最佳搭档（大白话：连体婴）的黄金切入点！"
        
        return {
            "target_period": last_p,
            "hot_momentum": hot_text,
            "cold_omission": cold_text,
            "neighbor_diagonal": neigh_text
        }

    def get_daily_points_info(self) -> Dict[str, Any]:
        """获取点位库当前状态、最新录入点位与推荐目标期信息"""
        try:
            from backend.data_acquisition.daily_points_manager import (
                get_next_target_info,
                load_daily_points,
                analyze_points_distribution
            )
            target_info = get_next_target_info()
            all_pts = load_daily_points()
            
            analysis = None
            if target_info["already_input"]:
                analysis = analyze_points_distribution(target_info["existing_points"])
                
            return {
                "status": "ok",
                "target_info": target_info,
                "total_records": len(all_pts),
                "analysis": analysis
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_daily_points_history(self, limit: int = 30) -> Dict[str, Any]:
        """获取最近 N 期点位记录与历史开奖命中对账"""
        try:
            from backend.data_acquisition.daily_points_manager import load_daily_points
            all_pts = load_daily_points()
            
            # 读取历史开奖
            draws_map = {}
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        m_iss = re.search(r"period:(\d+)", line)
                        m_nums = re.search(r"numbers:([0-9\-]+)", line)
                        if m_iss and m_nums:
                            draws_map[m_iss.group(1)] = {int(x) for x in m_nums.group(1).split("-") if x.isdigit()}
                            
            sorted_issues = sorted(all_pts.keys(), key=int, reverse=True)[:limit]
            records = []
            for iss in sorted_issues:
                item = all_pts[iss]
                pts = item["points"]
                pts_set = set(pts)
                
                drawn_nums = draws_map.get(iss, set())
                hit_nums = sorted(list(pts_set & drawn_nums)) if drawn_nums else []
                is_drawn = len(drawn_nums) > 0
                
                records.append({
                    "period": iss,
                    "date": item["date"],
                    "points": pts,
                    "points_str": " ".join(f"{x:02d}" for x in pts),
                    "is_drawn": is_drawn,
                    "hits_count": len(hit_nums) if is_drawn else None,
                    "hit_numbers": hit_nums if is_drawn else []
                })
                
            return {
                "status": "ok",
                "total_count": len(all_pts),
                "records": records
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "records": []}

    def submit_daily_points(self, date_str: str, period_str: str, raw_points: str, overwrite: bool = True) -> Dict[str, Any]:
        """提交并保存新的点位数据，执行严格格式校验与多维画像"""
        try:
            from backend.data_acquisition.daily_points_manager import (
                parse_points_input,
                validate_points_list,
                analyze_points_distribution,
                save_daily_points
            )
            parsed = parse_points_input(raw_points)
            valid, msg = validate_points_list(parsed)
            if not valid:
                return {"status": "error", "message": msg}
                
            save_res = save_daily_points(date_str, period_str, parsed, overwrite=overwrite)
            if save_res["status"] != "ok":
                return save_res
                
            analysis = analyze_points_distribution(parsed)
            return {
                "status": "ok",
                "save_result": save_res,
                "analysis": analysis
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _build_actual_map(self) -> Dict[str, List[int]]:
        """构建 期号 -> 实际开奖号码 映射（用于补齐 walk-forward rows 里缺失的 actual）"""
        actual_map: Dict[str, List[int]] = {}
        if os.path.exists(self.history_file):
            with open(self.history_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m_iss = re.search(r"period:(\d+)", line)
                    m_nums = re.search(r"numbers:([0-9\-]+)", line)
                    if m_iss and m_nums:
                        actual_map[m_iss.group(1)] = [int(x) for x in m_nums.group(1).split("-") if x.isdigit()]
        return actual_map

    def _norm_wf_rows(self, raw_rows, pkey, rkey, tkey=None, reverse=False, first_as_top=False):
        """把各模块 walk-forward 的原始 rows 归一化为 [{period, recommended, top1}]（最新在前）"""
        out = []
        for r in raw_rows or []:
            try:
                p = str(r.get(pkey, ""))
                if not p:
                    continue
                rec = r.get(rkey, [])
                if not isinstance(rec, (list, tuple)):
                    rec = [rec] if rec is not None else []
                rec = [int(x) for x in rec if str(x).isdigit()]
                if not rec:
                    continue
                top1 = None
                if tkey and r.get(tkey) is not None:
                    try:
                        top1 = int(r.get(tkey))
                    except Exception:
                        top1 = None
                if top1 is None and first_as_top and isinstance(r.get(tkey), (list, tuple)) and r.get(tkey):
                    try:
                        top1 = int(r.get(tkey)[0])
                    except Exception:
                        top1 = None
                if top1 is None and first_as_top:
                    top1 = rec[0]
                out.append({"period": p, "recommended": rec, "top1": top1})
            except Exception:
                continue
        # 各模块原始行序可能新旧相反，统一为最新在前
        if reverse:
            out.reverse()
        return out

    def get_hit_leaderboard(self, n: int = 10) -> Dict[str, Any]:
        """跨模块每日命中热力榜：整合各预测模块的 Walk-Forward 命中，按命中率排序"""
        baseline = 25.0  # 快乐8 单码先验命中率 20/80
        actual_map = self._build_actual_map()
        latest_period_key = max(actual_map.keys(), key=lambda p: int(p)) if actual_map else None

        cache_key = (n, latest_period_key)
        if cache_key in _hit_leaderboard_cache:
            return _hit_leaderboard_cache[cache_key]

        module_results = []
        period_set = set()

        def compute_metrics(rec, actual, is_kill):
            size = len(set(rec))
            if size <= 0 or not actual:
                return None
            if is_kill:
                hit_count = sum(1 for x in set(rec) if x not in actual)
            else:
                hit_count = sum(1 for x in set(rec) if x in actual)
            rate = hit_count / size * 100.0
            return {
                "size": size,
                "hit_count": hit_count,
                "hit_rate": round(rate, 2),
                "lift": round(rate / baseline, 2)
            }

        # ── 1. 三维主系统：来自每日自动复盘总账本（review_*.json 的 hit_stats 已算好） ──
        try:
            ledger = self.get_daily_reviews_ledger(limit=200)
            recs = ledger.get("records", [])
            series = []
            for rec in recs:
                p = str(rec.get("period", ""))
                if p not in actual_map:
                    continue
                hits = rec.get("top12_hits", 0)
                rate = rec.get("top12_rate", 0.0) * 100.0
                series.append({
                    "period": p, "size": 12, "hit_count": hits,
                    "hit_rate": round(rate, 2), "lift": round(rate / baseline, 2),
                    "top1": None, "top1_hit": None, "recommended": []
                })
                period_set.add(p)
            if series:
                module_results.append({"id": "trinity", "name": "三维融合主系统", "pick_type": "pick",
                                       "series": series[:n]})
        except Exception:
            pass

        # ── 2. 其余模块：调用各自 walk-forward review，归一化后与 actual 对账 ──
        # C3 整改 (2026-09-10): 原各样例写死 (30) —— 无论前端选 50/100/200 期,
        # 这些模块永远只回 30 期数据。现全部透传 n, 窗口才真正可调。
        modules_config = [
            # (id, name, is_kill, loader, pkey, rkey, tkey, reverse, first_as_top)
            ("lstm",      "双层LSTM",       False, lambda: self.get_lstm_review(n).get("rows", []),           "target", "top10", "gold",          True,  False),
            ("spatial",   "空间重点点位",   False, lambda: self.get_spatial_points_review(n).get("rows", []), "period", "ten",   "core5",         True,  True),
            ("follow",    "跟班跟随",       False, lambda: self.get_follow_review(n).get("rows", []),         "period", "rep_picks", "rep_picks",   True,  True),
            ("suppression","未开点位反弹",  False, lambda: self.get_suppression_review(n).get("period_logs", []), "period", "top3_nums", "top1_num", True,  False),
            ("gemini",    "Gemini选2",      False, lambda: self.get_gemini_review(n).get("rows", []),         "period", "def5",   "gold",          True,  False),
            ("gold_pick2","定金选2",        False, lambda: self.get_gold_pick2_review(n).get("rows", []),     "period", "top1_pair", "top1_pair",   False, True),
            ("sixteen",   "16期中热",       False, lambda: self.get_sixteen_review(n).get("rows", []),        "period", "top5",   "gold",          False, False),
            ("jingle",    "顺口溜口诀",     False, lambda: self.get_jingle_review(n).get("pairs", []),    "target_issue", "recommended", "recommended", True, True),
        ]

        # B1/E4 整改 (2026-09-10): 退役模块不再上天梯榜。
        # 此前 LSTM / 空间点位 / 跟随 / Gemini 虽已退役, 仍作为"参赛者"排在榜上参与
        # BH-FDR 多重检验——既摊薄了校正预算, 又让界面看起来像"这些模块还在竞争"。
        # 判决唯一权威源是 module_gate 注册表, 此处直接派生。
        _lb_registry_ids = {
            "lstm": "lstm", "spatial": "spatial_points", "follow": "follow_track",
            "suppression": "point_suppression", "gemini": "gemini_pick2",
            "gold_pick2": "gold_pick2", "sixteen": "sixteen_hot", "jingle": "formula_jingle",
        }
        retired_excluded = []
        try:
            from backend.core.module_gate import ModuleGate
            _gate = ModuleGate(self.proj_dir)
            kept = []
            for cfg in modules_config:
                rid = _lb_registry_ids.get(cfg[0], cfg[0])
                if _gate.status_of(rid) == "retired":
                    retired_excluded.append({"id": cfg[0], "name": cfg[1], "registry_id": rid})
                    continue
                kept.append(cfg)
            modules_config = kept
        except Exception:
            # 注册表读不到就照旧全上, 但这属于"退化", 不能静默
            retired_excluded = [{"id": "?", "name": "注册表不可读, 未做退役过滤", "registry_id": "?"}]

        for (mid, name, is_kill, loader, pkey, rkey, tkey, reverse, first_as_top) in modules_config:
            try:
                raw = loader()
                rows = self._norm_wf_rows(raw, pkey, rkey, tkey, reverse, first_as_top)
            except Exception:
                continue
            series = []
            for row in rows:
                p = row["period"]
                actual = actual_map.get(p)
                if not actual:
                    continue
                metrics = compute_metrics(row["recommended"], actual, is_kill)
                if metrics is None:
                    continue
                top1 = row["top1"]
                top1_hit = None
                if top1 is not None and not is_kill:
                    top1_hit = bool(top1 in actual)
                series.append({
                    "period": p, **metrics,
                    "top1": top1, "top1_hit": top1_hit,
                    "recommended": list(dict.fromkeys(row["recommended"]))
                })
                period_set.add(p)
            if series:
                module_results.append({"id": mid, "name": name, "pick_type": "kill" if is_kill else "pick",
                                       "series": series[:n]})

        # ── 3. 汇总为统一结构（最新在前、按 period 对齐） ──
        periods_list = sorted(period_set, key=lambda p: int(p), reverse=True)[:n]
        latest_period = periods_list[0] if periods_list else None
        latest_actual = actual_map.get(latest_period, []) if latest_period else []

        out_modules = []
        for mr in module_results:
            series_map = {s["period"]: s for s in mr["series"]}
            aligned = []
            for p in periods_list:
                s = series_map.get(p)
                if s:
                    aligned.append(s)
                else:
                    aligned.append({"period": p, "size": None, "hit_count": None,
                                    "hit_rate": None, "lift": None, "top1": None,
                                    "top1_hit": None, "recommended": []})
            n_s = [s for s in aligned if s.get("hit_rate") is not None]
            avg_rate = round(sum(s["hit_rate"] for s in n_s) / len(n_s), 2) if n_s else 0
            avg_hits = round(sum(s["hit_count"] for s in n_s) / len(n_s), 2) if n_s else 0
            avg_lift = round(sum(s["lift"] for s in n_s) / len(n_s), 2) if n_s else 0
            latest = next((s for s in aligned if s.get("hit_rate") is not None), None)
            if latest is None:
                latest = {"period": latest_period, "size": 0, "hit_count": 0, "hit_rate": 0,
                          "lift": 0, "top1": None, "top1_hit": None, "recommended": []}
            out_modules.append({
                "id": mr["id"], "name": mr["name"], "pick_type": mr["pick_type"],
                "recommended_count": latest.get("size", 0),
                "latest": latest,
                "avg": {"hit_rate": avg_rate, "hit_count": avg_hits, "lift": avg_lift},
                "series": aligned
            })

        result = {
            "status": "ok",
            "n": n,
            "baseline_rate": baseline,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "latest_period": latest_period,
            "latest_actual": latest_actual,
            "periods": periods_list,
            "modules": out_modules,
            # B1/E4: 本榜单按 module_gate 注册表剔除了退役模块; 剔除名单必须回传,
            # 否则下游 (get_module_hit_eval) 只会看到"模块变少", 无法解释为什么。
            "retired_excluded": retired_excluded,
        }
        _hit_leaderboard_cache[cache_key] = result
        return result

    def get_module_hit_eval(self, n: int = 30, baseline: float = 0.25,
                            min_n: int = 30) -> Dict[str, Any]:
        """诚实的模块级样本外命中评估: 走 wf_hit_engine 统一做 CI + BH-FDR。

        复用 get_hit_leaderboard 已对齐的 per-period 命中数据 (size/hit_count),
        避免重复实现各 review 解析; 对每模块用 evaluate_from_counts 聚合,
        再跨模块做 BH-FDR 多重检验, 判断哪些模块真的显著优于随机基线。
        """
        try:
            from core.wf_hit_engine import evaluate_from_counts, fdr_summarize, render_report
        except Exception as e:  # pragma: no cover - 保障 offline 可用
            return {"status": "error", "detail": f"wf_hit_engine import failed: {e}"}

        try:
            leaderboard = self.get_hit_leaderboard(n=n)
        except Exception as e:
            return {"status": "error", "detail": f"get_hit_leaderboard failed: {e}"}

        evals: Dict[str, Any] = {}
        for m in leaderboard.get("modules", []):
            counts = []
            for s in m.get("series", []):
                if s.get("size") is None or s.get("hit_count") is None:
                    continue
                counts.append({"period": s["period"], "size": s["size"],
                               "hit_count": s["hit_count"]})
            if not counts:
                continue
            is_kill = m.get("pick_type") == "kill"
            # 杀号模块的公平基线: 随机杀 25 码期望杀对 (60/80)=0.75,
            # 若仍用 0.25 基线会把"随机也能做到"的杀对率虚报成 3.0x。
            bl = (1.0 - baseline) if is_kill else baseline
            evals[m["id"]] = evaluate_from_counts(counts, baseline=bl,
                                                  min_n=min_n, is_kill=is_kill)

        summary = fdr_summarize(evals)
        text = render_report(summary["results"], summary["winning"])
        return {
            "status": "ok",
            "n": n,
            "baseline_rate": baseline,
            "min_n": min_n,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modules": summary["results"],
            "winning": summary["winning"],
            "report_text": text,
            # B1/E4: 被排除的退役模块要明说, 不能静默少人
            # 由上游 get_hit_leaderboard 计算并随载荷回传, 此处透传 (原直接引用未定义变量导致接口 500)
            "retired_excluded": leaderboard.get("retired_excluded", []),
        }

    def get_module_consensus_overlay(self) -> Dict[str, Any]:
        """全模块「当期预测票」共识叠加数据 — 供开奖走势图预测行按模块上色。

        大白话: 把前瞻账里**目标期(未开奖)**那一行各模块真实录入的号码全部取出来，
        连同该模块的历史实测水位 (Lift/CI/p) 一起返回。前端据此在 80 码格子里
        为每个号码画出"是哪几路模块同时点了它"的彩色圆点。

        2026-10-22 新增。设计约束:
          1. 只读 storage/cache/paper_trading_modules.jsonl (收割器落盘的真实票)，
             不重算任何模型 —— 与看板/复盘严格同源，杜绝"界面号码与账本不一致"。
          2. 目标期 = 账本里 actual 为空 (未开奖) 的最大期号; 取不到则回退最新开奖+1。
          3. 退役模块 (注册表 status=retired) 一律剔除, 不混进现役共识。
          4. 水位取 module_ledger_report 同口径 (wf_hit_engine: lift/CI下界/p/BH-q)，
             样本不足要如实标 insufficient, 不得把小样本噪声画成"高水位模块"。
        """
        from backend.core.module_gate import (
            MODULE_LEDGER_FILE, ModuleGate, module_ledger_report,
        )

        try:
            gate = ModuleGate(self.proj_dir)
            retired = set(gate.retired_ids())
        except Exception:
            gate, retired = None, set()

        # ── 1. 读账本, 找出目标期 (未开奖的最大期) ──
        rows: List[Dict[str, Any]] = []
        if os.path.exists(MODULE_LEDGER_FILE):
            try:
                with open(MODULE_LEDGER_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            continue
            except Exception as e:
                logger.warning("共识叠加: 前瞻账读取失败: %s", e)

        pending = [r for r in rows if r.get("actual") is None and r.get("picks")]
        target_period: Optional[str] = None
        if pending:
            target_period = max((str(r["period"]) for r in pending), key=int)
        else:
            # 账本无未开奖票 → 回退到"最新开奖期 + 1"
            try:
                hist = self._build_actual_map()
                if hist:
                    target_period = str(int(max(hist.keys(), key=lambda p: int(p))) + 1)
            except Exception:
                target_period = None

        # ── 2. 目标期各模块票面 (剔除退役模块, 同模块取最新一条) ──
        picks_by_module: Dict[str, Dict[str, Any]] = {}
        for r in pending:
            if target_period and str(r.get("period")) != str(target_period):
                continue
            mid = str(r.get("module") or "")
            if not mid or mid in retired:
                continue
            try:
                nums = sorted({int(x) for x in (r.get("picks") or []) if 1 <= int(x) <= 80})
            except Exception:
                continue
            if not nums:
                continue
            prev = picks_by_module.get(mid)
            if prev is None or str(r.get("timestamp") or "") >= prev["timestamp"]:
                picks_by_module[mid] = {
                    "id": mid, "picks": nums,
                    "timestamp": str(r.get("timestamp") or ""),
                }

        # ── 3. 模块中文名 + 历史水位 (与看板同源) ──
        try:
            from backend.core.module_gate import MODULE_SEED
        except Exception:
            MODULE_SEED = {}
        try:
            ledger_rep = module_ledger_report().get("modules", {}) or {}
        except Exception:
            ledger_rep = {}

        # 展示色板: 高对比、互不重复的 20 色 (深色主题下均清晰可辨)
        palette = [
            "#f59e0b", "#10b981", "#38bdf8", "#a78bfa", "#f472b6",
            "#fb7185", "#34d399", "#fbbf24", "#60a5fa", "#c084fc",
            "#f97316", "#22d3ee", "#e879f9", "#a3e635", "#facc15",
            "#2dd4bf", "#818cf8", "#fb923c", "#4ade80", "#f43f5e",
        ]

        modules: List[Dict[str, Any]] = []
        for idx, (mid, info) in enumerate(sorted(picks_by_module.items())):
            ev = ledger_rep.get(mid) or {}
            name = (MODULE_SEED.get(mid) or {}).get("name") or (ev.get("name")) or mid
            lift = ev.get("lift")
            modules.append({
                "id": mid,
                "name": name,
                "picks": info["picks"],
                "color": palette[idx % len(palette)],
                # 水位: 样本不足时如实标注, 前端不得当作高置信信号渲染
                "lift": round(float(lift), 3) if isinstance(lift, (int, float)) else None,
                "lift_ci_lo": round(float(ev["lift_ci_lo"]), 3)
                    if isinstance(ev.get("lift_ci_lo"), (int, float)) else None,
                "p_value": round(float(ev["p_value"]), 4)
                    if isinstance(ev.get("p_value"), (int, float)) else None,
                "bh_q": round(float(ev["bh_q"]), 4)
                    if isinstance(ev.get("bh_q"), (int, float)) else None,
                "n_periods": int(ev.get("n_periods") or 0),
                "insufficient": bool(ev.get("insufficient", True)),
                "bh_significant": bool(ev.get("bh_significant", False)),
            })

        # 按水位降序: 强信号模块排在图例前面, 默认勾选也优先给它们
        modules.sort(key=lambda m: (-(m["lift"] or 0), m["id"]))

        # ── 4. 共识矩阵: 号码 -> 点了它的模块 id 列表 ──
        consensus: Dict[str, List[str]] = {}
        for m in modules:
            for n in m["picks"]:
                consensus.setdefault(str(n), []).append(m["id"])

        return {
            "status": "ok",
            "target_period": target_period,
            "module_count": len(modules),
            "modules": modules,
            "consensus": consensus,
            "excluded_retired": sorted(retired),
            "note": (
                "票面取自前瞻账当期录入 (与全模块看板同源); 水位为该模块历史前瞻账实测, "
                "样本不足或未过 BH-FDR 者仅供研究参考, 不构成加注依据。"
            ),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_all_modules_prediction_overview(self) -> Dict[str, Any]:
        """获取全模块最新一期预测汇总大盘 (含前一位+中心点位+后一位三联邻域)"""
        status = self.get_system_status()
        target_period = status.get("target_period", "2026232")
        latest_draw = status.get("latest_draw_period", "0")
        cache_key = (str(target_period), str(latest_draw))
        if cache_key in _all_modules_overview_cache:
            return _all_modules_overview_cache[cache_key]

        # ── 诚实命中评估 (CI + BH-FDR): 替换下方硬编码的 wf_lift/coverage 等展示字段 ──
        try:
            hit_eval = self.get_module_hit_eval(n=30)
            _he = hit_eval.get("modules", {})
        except Exception:
            hit_eval, _he = {}, {}

        def _lift_str(mid, fallback=None):
            """用 wf_hit_engine 的池化 Lift(+CI下界) 替代硬编码基准; 无数据则回退。"""
            ev = _he.get(mid) or {}
            if ev.get("total_picks", 0) <= 0:
                return fallback
            flag = "⭐显著" if ev.get("bh_significant") else ("样本不足" if ev.get("insufficient") else "贴基线")
            return f"{ev.get('lift', 1.0):.2f}x (CI下界 {ev.get('lift_ci_lo', 1.0):.2f}x, {flag})"

        overview = {
            "target_period": target_period,
            "latest_draw_period": status.get("latest_draw_period"),
            "latest_draw_numbers": status.get("latest_draw_numbers"),
            "modules": {}
        }
        
        # 1. Trinity & 主系统
        try:
            main_pred = self.get_latest_prediction()
            overview["modules"]["trinity"] = {
                "name": "三维融合与主系统核心",
                "top5": main_pred.get("top5_gold", []),
                "top12": main_pred.get("top12_pool", []),
                "hidden_energy5": main_pred.get("hidden_energy_5", []),
                "pure_pool": main_pred.get("pure_pool", []),
                "golden_pair": main_pred.get("golden_pair", []),
                "golden_pair_reason": main_pred.get("golden_pair_reason"),
                "weights": main_pred.get("weights"),
                "beacon_status": status.get("beacon_status", "正常")
            }
        except Exception:
            overview["modules"]["trinity"] = {"data_missing": True}

        # 2. 双层LSTM深度学习 —— B1/E4 整改 (2026-09-10): 已退役, 不再构造。
        # 此前这里会调 get_lstm_summary()(要加载 torch 模型) 拼出完整对象,
        # 几行后又在该函数末尾 pop 掉; 纯属白烧算力, 且中间产物可能被别的分支读走。

        # 3. 空间重点点位分析 (含最优点位：前一位 + 中心点位 + 后一位)
        try:
            sp_json = os.path.join(get_outputs_dir(), "spatial_points", "spatial_points_latest.json")
            if os.path.exists(sp_json):
                with open(sp_json, "r", encoding="utf-8") as f:
                    spd = json.load(f)
                picks = spd.get("picks", {})
                top10_details = picks.get("top10_details", [])
                
                # 构造前5最优点位及其【前一位 + 中心点位 + 后一位】结构
                top5_neighborhoods = []
                for item in top10_details[:5]:
                    center = item.get("point")
                    left = center - 1 if center > 1 else 80
                    right = center + 1 if center < 80 else 1
                    top5_neighborhoods.append({
                        "center": center,
                        "left": left,
                        "right": right,
                        "region": [left, center, right],
                        "score": item.get("score"),
                        "gap": item.get("features", {}).get("gap", 0),
                        "freq": item.get("features", {}).get("freq", 0),
                        "reg_heat": item.get("features", {}).get("reg_heat", 0)
                    })
                
                if not top5_neighborhoods:
                    order = picks.get("order", [])
                    for pt in order[:5]:
                        left = pt - 1 if pt > 1 else 80
                        right = pt + 1 if pt < 80 else 1
                        top5_neighborhoods.append({
                            "center": pt,
                            "left": left,
                            "right": right,
                            "region": [left, pt, right],
                            "score": None,
                            "gap": None,
                            "freq": None,
                            "reg_heat": None
                        })

                overview["modules"]["spatial_points"] = {
                    "name": "空间重点点位分析 (4维精排)",
                    "top5_neighborhoods": top5_neighborhoods,
                    "core5": picks.get("core5", [x["center"] for x in top5_neighborhoods]),
                    "ten_picks": picks.get("top10_points", picks.get("order", [])[:10]),
                    "top_regions": picks.get("top_regions", []),
                    "confidence": spd.get("confidence", {}).get("description"),
                    "wf_avg_hit": None,
                    "coverage": _lift_str("spatial")
                }
            else:
                sp = self.get_spatial_points_summary()
                picks = sp.get("picks", {})
                top10_details = picks.get("top10_details", [])
                top5_neighborhoods = []
                for item in top10_details[:5]:
                    center = item.get("point")
                    left = center - 1 if center > 1 else 80
                    right = center + 1 if center < 80 else 1
                    top5_neighborhoods.append({
                        "center": center,
                        "left": left,
                        "right": right,
                        "region": [left, center, right],
                        "score": item.get("score"),
                        "gap": item.get("features", {}).get("gap", 0),
                        "freq": item.get("features", {}).get("freq", 0),
                        "reg_heat": item.get("features", {}).get("reg_heat", 0)
                    })
                wf = sp.get("wf_summary", {})
                overview["modules"]["spatial_points"] = {
                    "name": "空间重点点位分析 (4维精排)",
                    "top5_neighborhoods": top5_neighborhoods,
                    "core5": picks.get("core5", [x["center"] for x in top5_neighborhoods]),
                    "ten_picks": picks.get("top10_points", picks.get("order", []))[:10],
                    "top_regions": picks.get("top_regions", [])[:3],
                    "confidence": sp.get("confidence", {}).get("description"),
                    "wf_avg_hit": f"{wf['avg_ten_hits']} / 10" if wf.get("avg_ten_hits") is not None else None,
                    "coverage": _lift_str("spatial")
                }
        except Exception:
            overview["modules"]["spatial_points"] = {"data_missing": True}

        # 4. 跟班跟随分析
        try:
            fl_json = os.path.join(get_outputs_dir(), "follow_analysis", "follow_latest.json")
            if os.path.exists(fl_json):
                with open(fl_json, "r", encoding="utf-8") as f:
                    fld = json.load(f)
                picks = fld.get("picks", {})
                overview["modules"]["follow"] = {
                    "name": "跟班跟随分析 (三路条件跟随)",
                    "repeat_top5": picks.get("repeat", {}).get("top5", []),
                    "follow_top6": picks.get("inference", {}).get("top6", []),
                    "conditions_top8": picks.get("conditional", {}).get("top8", []),
                    "resonance": picks.get("resonance_intersection", []),
                    "confidence": fld.get("confidence", {}).get("description"),
                    "rep_lift": _lift_str("follow"),
                    "inf_lift": _lift_str("follow")
                }
            else:
                fl = self.get_follow_summary()
                picks = fl.get("picks", {})
                overview["modules"]["follow"] = {
                    "name": "跟班跟随分析 (三路条件跟随)",
                    "repeat_top5": picks.get("repeat_top5", []),
                    "follow_top6": picks.get("follow_top6", []),
                    "conditions_top8": picks.get("conditions_top8", []),
                    "resonance": [],
                    "confidence": None,
                    "rep_lift": _lift_str("follow"),
                    "inf_lift": _lift_str("follow")
                }
        except Exception:
            overview["modules"]["follow"] = {"data_missing": True}

        # 5. 未开点位高压反弹 (含弹簧三连伴生区域)
        try:
            supp_json = os.path.join(get_outputs_dir(), "point_suppression", "suppression_latest.json")
            if os.path.exists(supp_json):
                with open(supp_json, "r", encoding="utf-8") as f:
                    suppd = json.load(f)
                cand_list = suppd.get("top3_candidates", [])
                rebound_cands = []
                for c in cand_list[:3]:
                    num = c.get("num")
                    if num is None:
                        continue
                    left = num - 1 if num > 1 else 80
                    right = num + 1 if num < 80 else 1
                    rebound_cands.append({
                        "num": num,
                        "left": left,
                        "right": right,
                        "region": [left, num, right],
                        "score": c.get("score"),
                        "k_suppression": c.get("k_suppression"),
                        "confidence": c.get("confidence")
                    })
                
                rebound_nums = [c["num"] for c in rebound_cands]
                overview["modules"]["suppression"] = {
                    "name": "未开点位高压反弹追踪",
                    "top_rebounds": rebound_nums,
                    "top3_candidates_detailed": rebound_cands,
                    "top1_details": suppd.get("top1"),
                    "spill_rate": _lift_str("suppression")
                }
            else:
                supp = self.get_suppression_summary()
                overview["modules"]["suppression"] = {
                    "name": "未开点位高压反弹追踪",
                    "top_rebounds": [],
                    "top3_candidates_detailed": [],
                    "top1_details": supp.get("top1", {}),
                    "spill_rate": _lift_str("suppression")
                }
        except Exception:
            overview["modules"]["suppression"] = {"data_missing": True}

        # 6. 定金选2
        try:
            gp_json = os.path.join(get_outputs_dir(), "gold_pick2", "gold_pick2_latest.json")
            if os.path.exists(gp_json):
                with open(gp_json, "r", encoding="utf-8") as f:
                    gpd = json.load(f)
                golden_pairs = [p.get("pair") for p in gpd.get("top5_golden", []) if p.get("pair")]
                pairs_detailed = gpd.get("top5_golden", [])[:3]
                overview["modules"]["gold_pick2"] = {
                    "name": "定金选2决策系统 (双重金胆)",
                    "golden": gpd.get("golden"),
                    "hot": gpd.get("hot"),
                    "top_pairs": golden_pairs[:3],
                    "top_pairs_detailed": pairs_detailed,
                    "confidence": gpd.get("confidence", {}).get("description"),
                    "hit_rate_pair": _lift_str("gold_pick2")
                }
            else:
                gp = self.get_gold_pick2_summary()
                overview["modules"]["gold_pick2"] = {
                    "name": "定金选2决策系统 (双重金胆)",
                    "golden": gp.get("golden"),
                    "hot": gp.get("hot"),
                    "top_pairs": gp.get("top_pairs", [])[:3],
                    "confidence": None,
                    "hit_rate_pair": _lift_str("gold_pick2")
                }
        except Exception:
            overview["modules"]["gold_pick2"] = {"data_missing": True}

        # 7. Gemini 选2
        try:
            gem = self.get_gemini_summary()
            gold = gem.get("gold")
            silver = gem.get("silver")
            bronze = gem.get("bronze")
            def5 = gem.get("def5", [])
            if not def5 and gold and silver and bronze:
                def5 = [gold, silver, bronze] + (gem.get("core4", [])[:2])
            overview["modules"]["gemini"] = {
                "name": "Gemini 选2 (5大物理算子协同)",
                "gold": gold,
                "silver": silver,
                "bronze": bronze,
                "core4": gem.get("core4", []),
                "final5": def5,
                "confidence": gem.get("confidence"),
                "lift": _lift_str("gemini"),
                "active_operators": "密度聚类 + 极值抑制 + 能量外溢"
            }
        except Exception:
            overview["modules"]["gemini"] = {"data_missing": True}

        # 8. 顺口溜口诀
        try:
            j_files = sorted(glob.glob(os.path.join(get_outputs_dir(), "jingle", "顺口溜预测_*.txt")) + glob.glob(os.path.join(get_outputs_dir(), "predictions", "顺口溜预测_*.txt")))
            rec_nums = []
            if j_files:
                with open(j_files[-1], "r", encoding="utf-8") as f:
                    txt = f.read()
                import re
                m = re.search(r"推荐码[^\n:]*:\s*([\d\s]+)", txt)
                if m:
                    rec_nums = [int(x) for x in m.group(1).split() if x.isdigit()]
            overview["modules"]["jingle"] = {
                "name": "民间顺口溜精英口诀规律",
                "recommended": rec_nums,
                "fired_count": len(rec_nums),
                "fired_samples": [],
                "wf_accuracy": _lift_str("jingle")
            }
        except Exception:
            overview["modules"]["jingle"] = {"data_missing": True}

        # 9. 16期频次跃迁与中热推演
        try:
            six = self.get_sixteen_summary()
            pairs_raw = six.get("top5_pairs", [])
            t_pairs = [p.get("pair", []) for p in pairs_raw if p.get("pair")]
            ta = six.get("transition_analysis", {})
            ladders = ta.get("ladders", {})
            gr_picks = ladders.get("ladder_gold_rush", {}).get("top_picks", [])
            
            status_desc = f"20码出窗待卸压 + {len(gr_picks)}码冲刺黄金4次甜区" if gr_picks else None
            overview["modules"]["sixteen"] = {
                "name": "16期频次跃迁与中热推演 (光谱稳健号)",
                "gold": six.get("gold_dan"),
                "silver": six.get("silver_dan"),
                "bronze": six.get("bronze_dan"),
                "defense5": six.get("medium_top5", []),
                "pool10": six.get("medium_top10", []),
                "top_pairs": t_pairs[:3],
                "dynamic_status": status_desc,
                "wf_lift": _lift_str("sixteen"),
                "transition_ladders": ladders
            }
        except Exception:
            overview["modules"]["sixteen"] = {"data_missing": True}

        # 10. 终审共识汇总
        try:
            agg_pattern = os.path.join(get_outputs_dir(), "aggregation", "aggregation_*.json")
            agg_files = sorted(glob.glob(agg_pattern))
            if agg_files:
                with open(agg_files[-1], "r", encoding="utf-8") as f:
                    aggd = json.load(f)
                overview["modules"]["aggregation"] = {
                    "name": "终审共识多维汇总 (7路多维共振 + 8区空间平衡)",
                    "meta_gold": aggd.get("meta_gold", {}),
                    "final_resonance": aggd.get("consensus_dan_pool", []),
                    "balanced_8zones": aggd.get("stable_top10", []),
                    "subsystems_count": aggd.get("subsystems_count"),
                    "vote_leaders": []
                }
            else:
                agg = self.get_aggregation_cockpit()
                overview["modules"]["aggregation"] = {
                    "name": "终审共识多维汇总 (7路多维共振 + 8区空间平衡)",
                    "meta_gold": agg.get("meta_gold", {}),
                    "final_resonance": [],
                    "balanced_8zones": [],
                    "subsystems_count": None,
                    "vote_leaders": []
                }
        except Exception:
            overview["modules"]["aggregation"] = {"data_missing": True}

        # 12. 数据源1×数据源2 深层关联与极高命中研判
        try:
            da_pattern = os.path.join(get_outputs_dir(), "deep_association", "深层关联预测_*.txt")
            da_files = sorted(glob.glob(da_pattern))
            if da_files:
                with open(da_files[-1], "r", encoding="utf-8") as f:
                    da_txt = f.read()
                hot_m = re.search(r"\[精选爆发(?:最优3码| Top 5)\]:\s*([0-9, ]+)", da_txt)
                cons_m = re.search(r"\[跨规则共识金胆\]:\s*([0-9, ]+)", da_txt)
                pair_m = re.search(r"\[黄金连体婴选2\]:\s*\[(\d{2})-(\d{2})\]", da_txt)

                hot_picks = [int(x) for x in re.findall(r"\d{2}", hot_m.group(1))] if hot_m else []
                cons_picks = [int(x) for x in re.findall(r"\d{2}", cons_m.group(1))] if (cons_m and "无" not in cons_m.group(1)) else []
                pair_picks = [int(pair_m.group(1)), int(pair_m.group(2))] if pair_m else []

                overview["modules"]["deep_association"] = {
                    "name": "数据源1×数据源2 深层关联预测",
                    "top_hot_numbers": hot_picks[:3],
                    "top3_gold": hot_picks[:3],
                    "consensus_numbers": cons_picks,
                    "gold_pair": pair_picks,
                    "confidence": None,
                    "wf_accuracy": _lift_str("deep_association")
                }
            else:
                overview["modules"]["deep_association"] = {"data_missing": True}
        except Exception:
            overview["modules"]["deep_association"] = {"data_missing": True}

        # 已退役子系统不再出现在 modules 里 —— 但"它们去哪了"必须给界面一个交代。
        # E3 整改 (2026-09-10): 此前是静默 pop, 前端只看到"少了几个人",
        # 分不清是"退役了"还是"跑挂了"。现在把判决理由一并带出去。
        _retired_ids = ["lstm", "spatial_points", "follow_track", "gemini_pick2", "pure_pool"]
        retired_modules = []
        try:
            from backend.core.module_gate import ModuleGate
            _rg = ModuleGate(self.proj_dir)
            for _rid in _retired_ids:
                _m = _rg.get(_rid) or {}
                retired_modules.append({
                    "id": _rid,
                    "name": _m.get("name", _rid),
                    "retired_since": (_m.get("decree") or {}).get("date"),
                    "reason": (_m.get("decree") or {}).get("reason") or _m.get("auto_note") or "",
                })
        except Exception:
            retired_modules = [{"id": "?", "name": "注册表不可读", "retired_since": None,
                                "reason": "无法读取 module_gate 注册表, 退役清单不可用"}]
        overview["retired_modules"] = retired_modules

        for disc in ("lstm", "spatial_points", "follow", "gemini"):
            overview["modules"].pop(disc, None)
        if "trinity" in overview.get("modules", {}) and "pure_pool" in overview["modules"]["trinity"]:
            overview["modules"]["trinity"]["pure_pool"] = []

        _all_modules_overview_cache[cache_key] = overview
        return overview

    def get_meta_gold_summary(self) -> Dict[str, Any]:
        """获取 Meta-Gold 至尊金胆超级共识熔炉数据
        （各引擎投票权重为手工经验值，未经样本外审计——2026-09-10 数据诚信整改）"""
        out_dir = os.path.join(get_outputs_dir(), "aggregation")
        if os.path.exists(out_dir):
            agg_files = sorted(glob.glob(os.path.join(out_dir, "aggregation_*.json")), reverse=True)
            if agg_files:
                try:
                    with open(agg_files[0], "r", encoding="utf-8") as jf:
                        d = json.load(jf)
                    mg = d.get("meta_gold", {})
                    if mg:
                        return {"status": "ok", "target_period": d.get("target_period", "2026234"), "data": mg}
                except Exception:
                    pass

        try:
            from backend.core.aggregation.consensus_engine import ConsensusEngine
            engine = ConsensusEngine(self.proj_dir)
            agg = engine.run_aggregation(n_review=30)
            return {"status": "ok", "target_period": agg.get("target_period", "2026234"), "data": agg.get("meta_gold", {})}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_meta_gold_review(self, n: int = 30) -> Dict[str, Any]:
        """获取 Meta-Gold 至尊金胆近 N 期样本外实测逐期命中复盘对账总账"""
        try:
            history = self.load_history(limit=0)
            hist_map = {int(d["period"]): set(d["numbers"]) for d in history}
            sorted_all_periods = sorted(hist_map.keys(), reverse=True)
            target_periods = sorted_all_periods[:n]

            learner_file = os.path.join(get_cache_dir(), "self_learning_state.json")
            learner_history = []
            if os.path.exists(learner_file):
                try:
                    with open(learner_file, "r", encoding="utf-8") as f:
                        learner_history = json.load(f).get("history", [])
                except Exception:
                    pass

            rec_map = {}
            for r in learner_history:
                iss = int(r.get("target_issue", 0))
                if iss in hist_map:
                    rec_map[iss] = r

            rows = []
            tot_supreme_hits = 0
            tot_t5_hits = 0
            tot_t5_picks = 0
            missing_periods = []

            for period in target_periods:
                actual = hist_map.get(period, set())
                rec = rec_map.get(period)
                if rec:
                    t5 = rec.get("top5", [])
                    he5 = rec.get("b3_final5", [])
                    deep = rec.get("deep_picks", [])
                else:
                    # 历史回退现场解算
                    idx = next((i for i, d in enumerate(history) if int(d["period"]) == period), None)
                    sub_hist = history[idx + 1:] if idx is not None else history
                    live = self._compute_live_prediction(sub_hist, n=30)
                    t5 = live.get("top5_gold", [])
                    he5 = live.get("hidden_energy_5", [])
                    deep = live.get("top12_pool", [])[:5]

                combined_scores = {}
                for idx_b, num in enumerate(t5):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.0
                for idx_b, num in enumerate(he5):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.2
                for idx_b, num in enumerate(deep[:5]):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.3

                sorted_mg = sorted(combined_scores.keys(), key=lambda x: -combined_scores[x])

                # 2026-09-10 数据诚信整改：上游三路池全空时不再编造 [1,2,3,4,5] 兜底号码。
                # 原实现会拿这组假号码去和真实开奖对账，进而产出虚假命中率/Lift 与"显著超额"结论，
                # 现改为显式 data_missing 行，且不纳入汇总分母。
                if not sorted_mg:
                    missing_periods.append(period)
                    rows.append({
                        "period": period,
                        "actual_numbers": sorted(list(actual)),
                        "supreme_gold": None,
                        "supreme_hit": False,
                        "meta_top5": [],
                        "hit_balls": [],
                        "hit_count": 0,
                        "total_picks": 0,
                        "hit_rate": None,
                        "lift": None,
                        "data_missing": True,
                        "verdict": "⚠️ 数据缺失（未纳入对账）"
                    })
                    continue

                meta_top5 = sorted_mg[:5]
                supreme = meta_top5[0]

                hit_supreme = supreme in actual
                hit_t5 = [num for num in meta_top5 if num in actual]
                hit_count = len(hit_t5)

                if hit_supreme:
                    tot_supreme_hits += 1
                tot_t5_hits += hit_count
                tot_t5_picks += len(meta_top5)

                lift = (hit_count / len(meta_top5)) / 0.25

                rows.append({
                    "period": period,
                    "actual_numbers": sorted(list(actual)),
                    "supreme_gold": supreme,
                    "supreme_hit": hit_supreme,
                    "meta_top5": meta_top5,
                    "hit_balls": hit_t5,
                    "hit_count": hit_count,
                    "total_picks": len(meta_top5),
                    "hit_rate": round(hit_count / len(meta_top5), 3),
                    "lift": round(lift, 2),
                    "data_missing": False,
                    # 单期 5 码期望命中 1.25 码，高于/低于期望不能称为"显著"（无统计检验，n=1）
                    "verdict": "🟢 高于单期期望" if hit_count >= 2 else "🔴 低于单期期望"
                })

            n_rows = len(rows)
            n_eval = n_rows - len(missing_periods)   # 仅统计有前瞻产出的期数，缺失期不摊薄分母
            avg_t5_hits = round(tot_t5_hits / n_eval, 2) if n_eval else None
            t5_win_rate = round(tot_t5_hits / tot_t5_picks, 3) if tot_t5_picks else None
            overall_lift = round(t5_win_rate / 0.25, 2) if t5_win_rate is not None else None
            supreme_rate = round(tot_supreme_hits / n_eval, 3) if n_eval else None

            return {
                "status": "ok",
                "n_periods": n_rows,
                "summary": {
                    "supreme_hits": tot_supreme_hits,
                    "supreme_hit_rate": supreme_rate,
                    "supreme_lift": round(supreme_rate / 0.25, 2) if supreme_rate is not None else None,
                    "avg_top5_hits": avg_t5_hits,
                    "top5_win_rate": t5_win_rate,
                    "overall_lift": overall_lift,
                    "total_periods": n_eval,
                    "missing_periods": missing_periods,
                    "significance_note": "逐期为对账展示，不构成显著性证据；30 期样本不足以判定超额（基线 25%）"
                },
                "rows": rows
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": [], "summary": {}}

    def get_funnel_pipeline_summary(self) -> Dict[str, Any]:
        """获取三级漏斗全链路清洗流水线 (25码海选 ➔ 18码纯净池 ➔ 5码精选 ➔ 2码黄金配对)"""
        status = self.get_system_status()
        target_p = status.get("target_period", "2026234")
        
        # 聚合各层产物
        # 2026-09-10 数据诚信整改：上游缺数据时不再硬编码兜底号码，
        # 改为空池 + missing_sources 显式声明，由前端展示"数据缺失"。
        main_pred = self.get_latest_prediction()
        ds = self.get_datasource_summary().get("data", {})
        mg = self.get_meta_gold_summary().get("data", {})

        top12_pool = main_pred.get("top12_pool") or []
        ds_hot = ds.get("top_hot_numbers") or []
        mg_top5 = mg.get("meta_gold_top5") or []
        he5 = main_pred.get("hidden_energy_5") or []

        missing_sources = []
        if not top12_pool: missing_sources.append("三维融合Top12")
        if not ds_hot: missing_sources.append("数据源热码Top5")
        if not mg_top5: missing_sources.append("Meta-Gold金胆Top5")
        if not he5: missing_sources.append("Hidden Energy 5")

        level1_candidates = list(dict.fromkeys(top12_pool + ds_hot + mg_top5 + he5))[:25]
        level2_pure_pool = level1_candidates[:18]

        supreme_gold = mg.get("supreme_gold")  # 可能为 None，表示无数据
        pair = main_pred.get("golden_pair") or []
        top5 = mg_top5
        if supreme_gold is None: missing_sources.append("至尊金胆")
        if not pair: missing_sources.append("黄金选2搭档")

        return {
            "status": "ok",
            "target_period": target_p,
            "level1_wide_pool": {
                "name": "Level 1: 大盘海选宽门池",
                "count": len(level1_candidates),
                "numbers": level1_candidates,
                "desc": "汇聚三维融合、深层关联做多、Meta-Gold与隐能量场的多路做多宽门阵列"
            },
            "level2_pure_pool": {
                "name": "Level 2: 共识提纯底仓",
                "count": len(level2_pure_pool),
                "numbers": level2_pure_pool,
                "kills_filtered": [],
                "desc": "经票权引擎加权共识提纯后的做多底仓（杀号过滤已退役）"
            },
            "level3_supreme": {
                "name": "Level 3: 至尊金胆与极简选2终极配对",
                "supreme_gold": supreme_gold,
                "meta_top5": top5,
                "golden_pair": pair,
                "desc": "由 Meta-Gold 投票与主脑配对产出；各引擎投票权重为经验值，未经样本外审计（整改清单 A2/C1）"
            },
            "data_integrity": {
                "missing_sources": missing_sources,
                "note": "上游缺数据时展示为空，不再用硬编码号码冒充（2026-09-10 数据诚信整改）"
            }
        }

    def get_funnel_pipeline_review(self, n: int = 30) -> Dict[str, Any]:
        """获取三级漏斗全链路近 N 期样本外实测逐期对账台账"""
        try:
            history = self.load_history(limit=0)
            hist_map = {int(d["period"]): set(d["numbers"]) for d in history}
            sorted_all_periods = sorted(hist_map.keys(), reverse=True)
            target_periods = sorted_all_periods[:n]

            learner_file = os.path.join(get_cache_dir(), "self_learning_state.json")
            learner_history = []
            if os.path.exists(learner_file):
                try:
                    with open(learner_file, "r", encoding="utf-8") as f:
                        learner_history = json.load(f).get("history", [])
                except Exception:
                    pass

            rec_map = {}
            for r in learner_history:
                iss = int(r.get("target_issue", 0))
                if iss in hist_map:
                    rec_map[iss] = r

            rows = []
            tot_l1_hits = 0
            tot_l1_picks = 0
            tot_l2_hits = 0
            tot_l2_picks = 0
            tot_l3_hits = 0
            tot_l3_picks = 0
            pair_both_count = 0

            for period in target_periods:
                actual = hist_map.get(period, set())
                rec = rec_map.get(period)
                if rec:
                    t12 = rec.get("top12", [])
                    he5 = rec.get("b3_final5", [])
                    deep = rec.get("deep_picks", [])
                    pure = rec.get("pure_pool_top", [])
                else:
                    idx = next((i for i, d in enumerate(history) if int(d["period"]) == period), None)
                    sub_hist = history[idx + 1:] if idx is not None else history
                    live = self._compute_live_prediction(sub_hist, n=30)
                    t12 = live.get("top12_pool", [])
                    he5 = live.get("hidden_energy_5", [])
                    deep = live.get("top5_gold", [])
                    pure = live.get("pure_pool", [])

                l1_pool = list(dict.fromkeys(t12 + he5 + deep))[:25]
                if len(l1_pool) < 15:
                    l1_pool = list(dict.fromkeys(t12 + he5 + pure))[:25]

                l2_pool = l1_pool[:18]

                combined_scores = {}
                for idx_b, num in enumerate(t12[:5]):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.0
                for idx_b, num in enumerate(he5):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.2
                for idx_b, num in enumerate(deep[:5]):
                    combined_scores[num] = combined_scores.get(num, 0) + (5 - idx_b) * 1.3
                sorted_mg = sorted(combined_scores.keys(), key=lambda x: -combined_scores[x])
                l3_top5 = sorted_mg[:5] if len(sorted_mg) >= 5 else l1_pool[:5]

                gold_pair = l3_top5[:2] if len(l3_top5) >= 2 else []

                l1_hits = [num for num in l1_pool if num in actual]
                l2_hits = [num for num in l2_pool if num in actual]
                l3_hits = [num for num in l3_top5 if num in actual]
                pair_hits = [num for num in gold_pair if num in actual]

                if len(pair_hits) == 2:
                    pair_both_count += 1

                tot_l1_hits += len(l1_hits)
                tot_l1_picks += len(l1_pool)
                tot_l2_hits += len(l2_hits)
                tot_l2_picks += len(l2_pool)
                tot_l3_hits += len(l3_hits)
                tot_l3_picks += len(l3_top5)

                l3_lift = (len(l3_hits) / len(l3_top5)) / 0.25 if l3_top5 else 1.0

                rows.append({
                    "period": period,
                    "actual_numbers": sorted(list(actual)),
                    "level1_pool": l1_pool,
                    "level1_hits": l1_hits,
                    "level1_hit_count": len(l1_hits),
                    "level1_total": len(l1_pool),
                    "level2_pool": l2_pool,
                    "level2_hits": l2_hits,
                    "level2_hit_count": len(l2_hits),
                    "level2_total": len(l2_pool),
                    "level3_top5": l3_top5,
                    "level3_hits": l3_hits,
                    "level3_hit_count": len(l3_hits),
                    "golden_pair": gold_pair,
                    "pair_hits": len(pair_hits),
                    "pair_both": len(pair_hits) == 2,
                    "l3_lift": round(l3_lift, 2),
                    "verdict": "⭐ 3级全打通" if (len(l3_hits) >= 2 or len(pair_hits) == 2) else ("🟢 稳健过滤" if len(l2_hits) >= 5 else "🟡 常规防守")
                })

            n_rows = len(rows)
            avg_l1 = round(tot_l1_hits / n_rows, 2) if n_rows else 0
            avg_l2 = round(tot_l2_hits / n_rows, 2) if n_rows else 0
            avg_l3 = round(tot_l3_hits / n_rows, 2) if n_rows else 0
            l3_win_rate = round(tot_l3_hits / tot_l3_picks, 3) if tot_l3_picks else 0
            l3_lift = round(l3_win_rate / 0.25, 2) if l3_win_rate else 1.0
            pair_both_rate = round(pair_both_count / n_rows, 3) if n_rows else 0

            return {
                "status": "ok",
                "n_periods": n_rows,
                "summary": {
                    "avg_l1_hits": avg_l1,
                    "l1_hit_rate": round(tot_l1_hits / tot_l1_picks, 3) if tot_l1_picks else 0,
                    "avg_l2_hits": avg_l2,
                    "l2_hit_rate": round(tot_l2_hits / tot_l2_picks, 3) if tot_l2_picks else 0,
                    "avg_l3_hits": avg_l3,
                    "l3_win_rate": l3_win_rate,
                    "l3_lift": l3_lift,
                    "pair_both_count": pair_both_count,
                    "pair_both_rate": pair_both_rate,
                    "total_periods": n_rows
                },
                "rows": rows
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "rows": [], "summary": {}}

    def get_environment_regime_summary(self) -> Dict[str, Any]:
        """获取宏观大环境与变盘监控雷达数据 (5类市场态势识别与 KL 散度漂移)"""
        try:
            from backend.recognition.simplified_env_recognition import recognize_environment, ENVIRONMENT_CLASSES
            history_draws = self._build_draw_items()
            hist_formatted = [{"period": d["period"], "numbers": d["numbers"]} for d in history_draws[-30:]]
            hist_formatted.reverse() # 最新在前
            
            env_class, env_name, conf, strat = recognize_environment(hist_formatted)
            env_meta = ENVIRONMENT_CLASSES.get(env_class, {})
            
            # 计算大盘温度计 (0~100) 与变盘风险
            temp_score = min(100, max(0, int(conf * 100)))
            drift_risk = "🟢 极低 (规律平稳)" if conf > 0.6 else ("🟡 中等 (常规震荡)" if conf > 0.4 else "🔴 偏高 (注意防守)")

            return {
                "status": "ok",
                "environment_class": env_class,
                "environment_name": env_name,
                "confidence": round(conf, 3),
                "temperature_score": temp_score,
                "drift_risk": drift_risk,
                "description": strat.get("description", env_meta.get("desc", "大盘平稳")),
                "recommended_weights": strat.get("weights", {"EF": 0.40, "RW": 0.30, "FO": 0.30}),
                "weights_source": "静态默认值，非自学习产出（自学习门控当前处于冻结状态）",
                "predictive_power_note": "开奖序列 lag-1 自相关≈0（纯随机），环境分类仅作形态描述，不构成预测力证据",
                "is_fallback": False,
                "strategy_advice": "当前处于进攻态，建议重仓至尊金胆与黄金选2" if env_class == 0 else "当前处于震荡防守态，建议以纯净池防守做空排雷为主"
            }
        except Exception as e:
            return {
                "status": "ok",
                "environment_class": None,
                "environment_name": None,
                "confidence": None,
                "temperature_score": None,
                "drift_risk": None,
                "description": None,
                "recommended_weights": None,
                "weights_source": "静态默认值（异常回退），非自学习产出",
                "predictive_power_note": "开奖序列 lag-1 自相关≈0（纯随机），环境分类仅作形态描述，不构成预测力证据",
                "is_fallback": True,
                "data_missing": True,
                "strategy_advice": None
            }

    def get_fdr_audit_summary(self, n: int = 100) -> Dict[str, Any]:
        """获取严谨统计信标与 FDR-BH 多重检验显著性审计总表 (C3: 默认窗口 100 期, 30 期样本太小易被赢家诅咒误导)"""
        return self.get_module_hit_eval(n=n)

    def get_paper_trading_summary(self, rolling: int = 30) -> Dict[str, Any]:
        """获取样本外前瞻台账 + 选2 盈亏平衡对照。

        2026-09-10 整改: 本方法此前会返回一条"模拟盘实战资金净值曲线", 其每期盈亏由
            ret_rate = (hits / 20.0 - 0.25) * 4.0 ;  profit = 200.0 * ret_rate
        这个线性公式臆造而来。它不对应任何真实玩法:
          · 快乐8 选2 是 2 元/注、两码全中派 19 元, 随机成对概率 C(20,2)/C(80,2)=6.01%,
            盈亏平衡需要 Lift >= 1.75x —— 与"命中率是否超过 25%"毫无关系;
          · 且账本只记 Top20 号码的命中数与 Lift, 从未记录实际下注的选2组合。
        于是该曲线会在 lift≈1.04 时显示"盈利", 而真实选2 每注亏约 43%。已移除。
        现改为如实展示账本实测指标 + 选2 盈亏平衡门槛对照, 不提供任何金额。
        """
        try:
            from backend.learning.paper_trading import report_oos, _load_ledger
            oos = report_oos(rolling=rolling)
            rows = _load_ledger()

            # 逐期对账: 只放账本里真实存在的量, 不派生金额
            curve = []
            for r in rows[-30:]:
                top_k = r.get("top_k", 20) or 20
                curve.append({
                    "period": r.get("period"),
                    "hits": r.get("hits", 0),
                    "top_k": top_k,
                    "baseline_expected_hits": r.get(
                        "baseline_expected_hits", round(0.25 * top_k, 2)),
                    "lift": r.get("lift", 1.0),
                    "start_date": r.get("timestamp", "")[:10] or None,
                })

            # C5: 全员独立前瞻账 —— 每个模块一本账 (module_gate 维护, 同 wf_hit_engine 口径)
            by_module = {}
            try:
                from backend.core.module_gate import module_ledger_report
                by_module = module_ledger_report().get("modules", {})
            except Exception:
                pass

            return {
                "status": "ok",
                "summary": oos,
                "curve": curve,
                # 选2 盈亏平衡门槛 (真实玩法口径)
                "breakeven_lift": 1.75,
                "breakeven_note": (
                    "快乐8 选2: 2 元/注, 两码全中派彩 19 元。随机成对概率 "
                    "C(20,2)/C(80,2) = 190/3160 = 6.01%, 故盈亏平衡需要 Lift >= 1.75x。"
                ),
                "can_settle_cash": False,
                "can_settle_cash_reason": (
                    "本台账只记录 Top20 号码的命中数与 Lift, 未记录实际下注的选2组合, "
                    "因此无法结算真实盈亏。此前页面上的资金净值曲线为臆造公式所致, 已移除。"
                ),
                "total_records": len(rows),
                "by_module": by_module,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_module_gate_registry(self) -> Dict[str, Any]:
        """获取模块投票注册表 (唯一权重权威源): 谁有票权、谁进观察仓、谁已退役。"""
        try:
            from backend.core.module_gate import ModuleGate
            gate = ModuleGate(self.proj_dir)
            return {"status": "ok", "registry": gate.registry(),
                    "retired": gate.retired_ids(), "observation": gate.observation_ids()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_data_freshness(self) -> Dict[str, Any]:
        """E5: 数据新鲜度探针 —— 扫描关键产出, 报"最新期号/落后几期/状态"。

        大白话: 看板再也不能拿"停更数据"装新鲜。每个关键产出都报清楚它最新到哪一期、
        比最新开奖落后几期; 落后的标 stale, 期号超前的标 anomaly, 人为退役的标 retired。
        """
        from backend.utils.history_loader import load_history
        try:
            hist = load_history(limit=1)
            latest_issue = int(hist[0].get("issue") or hist[0].get("period")) if hist else None
        except Exception:
            latest_issue = None

        pat = re.compile(r"(20\d{5})")   # 期号形如 2026243 (20 + 5位)
        items, bogus_files = [], []

        for key, label, reldir, prefix, suffix in self._FRESHNESS_DIRS:
            # v5.4: outputs/... 已迁到 storage/outputs/...
            candidates = [
                os.path.join(get_storage_dir(), reldir.replace("\\", "/")),
                os.path.join(self.proj_dir, "storage", reldir),
                os.path.join(self.proj_dir, reldir),
            ]
            d = next((c for c in candidates if os.path.isdir(c)), candidates[0])
            best_p, best_f = None, None
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    if not (fn.startswith(prefix) and fn.endswith(suffix)):
                        continue
                    mm = pat.search(fn)
                    if not mm:
                        continue
                    pv = int(mm.group(1))
                    # 期号比最新开奖超前 2 期以上 → 手滑打错的文件名, 不算"最新产物"
                    if latest_issue is not None and pv > latest_issue + 2:
                        bogus_files.append(f"{reldir}/{fn}")
                        continue
                    if best_p is None or pv > best_p:
                        best_p, best_f = pv, os.path.join(d, fn)
            if best_p is None:
                state, lag = "missing", None
            elif latest_issue is None:
                state, lag = "unknown", None
            else:
                # lag = 最新开奖期号 - 产出的期号。
                # 0/−1 都是健康态: 0 = 已为本期开奖落了稿; −1 = 已为下一期备好稿 (常态)
                lag = latest_issue - best_p
                if lag > 1:
                    state = "stale"
                elif lag < -1:
                    state = "anomaly"
                else:
                    state = "fresh"
            items.append({
                "key": key, "label": label, "latest_period": best_p, "lag": lag, "state": state,
                "mtime": (datetime.fromtimestamp(os.path.getmtime(best_f)).strftime("%Y-%m-%d %H:%M:%S")
                          if best_f else None),
            })

        for key, label, rel in self._FRESHNESS_FILES:
            rel_norm = rel.replace("\\", "/")
            if rel_norm.startswith("storage/"):
                p = os.path.join(self.proj_dir, rel_norm)
            elif rel_norm.startswith("cache/") or rel_norm.startswith("outputs/") or rel_norm.startswith("reports/"):
                p = data_path(*rel_norm.split("/"))
            else:
                p = data_path(rel_norm)
            exists = os.path.exists(p)
            if not exists:
                state, lag, pv = "missing", None, None
            else:
                pv = self._peek_period(p)
                if pv is None or latest_issue is None:
                    state, lag = "fresh", None
                else:
                    lag = latest_issue - pv
                    state = "stale" if lag > 1 else ("anomaly" if lag < -1 else "fresh")
            items.append({
                "key": key, "label": label, "latest_period": pv, "lag": lag, "state": state,
                "mtime": (datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
                          if exists else None),
            })

        # E3: 人为退役的产出 (停更是判决, 不是故障)
        # 判决唯一权威源是 module_gate 注册表，此处直接派生，不再硬编码清单
        # (硬编码曾漏掉 spatial_points/datasource_1x2_hot/pure_pool，页面看不出停更)
        retired = []
        try:
            from backend.core.module_gate import ModuleGate
            _mods = (ModuleGate(self.proj_dir).registry() or {}).get("modules", {}) or {}
            for _mid, _m in _mods.items():
                if (_m or {}).get("status") != "retired":
                    continue
                _d = _m.get("decree") or {}
                _reason = _d.get("reason") or _m.get("evidence_source") or "已退役"
                _date = _d.get("date") or ""
                retired.append({
                    "key": _mid,
                    "label": _m.get("name") or _mid,
                    "note": f"已退役 {_date} ({_reason})" if _date else f"已退役 ({_reason})",
                })
        except Exception as _e:
            logger.warning(f"读取退役模块注册表失败, retired_outputs 置空: {_e}")

        bad = [i["key"] for i in items if i["state"] in ("stale", "anomaly", "missing")]
        parts = []
        if bad:
            parts.append(f"⚠️ {len(bad)} 项需关注: {', '.join(bad)}")
        if bogus_files:
            parts.append(f"{len(bogus_files)} 个文件名期号异常")
        return {
            "status": "ok",
            "latest_draw_period": latest_issue,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": items,
            "retired_outputs": retired,
            "bogus_files": bogus_files,
            "bad_count": len(bad), "bad": bad,
            "verdict": ("全部新鲜" if not parts else " / ".join(parts)),
        }

    @staticmethod
    def _peek_period(path: str):
        """从账本/状态文件里顺手掏一个"最新期号", 掏不到就返回 None (不猜)。

        注意: 各账本有的正序追加 (老→新), 有的倒序 (新→老), 所以两端各取几个
        候选再取最大值, 不假设排序方向。
        """
        if not os.path.exists(path) or not (path.endswith(".json") or path.endswith(".jsonl")):
            return None
        try:
            if path.endswith(".jsonl"):
                last_lines = []
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            last_lines.append(line)
                            if len(last_lines) > 3:
                                last_lines.pop(0)
                data = [json.loads(x) for x in last_lines]
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            return None

        PERIOD_KEYS = ("target_period", "last_period", "latest_period",
                       "target_issue", "period", "issue")

        def _from_dict(d):
            if not isinstance(d, dict):
                return None
            for k in PERIOD_KEYS:
                mm = re.search(r"(20\d{5})", str(d.get(k, "")))
                if mm:
                    return int(mm.group(1))
            return None

        def _dig(obj, depth=0):
            got = _from_dict(obj)
            if got or depth > 2:
                return got
            if isinstance(obj, list):
                seqs = [obj]
            elif isinstance(obj, dict):
                seqs = [v for v in obj.values() if isinstance(v, list) and v]
            else:
                return None
            best = None
            for seq in seqs:
                sample = seq[:3] + seq[-3:] if len(seq) > 3 else seq
                for ent in sample:
                    got = _dig(ent, depth + 1)
                    if got and (best is None or got > best):
                        best = got
            return best

        return _dig(data)

    @staticmethod
    def _observation_tag(module_id: str) -> Dict[str, Any]:
        """B3: 给「观察仓·未验证」模块的 API 响应贴状态牌。

        大白话: 质合/心理博弈这类模块本就不在共识票池里, 但接口以前对此只字不提,
        看板把它们当正常预测展示。现在响应里明说: 它没有投票权, 结论仅供参考。
        """
        from core.module_gate import MIN_PROSPECTIVE_PERIODS
        m = {}
        try:
            from core.module_gate import ModuleGate
            m = ModuleGate().get(module_id) or {}
        except Exception:
            pass
        status = m.get("status", "observation")
        weight = m.get("vote_weight", 0.0) or 0.0
        prereg = bool(m.get("preregistered"))
        warning = "⚠️ 观察仓·未验证: 本模块不参与共识投票, 结论仅供参考, 尚未通过样本外显著性检验。"
        if prereg:
            warning += (f" 门禁进度: 前瞻账 {m.get('prospective_periods', 0)}/"
                        f"{MIN_PROSPECTIVE_PERIODS} 期, 满期且过 BH-FDR 后才可能取得投票权。")
        return {
            "module_id": module_id,
            "module_status": status,
            "vote_weight": weight,
            "votable": bool(status == "votable" and weight > 0),
            "preregistered": prereg,
            "prospective_periods": m.get("prospective_periods", 0),
            "warning": warning,
        }

    def get_prime_composite_analysis(self, force_refresh: bool = False) -> Dict[str, Any]:
        """B3 包装层: 原逻辑不动, 只往响应里注入观察仓状态牌。"""
        res = self._get_prime_composite_analysis_raw(force_refresh=force_refresh)
        if isinstance(res, dict) and res.get("status") == "ok":
            res["module_gate"] = self._observation_tag("prime_composite")
        return res

    def _get_prime_composite_analysis_raw(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取质数合数与尾数香农熵综合量化推演数据 (方案二、三、四三合一)

        @param force_refresh 是否强制重新计算落盘
        @return 包含尾数香农熵、22质数小池塘考勤榜、8对孪生质数雷达的字典
        """
        json_path = os.path.join(self.proj_dir, "storage", "stats", "prime_tail_entropy_analysis.json")
        if not force_refresh and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)

                # 步骤 1: 校验缓存期号是否与全量历史最新开奖对齐 (防止跨天出现陈旧缓存)
                from backend.utils.history_loader import load_history
                hist = load_history()
                latest_issue = str(hist[0].get("issue") or hist[0].get("period") or "") if hist else ""
                if cached_data.get("based_on_period") == latest_issue and latest_issue:
                    return {"status": "ok", "source": "cache", "data": cached_data}
            except Exception:
                pass

        try:
            from backend.core.prime_composite_engine import run_prime_tail_analysis_pipeline
            fresh_data = run_prime_tail_analysis_pipeline()
            return {"status": "ok", "source": "live", "data": fresh_data}
        except Exception as e:
            return {"status": "error", "message": f"计算质合数与尾数香农熵异常: {str(e)}"}

    def get_psychological_game_analysis(self, force_refresh: bool = False) -> Dict[str, Any]:
        """B3 包装层: 原逻辑不动, 只往响应里注入观察仓状态牌。"""
        res = self._get_psychological_game_analysis_raw(force_refresh=force_refresh)
        if isinstance(res, dict) and res.get("status") == "ok":
            res["module_gate"] = self._observation_tag("psychological_game")
        return res

    def _get_psychological_game_analysis_raw(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取心理博弈论与逆向均值回归综合量化推演数据

        @param force_refresh 是否强制重新计算落盘
        @return 包含突击Top5、稳健Top12、弹性冷号名单、健康重号、宏观钟摆态势的字典
        """
        json_path = os.path.join(self.proj_dir, "storage", "stats", "psychological_game_analysis.json")
        if not force_refresh and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)

                # 步骤 1: 校验缓存期号是否与全量历史最新开奖对齐 (防止跨天出现陈旧缓存)
                from backend.utils.history_loader import load_history
                hist = load_history()
                latest_issue = str(hist[0].get("issue") or hist[0].get("period") or "") if hist else ""
                if cached_data.get("based_on_period") == latest_issue and latest_issue:
                    return {"status": "ok", "source": "cache", "data": cached_data}
            except Exception:
                pass

        try:
            from backend.core.psychological_game_engine import run_psychological_game_pipeline
            fresh_data = run_psychological_game_pipeline()
            return {"status": "ok", "source": "live", "data": fresh_data}
        except Exception as e:
            return {"status": "error", "message": f"计算心理博弈与逆向均值回归异常: {str(e)}"}

    def get_psychological_game_backtest(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取心理博弈论与逆向均值回归严格样本外滚动回测数据 (30/50/100/200周期与近100期明细)
        
        @param force_refresh 是否强制重新回测
        @return 包含多周期汇总与近100期逐期明细账本的字典
        """
        json_path = os.path.join(self.proj_dir, "storage", "reviews", "psychological_game_backtest_ledger.json")
        if not force_refresh and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)

                # 步骤 1: 校验缓存期号是否与全量历史最新开奖对齐 (防止跨天出现陈旧缓存)
                from backend.utils.history_loader import load_history
                hist = load_history()
                latest_issue = str(hist[0].get("issue") or hist[0].get("period") or "") if hist else ""
                end_issue = str(cached_data.get("multi_window_summary", {}).get("last_100", {}).get("end_issue") or "")
                total_draws = cached_data.get("meta", {}).get("total_history_draws")
                if end_issue == latest_issue and total_draws == len(hist) and latest_issue:
                    return {"status": "ok", "source": "cache", "data": cached_data}
            except Exception:
                pass

        try:
            from backend.audit.backtest_psychological_game_theory import PsychologicalGameTheoryAuditor
            auditor = PsychologicalGameTheoryAuditor()
            auditor.generate_full_audit_ledger_and_report()
            with open(json_path, "r", encoding="utf-8") as f:
                fresh_data = json.load(f)
            return {"status": "ok", "source": "live", "data": fresh_data}
        except Exception as e:
            return {"status": "error", "message": f"计算心理博弈回测对账异常: {str(e)}"}

