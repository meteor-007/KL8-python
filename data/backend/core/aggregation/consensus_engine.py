# -*- coding: utf-8 -*-
"""
consensus_engine.py — 终审多维共振投票、8区空间平衡与全系统数据汇总复盘引擎
"""
import os
import re
import glob
import json
from collections import Counter
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

from .stable_evaluator import top_freq_in_window, walk_forward_stable
from .proxy_generator import generate_proxy_signals

NUM_TOTAL = 80
BASE_RATE = 20 / 80


class ConsensusEngine:
    def __init__(self, data_root: Optional[str] = None):
        if data_root is None:
            self.data_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.data_root = data_root
        self.proj_root = os.path.dirname(self.data_root)
        self.history_file = os.path.join(self.data_root, "kl8_history_final.txt")
        self.out_dir = os.path.join(self.data_root, "outputs", "aggregation")
        os.makedirs(self.out_dir, exist_ok=True)

    def load_draws(self) -> List[Dict[str, Any]]:
        draws = []
        if not os.path.exists(self.history_file):
            return draws
        with open(self.history_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.search(r"date:([0-9\-]+),period:(\d+),numbers:([0-9\-]+)", line.strip())
                if not m:
                    continue
                nums = set(int(x) for x in m.group(3).split("-") if x.isdigit())
                if len(nums) == 20:
                    draws.append({
                        "period": int(m.group(2)),
                        "date": m.group(1),
                        "nums": nums
                    })
        draws.sort(key=lambda d: d["period"])
        return draws

    def collect_subsystem_picks(self, target_period: int) -> Dict[str, Set[int]]:
        target = str(target_period)
        picks: Dict[str, Set[int]] = {}

        # 1. 双层LSTM
        for f in glob.glob(os.path.join(self.data_root, "outputs", "predictions", f"prediction_{target}*.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "双层LSTM", "outputs", "predictions", f"prediction_{target}*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"Top10:\s*([0-9\-]+)", txt)
                if m:
                    picks["双层LSTM"] = {int(x) for x in m.group(1).split("-") if x.isdigit()}
            except Exception: pass

        # 2. 定金选2
        for f in glob.glob(os.path.join(self.data_root, "outputs", f"定金选2预测_{target}*.txt")) + \
                 glob.glob(os.path.join(self.data_root, "outputs", "gold_pick2", f"*{target}*.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "定金选2-分析", "output", f"定金选2预测_{target}*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                for m in re.finditer(r"\[(\d{2})-(\d{2})\]", txt):
                    s.add(int(m.group(1))); s.add(int(m.group(2)))
                gm = re.search(r"金胆 (\d{2})", txt)
                if gm: s.add(int(gm.group(1)))
                if s: picks["定金选2"] = s
            except Exception: pass

        # 3. Gemini选2
        for f in glob.glob(os.path.join(self.data_root, "outputs", f"gemini选2预测_{target}*.txt")) + \
                 glob.glob(os.path.join(self.data_root, "gemini_pick2", "output", f"gemini选2预测_{target}*.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "gemini选2-预测", "output", f"gemini选2预测_{target}*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                for key in ("核心4码:", "终极5码:"):
                    m = re.search(re.escape(key) + r"\s*([0-9\-]+)", txt)
                    if m: s |= {int(x) for x in m.group(1).split("-") if x.isdigit()}
                gm = re.search(r"金胆 (\d{2}) 银胆 (\d{2}) 铜胆 (\d{2})", txt)
                if gm: s |= {int(gm.group(1)), int(gm.group(2)), int(gm.group(3))}
                if s: picks["Gemini选2"] = s
            except Exception: pass

        # 4. 点位期数追踪
        for f in glob.glob(os.path.join(self.data_root, "outputs", f"*点位每日分析*T{target}*.md")) + \
                 glob.glob(os.path.join(self.proj_root, "点位期数-追踪", "output", f"*点位每日分析*T{target}*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"点位码池\(\d+码.*?\):\s*([0-9\-]+)", txt)
                if m: picks["点位追踪"] = {int(x) for x in m.group(1).split("-") if x.isdigit()}
            except Exception: pass

        # 5. 跟随分析
        for f in glob.glob(os.path.join(self.data_root, "reports", f"daily_{target}_*.txt")) + \
                 glob.glob(os.path.join(self.data_root, "outputs", "follow_analysis", "跟随分析预测.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "跟随分析", "reports", f"daily_{target}_*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                for key in ("重复号Top5:", "综合推演Top6:", "条件跟随Top8:", "重复号Top5 (主候选):", "综合推演Top6 (搭档跟随):", "条件跟随Top8 (多窗软融合):"):
                    m = re.search(re.escape(key) + r"\s*([0-9\-]+)", txt)
                    if m: s |= {int(x) for x in m.group(1).split("-") if x.isdigit()}
                if s: picks["跟随分析"] = s
            except Exception: pass

        # 6. 重点点位分析
        for f in [os.path.join(self.data_root, "outputs", "重点点位预测.txt"), os.path.join(self.proj_root, "重点点位分析", "output", "重点点位预测.txt")]:
            if os.path.exists(f):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    s = set()
                    for key in ("核心五码:", "精选十码:"):
                        m = re.search(re.escape(key) + r"\s*([0-9\-]+)", txt)
                        if m: s |= {int(x) for x in m.group(1).split("-") if x.isdigit()}
                    if s: picks["重点点位"] = s
                except Exception: pass

        # 7. 顺口溜
        for f in [os.path.join(self.data_root, "outputs", f"顺口溜预测_{target}.txt"), os.path.join(self.proj_root, "顺口溜", "output", f"顺口溜预测_{target}.txt")]:
            if os.path.exists(f):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    m = re.search(r"推荐码:\s*([0-9 ]+)", txt)
                    if m: picks["顺口溜"] = {int(x) for x in m.group(1).split() if x.isdigit()}
                except Exception: pass

        # 8. 首席特供 Hidden Energy 5
        for f in [os.path.join(self.data_root, "outputs", "hidden_energy_5.txt"), os.path.join(self.data_root, "outputs", f"prediction_{target}.txt")]:
            if os.path.exists(f):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    m = re.search(r"(Hidden Energy|首席推荐|最终推荐 5 码).*?:\s*([0-9\- ]+)", txt)
                    if m: picks["首席特供HE5"] = {int(x) for x in re.findall(r"\d{2}", m.group(2))}
                except Exception: pass

        # 9. 16期中热频次推演
        for f in glob.glob(os.path.join(self.data_root, "reports", f"sixteen_analysis_report_{target}*.md")) + \
                 glob.glob(os.path.join(self.data_root, "outputs", "reports", f"sixteen_analysis_report_{target}*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                m = re.search(r"中热精选 5 码防线.*?`([0-9 ]+)`", txt)
                if m: s |= {int(x) for x in m.group(1).split() if x.isdigit()}
                gm = re.search(r"中热首席金胆.*?`(\d{2})`", txt)
                if gm: s.add(int(gm.group(1)))
                if s: picks["16期中热"] = s
            except Exception: pass

        return picks

    def run_aggregation(self, n_review: int = 30) -> Dict[str, Any]:
        draws = self.load_draws()
        if not draws:
            return {"error": "历史数据为空"}

        latest = draws[-1]
        target_period = latest["period"] + 1
        picks = self.collect_subsystem_picks(target_period)

        votes = Counter()
        for name, num_set in picks.items():
            for n in num_set:
                votes[n] += 1

        top_dans = sorted((n for n in votes if votes[n] >= 2), key=lambda n: (-votes[n], n))
        
        zones = [f"{i*10+1:02d}-{i*10+10:02d}" for i in range(8)]
        pool = list(top_dans)
        miss_zones = []
        for z in zones:
            lo, hi = int(z.split("-")[0]), int(z.split("-")[1])
            if not any(lo <= n <= hi for n in pool):
                miss_zones.append(z)
                fill = sorted((n for n in votes if lo <= n <= hi), key=lambda n: -votes[n])
                if fill:
                    pool.append(fill[0])

        pool = sorted(list(set(pool)))

        win = draws[-20:]
        flat_win = Counter(x for s in win for x in s["nums"])
        stable_top10 = [n for n, _ in flat_win.most_common(10)]

        wf_res = self._run_walk_forward(draws, n_review)

        report_txt = self._generate_report_text(target_period, latest, picks, votes, pool, stable_top10, wf_res)
        out_file = os.path.join(self.out_dir, f"汇总复盘_{target_period}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(report_txt)

        result_json = {
            "target_period": target_period,
            "latest_period": latest["period"],
            "latest_date": latest["date"],
            "subsystems_count": len(picks),
            "subsystems_detail": {k: sorted(list(v)) for k, v in picks.items()},
            "consensus_dan_pool": pool,
            "votes_rank": [{"num": n, "votes": votes[n]} for n in sorted(votes.keys(), key=lambda x: (-votes[x], x))],
            "stable_top10": stable_top10,
            "eight_zones_status": {
                "full_coverage": len(miss_zones) == 0,
                "miss_zones": miss_zones
            },
            "walk_forward": wf_res,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_file": os.path.basename(out_file)
        }

        with open(os.path.join(self.out_dir, f"aggregation_{target_period}.json"), "w", encoding="utf-8") as jf:
            json.dump(result_json, jf, ensure_ascii=False, indent=2)

        return result_json

    def _run_walk_forward(self, draws: List[Dict[str, Any]], k: int = 30) -> Dict[str, Any]:
        m = len(draws)
        lo = max(0, m - k)
        stable_hits, stable_n = 0, 0
        cons_hits, cons_n, cons_size = 0, 0, 0

        for t in range(lo, m):
            act = draws[t]["nums"]
            win = draws[max(0, t - 20):t]
            flat = Counter(x for s in win for x in s["nums"])
            top5 = [n for n, _ in flat.most_common(5)]
            stable_hits += len(set(top5) & act)
            stable_n += 1

            sigs = generate_proxy_signals(draws, t)
            votes = Counter()
            for lst in sigs.values():
                for n in lst:
                    votes[n] += 1
            dans = [n for n in votes if votes[n] >= 2]
            cons_hits += len(set(dans) & act)
            cons_size += len(dans)
            cons_n += 1

        stable_avg = stable_hits / stable_n if stable_n else 0
        cons_avg = cons_hits / cons_n if cons_n else 0
        cons_avg_size = cons_size / cons_n if cons_n else 0
        cons_exp = cons_avg_size * BASE_RATE
        cons_lift = (cons_avg / cons_exp) if cons_exp > 0 else 0

        return {
            "stable_mean_hits": round(stable_avg, 2),
            "stable_expected": 1.25,
            "stable_lift": round(stable_avg / 1.25, 2),
            "proxy_consensus_mean_hits": round(cons_avg, 2),
            "proxy_consensus_size": round(cons_avg_size, 1),
            "proxy_consensus_expected": round(cons_exp, 2),
            "proxy_consensus_lift": round(cons_lift, 2)
        }

    def _generate_report_text(self, target, latest, picks, votes, pool, stable_top10, wf_res) -> str:
        lines = [
            f"数据汇总复盘 快乐8 每日终审复盘 {target} (落地整合版 {datetime.now():%Y-%m-%d %H:%M})",
            f"历史基础: 最新开奖 {latest['period']} ({latest['date']}) | 目标期号 {target}",
            f"参与系统: 共 {len(picks)} 路子系统参与投票",
            f"定胆池({len(pool)}码): " + "-".join(f"{x:02d}" for x in pool),
            f"共识明细: {dict((n, votes[n]) for n in sorted(votes, key=lambda x: (-votes[x], x)))}",
            f"stable Top10: " + "-".join(f"{x:02d}" for x in stable_top10),
            f"Walk-Forward 评估: 稳定号 Lift={wf_res['stable_lift']}x | 4路共识 Lift={wf_res['proxy_consensus_lift']}x"
        ]
        return "\n".join(lines)
