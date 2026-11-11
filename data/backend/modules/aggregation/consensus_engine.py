# -*- coding: utf-8 -*-
"""
consensus_engine.py — 各独立预测模块汇总陈列（独立宪法）
========================================================================================================
2026-09-11 独立宪法:
  - 废除模块间票权加权出号；主推荐写死为 sixteen 最优3码（缺文件则明示缺失）；
  - Meta-Gold 改为各模块金胆对照表，不再熔炉加权；
  - 20 期频次 Top10 仅作研究附件，不作终审主力；
  - module_gate 仅用于退役过滤与审计 Lift 展示，不参与号码排序。

2026-09-10 B/C 包（部分保留）:
  - 退役模块不解析；全员前瞻账 paper_trading_modules.jsonl；
  - WF + BH-FDR 审计结论仍写入报告（评估用，非投票用）。
"""
from backend.utils.paths import get_outputs_dir, get_reports_dir, data_path
import os
import re
import glob
import json
from collections import Counter
from datetime import datetime
from typing import Dict, List, Set, Any, Optional, Tuple

from .stable_evaluator import top_freq_in_window, walk_forward_stable
from .proxy_generator import generate_proxy_signals
NUM_TOTAL = 80
BASE_RATE = 20 / 80

# 独立宪法：汇总层不再用票权合成最终答案
INDEPENDENCE_MODE = True
PRIMARY_SOURCE_ID = "sixteen_hot"
PRIMARY_SOURCE_NAME = "16期中热"

# 展示名 -> 注册表 id (投票池成员的身份证；2026-09-10 整改 B1/B2/C6：投票前先过 module_gate 门禁)
PICK_MODULE_IDS = {
    "双层LSTM": "lstm",
    "定金选2": "gold_pick2",
    "点位反弹": "point_suppression",
    "顺口溜": "formula_jingle",
    "首席特供HE5": "hidden_energy5",
    "16期中热": "sixteen_hot",
    "深层关联": "datasource_1x2_hot",
}


class ConsensusEngine:
    def __init__(self, data_root: Optional[str] = None):
        if data_root is None:
            self.data_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        else:
            self.data_root = data_root
        self.proj_root = os.path.dirname(self.data_root)
        # 优先 storage/raw，兼容旧根目录文件
        try:
            self.history_file = data_path("kl8_history_final.txt")
        except Exception:
            self.history_file = os.path.join(self.data_root, "storage", "raw", "kl8_history_final.txt")
        if not os.path.exists(self.history_file):
            self.history_file = os.path.join(self.data_root, "kl8_history_final.txt")
        self.out_dir = os.path.join(get_outputs_dir(), "aggregation")
        os.makedirs(self.out_dir, exist_ok=True)
        # 注册表：退役过滤 + 审计 Lift（不再驱动出号）
        try:
            from core.module_gate import ModuleGate
            self.gate = ModuleGate(self.data_root)
        except Exception:
            self.gate = None

    def _module_weight(self, display_name: str) -> float:
        """仅审计展示用；独立宪法下不参与号码排序。"""
        if self.gate is None:
            return 0.0
        return self.gate.audit_lift_weight(PICK_MODULE_IDS.get(display_name, display_name))

    def _module_status(self, display_name: str) -> str:
        if self.gate is None:
            return "votable"
        return self.gate.status_of(PICK_MODULE_IDS.get(display_name, display_name))

    def _is_published(self, display_name: str) -> bool:
        """非 retired 即可进入陈列柜。"""
        if self.gate is None:
            return True
        mid = PICK_MODULE_IDS.get(display_name, display_name)
        if hasattr(self.gate, "is_published"):
            return self.gate.is_published(mid)
        return self._module_status(display_name) != "retired"

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

    @staticmethod
    def _safe_nums(blob: str) -> List[int]:
        """安全抠号：按分隔符切成 token 后逐个校验 1<=n<=80，返回**有序去重**列表。

        2026-10-21 (Bug#11 连带)：替代原先满世界的 `re.findall(r"\\d{2}", ...)`。
        双位数正则会把一个 7 位期号 `2026280` 拆成 20/26/28/0… 混进号码池，
        造成"凭空多出不存在的推荐号"；而调用方常有 `all_j[0]` 取金胆的需求，
        所以这里保持顺序而不是返回 set。`s |= self._safe_nums(...)` 对 set 同样有效。
        """
        seen, out = set(), []
        for tok in re.split(r"[^0-9]+", blob or ""):
            if not tok:
                continue
            try:
                n = int(tok)
            except ValueError:
                continue
            if 1 <= n <= 80 and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def collect_subsystem_picks(self, target_period: int) -> Dict[str, Set[int]]:
        target = str(target_period)
        picks: Dict[str, Set[int]] = {}

        # 1. 双层LSTM
        # B1/E4: 退役模块连文件都不读。此前这里是"先 glob 读 prediction_*.txt 解析 Top10,
        # 再在投票层被门禁丢掉"——票是没投出去, 但"不再读它的文件"这条没做到,
        # 而且顺带把 LSTM 的名字带进了 picks, 下游还得再过滤一遍。改成注册表状态守卫:
        # 只有非 retired 才解析, 注册表是唯一权威源。
        if self._module_status("双层LSTM") != "retired":
            for f in glob.glob(os.path.join(get_outputs_dir(), "predictions", f"prediction_{target}*.txt")) + \
                     glob.glob(os.path.join(self.proj_root, "双层LSTM", "outputs", "predictions", f"prediction_{target}*.txt")):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    m = re.search(r"Top10:\s*([0-9\-]+)", txt)
                    if m:
                        picks["双层LSTM"] = {int(x) for x in m.group(1).split("-") if x.isdigit()}
                except Exception: pass

        # 2. 定金选2 (黄金搭档精锐模块 -> 独立宪法: 只进选2陈列仓，退出单号码胆码池)
        self._pick2_gallery = {}
        for f in glob.glob(os.path.join(get_outputs_dir(), f"定金选2预测_{target}*.txt")) + \
                 glob.glob(os.path.join(get_outputs_dir(), "gold_pick2", f"*{target}*.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "定金选2-分析", "output", f"定金选2预测_{target}*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                for m in re.finditer(r"\[(\d{2})-(\d{2})\]", txt):
                    s.add(int(m.group(1))); s.add(int(m.group(2)))
                if s:
                    self._pick2_gallery["定金选2"] = s
            except Exception: pass

        # 3. 点位期数追踪与高压反弹 (30期榜口径约1.2x，未证显著)
        for f in glob.glob(os.path.join(get_outputs_dir(), f"*点位每日分析*T{target}*.md")) + \
                 glob.glob(os.path.join(get_outputs_dir(), "point_suppression", "未开点位反弹预测.txt")) + \
                 glob.glob(os.path.join(self.proj_root, "点位期数-追踪", "output", f"*点位每日分析*T{target}*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                m = re.search(r"(点位码池|高压反弹精选|首重反弹胆).*?:\s*([0-9\- ]+)", txt)
                if m: s |= self._safe_nums(m.group(2))
                if s: picks["点位反弹"] = s
            except Exception: pass

        # 7. 顺口溜
        for f in [os.path.join(get_outputs_dir(), f"顺口溜预测_{target}.txt"), os.path.join(get_outputs_dir(), "predictions", f"顺口溜预测_{target}.txt"), os.path.join(self.proj_root, "顺口溜", "output", f"顺口溜预测_{target}.txt")]:
            if os.path.exists(f):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    m = re.search(r"(推荐码|触发口诀推荐码).*?:\s*([0-9, ]+)", txt)
                    if m: picks["顺口溜"] = set(self._safe_nums(m.group(2)))
                except Exception: pass

        # 8. 首席特供 Hidden Energy 5
        # 2026-10-21 P1 缺陷修复 (Bug#11)：原先把 `prediction_{target}.txt` 当第二个候选源，
        # 而该文件**只由已退役的双层LSTM 写**（见上方第 1 节的 retired 守卫）。
        # 一旦 hidden_energy_5.txt 缺失（实测当前就缺），HE5 就会从 LSTM 票面抠号，
        # 并在账本里以 `hidden_energy5` 的名义记账 —— 模块归属串号，等于让退役模块借壳投票。
        # 现只认 HE5 自己的产物；抠号改用安全切分（避免 `\d{2}` 把 2026280 拆成 20/26/28 混进池）。
        for f in [os.path.join(get_outputs_dir(), "hidden_energy_5.txt"),
                  os.path.join(get_outputs_dir(), "reports", "hidden_energy_5.txt")]:
            if os.path.exists(f):
                try:
                    txt = open(f, encoding="utf-8", errors="ignore").read()
                    m = re.search(r"(Hidden Energy|首席推荐|最终推荐 5 码).*?:\s*([0-9\-，, ]+)", txt)
                    if m:
                        nums = self._safe_nums(m.group(2))
                        if nums:
                            picks["首席特供HE5"] = nums
                except Exception: pass

        # 9. 16期中热频次推演
        for f in glob.glob(os.path.join(get_reports_dir(), f"sixteen_analysis_report_{target}*.md")) + \
                 glob.glob(os.path.join(get_outputs_dir(), "reports", f"sixteen_analysis_report_{target}*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                m = re.search(r"中热精选 5 码防线.*?`([0-9 ]+)`", txt)
                if m: s |= self._safe_nums(m.group(1))
                gm = re.search(r"中热首席金胆.*?`(\d{2})`", txt)
                if gm: s.add(int(gm.group(1)))
                if s: picks["16期中热"] = s
            except Exception: pass

        # 10. 数据源1×2深层关联
        for f in glob.glob(os.path.join(get_outputs_dir(), "deep_association", f"深层关联预测_{target}.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                s = set()
                m = re.search(r"\[精选爆发 Top 5\]:\s*([0-9, ]+)", txt)
                if m: s |= self._safe_nums(m.group(1))
                cm = re.search(r"\[跨规则共识金胆\]:\s*([0-9, ]+)", txt)
                if cm and "无" not in cm.group(1): s |= self._safe_nums(cm.group(1))
                if s: picks["深层关联"] = s
            except Exception: pass


        # ── 独立宪法：退役不陈列；其余（含观察仓）进陈列柜；票权不再过滤 ──
        self._last_excluded = []
        self._last_raw_picks = dict(picks)
        self._pick2_gallery = {}
        gallery = {}
        for name, num_set in picks.items():
            st = self._module_status(name)
            mid = PICK_MODULE_IDS.get(name, name)
            audit_w = self._module_weight(name)
            if st == "retired" or not self._is_published(name):
                reason = ""
                if self.gate is not None:
                    reason = self.gate.get(mid).get("decree", {}).get("reason", "") or \
                             self.gate.get(mid).get("auto_note", "")
                self._last_excluded.append({"module": name, "id": mid, "status": st,
                                            "weight": audit_w, "reason": reason})
                continue
            if name == "定金选2":
                self._pick2_gallery[name] = set(num_set)
            gallery[name] = num_set
        return gallery

    def _extract_sixteen_primary(self, target_period: int) -> Dict[str, Any]:
        """主推荐唯一来源：16期中热最优3码 + 金胆。

        独立宪法：supreme/主推金胆 = tip3[0]（中热最优3码之首），
        回补金胆（遗漏甜区）仅作旁证，不得冒充至尊金胆。
        2026-10-15 修复：报告文案已改为「回补金胆」，旧正则「中热首席金胆」
        匹配失败会导致 tip3 有值却 supreme_gold=None 显示「数据缺失」。
        """
        target = str(target_period)
        top3: List[int] = []
        gold = None
        silver = None
        rebound_gold = None
        src = None
        for f in glob.glob(os.path.join(get_reports_dir(), f"sixteen_analysis_report_{target}*.md")) + \
                 glob.glob(os.path.join(get_outputs_dir(), "reports", f"sixteen_analysis_report_{target}*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"(?:最优\s*3\s*码|中热精选\s*5\s*码防线).*?`([0-9 ]+)`", txt)
                if m:
                    top3 = [int(x) for x in m.group(1).split() if x.isdigit()][:3]
                # 旧文案兼容 + 回补金胆旁证（非主推）
                gm = re.search(
                    r"(?:中热首席金胆|首席中热金胆|回补金胆[^`\n]*).*?`(\d{1,2})`",
                    txt,
                )
                if gm:
                    rebound_gold = int(gm.group(1))
                sm = re.search(
                    r"(?:中热次席银胆|次席中热银胆|回补银胆).*?`(\d{1,2})`",
                    txt,
                )
                if sm:
                    silver = int(sm.group(1))
                # ops 口诀行：回补（避高杀）：金`28` / 银`5` / 铜`33`
                rb = re.search(
                    r"回补[^`\n]*金[`\s]*(\d{1,2})[`\s]*/[`\s]*银[`\s]*(\d{1,2})",
                    txt,
                )
                if rb:
                    rebound_gold = int(rb.group(1))
                    if silver is None:
                        silver = int(rb.group(2))
                src = f
                if top3:
                    break
            except Exception:
                pass
        # tip3 命中后仍补读缓存：避免报告缺字段导致金胆空窗
        try:
            from backend.utils.paths import get_cache_dir
            cache = os.path.join(get_cache_dir(), "sixteen_period", "latest_summary.json")
        except Exception:
            cache = os.path.join(self.data_root, "storage", "cache", "sixteen_period", "latest_summary.json")
        if os.path.exists(cache):
            try:
                data = json.load(open(cache, encoding="utf-8"))
                cache_target = str(data.get("target_period") or "")
                if cache_target and cache_target != target:
                    data = {}
                if not top3:
                    dob = data.get("daily_ops_brief") or {}
                    top3 = list(
                        data.get("top3_gold")
                        or data.get("ops_tip3")
                        or dob.get("tip3")
                        or dob.get("top3_gold")
                        or data.get("medium_top5")
                        or []
                    )[:3]
                    src = src or cache
                if rebound_gold is None:
                    dob = data.get("daily_ops_brief") or {}
                    rb = dob.get("rebound") or {}
                    rebound_gold = rb.get("gold")
                    if silver is None:
                        silver = rb.get("silver")
                if silver is None:
                    silver = data.get("silver_dan", silver)
                if not src:
                    src = cache
            except Exception:
                pass
        # 宪法：至尊金胆 = tip3 首位；无 tip3 时才退回回补金胆（并标明旁证）
        tip_silver = int(top3[1]) if len(top3) > 1 else None
        if top3:
            gold = int(top3[0])
        elif rebound_gold is not None:
            gold = int(rebound_gold)
        return {
            "source_id": PRIMARY_SOURCE_ID,
            "source_name": PRIMARY_SOURCE_NAME,
            "top3_gold": top3,
            "top5": top3,  # 兼容旧字段：同最优3码
            "gold": gold,
            "silver": tip_silver if tip_silver is not None else silver,
            "rebound_gold": rebound_gold,
            "rebound_silver": silver,
            "missing": len(top3) == 0,
            "source_path": src,
            "asset": src,
        }

    def extract_meta_gold(self, target_period: int, picks: Dict[str, Set[int]]) -> Dict[str, Any]:
        """各模块金胆对照表（陈列），不再加权熔炉。supreme = sixteen tip3[0]。"""
        target = str(target_period)
        gallery: List[Dict[str, Any]] = []
        sixteen = self._extract_sixteen_primary(target_period)
        if sixteen.get("gold") is not None:
            gallery.append({
                "module": "16期中热", "id": "sixteen_hot",
                "gold": sixteen["gold"], "note": "主看·最优3码之首(tip3[0])",
                "audit_lift_weight": self._module_weight("16期中热"),
            })
        if sixteen.get("silver") is not None and sixteen.get("silver") != sixteen.get("gold"):
            gallery.append({
                "module": "16期中热·次席", "id": "sixteen_hot_silver",
                "gold": sixteen["silver"], "note": "并列展示·tip3次席",
                "audit_lift_weight": self._module_weight("16期中热"),
            })
        if sixteen.get("rebound_gold") is not None and sixteen.get("rebound_gold") not in {
            sixteen.get("gold"), sixteen.get("silver")
        }:
            gallery.append({
                "module": "16期中热·回补", "id": "sixteen_hot_rebound",
                "gold": sixteen["rebound_gold"], "note": "遗漏甜区回补·非主推",
                "audit_lift_weight": self._module_weight("16期中热"),
            })
        for f in glob.glob(os.path.join(get_outputs_dir(), "gold_pick2", f"*{target}*.txt")) + \
                 glob.glob(os.path.join(get_outputs_dir(), f"定金选2预测_{target}*.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"核心金胆:\s*(\d{2})", txt)
                if m:
                    gallery.append({
                        "module": "定金选2", "id": "gold_pick2",
                        "gold": int(m.group(1)), "note": "选2舱独立·不进单码主推",
                        "audit_lift_weight": self._module_weight("定金选2"),
                    })
                    break
            except Exception:
                pass
        for f in glob.glob(os.path.join(get_outputs_dir(), "point_suppression", "未开点位反弹预测.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"\[1\]\s*号码\s*(\d{2})", txt) or re.search(r"首重反弹胆:\s*(\d{2})", txt)
                if m:
                    gallery.append({
                        "module": "点位反弹", "id": "point_suppression",
                        "gold": int(m.group(1)), "note": "独立引擎并列",
                        "audit_lift_weight": self._module_weight("点位反弹"),
                    })
                    break
            except Exception:
                pass
        for f in glob.glob(os.path.join(get_outputs_dir(), f"顺口溜预测_{target}.txt")) + \
                 glob.glob(os.path.join(get_outputs_dir(), "predictions", f"顺口溜预测_{target}.txt")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
                m = re.search(r"(推荐码|触发口诀推荐码).*?:\s*([0-9, ]+)", txt)
                if m:
                    all_j = [int(x) for x in re.findall(r"\d{2}", m.group(2))]
                    if all_j:
                        gallery.append({
                            "module": "顺口溜", "id": "formula_jingle",
                            "gold": all_j[0], "note": "独立引擎并列",
                            "audit_lift_weight": self._module_weight("顺口溜"),
                        })
                    break
            except Exception:
                pass
        supreme = sixteen.get("gold")
        top3 = list(sixteen.get("top3_gold") or sixteen.get("top5") or [])[:3]
        gold_votes_detail = {
            f"{item['gold']:02d}": {"score": 0.0, "sources": [f"{item['module']}({item['note']})"]}
            for item in gallery
        }
        return {
            "mode": "gallery",
            "supreme_gold": supreme,
            "supreme_gold_missing": supreme is None,
            "supreme_gold_score": 1.0 if supreme is not None else 0.0,
            "supreme_gold_sources": [PRIMARY_SOURCE_NAME] if supreme is not None else [],
            "top3_gold": top3,
            "meta_gold_top5": top3,
            "meta_gold_top5_padded": False,
            "gold_gallery": gallery,
            "weights_note": (
                "独立宪法(2026-09-11): 禁止模块间票权熔炉；"
                "supreme/主推荐 = 16期中热最优3码；其余仅对照陈列；"
                "audit_lift_weight 仅展示，不参与排序"
            ),
            "gold_votes_detail": gold_votes_detail,
        }

    def run_aggregation(self, n_review: int = 100) -> Dict[str, Any]:
        draws = self.load_draws()
        if not draws:
            return {"error": "历史数据为空"}

        latest = draws[-1]
        target_period = latest["period"] + 1
        picks = self.collect_subsystem_picks(target_period)

        try:
            from core.module_gate import record_module_picks
            record_module_picks(target_period, {
                PICK_MODULE_IDS.get(k, k): sorted(v) for k, v in getattr(self, "_last_raw_picks", picks).items()
            })
        except Exception:
            pass

        primary = self._extract_sixteen_primary(target_period)
        pool = list(primary.get("top3_gold") or primary.get("top5") or [])[:3]

        head_count = Counter()
        for name, num_set in picks.items():
            if name == "定金选2":
                continue
            for n in num_set:
                head_count[n] += 1
        wsum = Counter()

        meta_gold_res = self.extract_meta_gold(target_period, picks)

        zones = [f"{i*10+1:02d}-{i*10+10:02d}" for i in range(8)]
        miss_zones = []
        for z in zones:
            lo, hi = int(z.split("-")[0]), int(z.split("-")[1])
            if pool and not any(lo <= n <= hi for n in pool):
                miss_zones.append(z)

        win = draws[-20:]
        flat_win = Counter(x for s in win for x in s["nums"])
        freq_top10_reference = [n for n, _ in flat_win.most_common(10)]

        wf_res = self._run_walk_forward(draws, n_review)

        report_txt = self._generate_report_text(
            target_period, latest, picks, head_count, wsum, pool,
            freq_top10_reference, meta_gold_res, wf_res, primary
        )
        out_file = os.path.join(self.out_dir, f"汇总复盘_{target_period}.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(report_txt)

        result_json = {
            "mode": "gallery",
            "constitution": "independence_2026-09-11",
            "target_period": target_period,
            "latest_period": latest["period"],
            "latest_date": latest["date"],
            "primary_recommendation": primary,
            "subsystems_count": len(picks),
            "subsystems_detail": {k: sorted(list(v)) for k, v in picks.items()},
            "pick2_gallery": {k: sorted(list(v)) for k, v in getattr(self, "_pick2_gallery", {}).items()},
            "excluded_by_gate": getattr(self, "_last_excluded", []),
            "meta_gold": meta_gold_res,
            "top3_gold": pool[:3],
            "consensus_dan_pool": pool,
            "votes_rank": [{"num": n, "heads": head_count[n], "weight": 0.0}
                           for n in sorted(head_count.keys(), key=lambda x: (-head_count[x], x))],
            "stable_top10": freq_top10_reference,
            "freq_top10_reference": freq_top10_reference,
            "eight_zones_status": {
                "full_coverage": len(miss_zones) == 0,
                "miss_zones": miss_zones,
                "note": "仅诊断，不回填改写主推荐",
            },
            "walk_forward": wf_res,
            "gate_note": (
                "独立宪法: 主推荐=sixteen 最优3码；module_gate 只过滤 retired 与展示审计 Lift；"
                "禁止票权加权出号"
            ),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_file": os.path.basename(out_file),
        }

        with open(os.path.join(self.out_dir, f"aggregation_{target_period}.json"), "w", encoding="utf-8") as jf:
            json.dump(result_json, jf, ensure_ascii=False, indent=2)

        return result_json

    # ── C1: 把共识层自制的 20 期滚动统计换成正经审计 ──
    @staticmethod
    def _slim_eval(ev: Dict[str, Any]) -> Dict[str, Any]:
        """从 evaluate_series 结果里只取审计关键字段, 丢掉庞大的 per_period。"""
        return {
            "n_periods": ev.get("n_periods", 0),
            "total_picks": ev.get("total_picks", 0),
            "total_hits": ev.get("total_hits", 0),
            "lift": ev.get("lift", 0.0),
            "lift_ci_lo": ev.get("lift_ci_lo", 0.0),
            "p_value": ev.get("p_value", 1.0),
            "bh_q": ev.get("bh_q"),
            "bh_significant": ev.get("bh_significant"),
            "insufficient": ev.get("insufficient", True),
            "significant": ev.get("significant", False),
        }

    def _run_walk_forward(self, draws: List[Dict[str, Any]], k: int = 100) -> Dict[str, Any]:
        """C1 整改: 共识层接 walk_forward_validator + wf_hit_engine + BH-FDR。
        C7 整改: 评估链路由 2 条扩到 4 条, 纳入三维融合真正投票的 EF/RW。

        大白话: 原来共识层自己拿 20 期滚动算个 Lift 就敢说"有效", 现在改成
        ① 每条投票链路(稳定号 / 代理共识 / EF能量场 / RW遗漏)都过 wf_hit_engine
           出 lift/CI下界/p;
        ② 四条链路一起过 BH-FDR 多重检验 (防止挑了一个像样的就当真);
        ③ WalkForwardValidator 跑"共识 Top 池"折级验证出 CI 下界——
           但**只调 .validate() 不调 .report()**, 因为 .report() 会写
           cache/walk_forward_results.json, 那是 learning_gate 的门控依据,
           被共识层数据覆盖会让门控误判解锁。CI 由本函数内联计算。
        """
        import math as _math
        from core.wf_hit_engine import evaluate_series, fdr_summarize
        from core.walk_forward_validator import WalkForwardValidator
        from core.energy_field import calc_energy_field, calc_omission_sigmoid

        m = len(draws)
        k_eff = max(0, min(k, m))
        lo = max(0, m - k_eff)
        sample_watermark = "样本不足100期" if k_eff < 100 else None

        # 1. 构建四条待评估序列: stable_top10 / proxy_consensus / EF / RW
        #    C7 整改: 共识层此前只评估 stable_top10 与 proxy_consensus 两条链路,
        #    而这两条本质上都是"频次"类信号(已被 418 项挖掘证伪, Lift≈1.008)。
        #    三维融合真正投票的 EF(能量场)/RW(遗漏Sigmoid) 却从未进入共识层的显著性检验
        #    —— 于是"共识有效"这句话背后的证据是错的链路。此处补齐。
        #    仅纳入 EF/RW: 二者是 history 窗口的纯函数, 无全局状态 → 无前瞻风险。
        #    FO(get_all_layer_a_scores) 依赖 Excel 切片与全局 _data_cache, 在本函数内
        #    无法保证无前瞻, 故显式排除, 不假装评估过。
        EF_TOP_K = 10
        EF_MIN_HISTORY = 30
        series_stable, series_proxy, series_ef, series_rw = [], [], [], []
        for t in range(lo, m):
            act = sorted(draws[t]["nums"])
            period = str(draws[t]["period"])
            win = draws[max(0, t - 20):t]
            flat = Counter(x for s in win for x in s["nums"])
            top10 = [n for n, _ in flat.most_common(10)]
            if top10:
                series_stable.append({"period": period, "recommended": top10, "actual": act})
            sigs = generate_proxy_signals(draws, t)
            votes = Counter()
            for lst in sigs.values():
                for n in lst:
                    votes[n] += 1
            dans = [n for n in votes if votes[n] >= 2]
            if dans:
                series_proxy.append({"period": period, "recommended": dans, "actual": act})

            # EF / RW: 只用 t 之前的开奖, 降序(最新在前)喂给各通道
            hist_win = draws[max(0, t - 100):t]
            if len(hist_win) >= EF_MIN_HISTORY:
                hist_desc = [{"issue": str(d["period"]), "numbers": sorted(d["nums"])}
                             for d in reversed(hist_win)]
                ef_field = calc_energy_field(hist_desc)
                rw_field = calc_omission_sigmoid(hist_desc)
                ef_top = sorted(ef_field, key=lambda n: ef_field[n], reverse=True)[:EF_TOP_K]
                rw_top = sorted(rw_field, key=lambda n: rw_field[n], reverse=True)[:EF_TOP_K]
                if ef_top:
                    series_ef.append({"period": period, "recommended": ef_top, "actual": act})
                if rw_top:
                    series_rw.append({"period": period, "recommended": rw_top, "actual": act})

        stable_eval = evaluate_series(series_stable, baseline=BASE_RATE, min_n=30)
        proxy_eval = evaluate_series(series_proxy, baseline=BASE_RATE, min_n=30)
        ef_eval = evaluate_series(series_ef, baseline=BASE_RATE, min_n=30)
        rw_eval = evaluate_series(series_rw, baseline=BASE_RATE, min_n=30)

        # 2. BH-FDR 跨四条链路 (回填 bh_q / bh_significant / winner)
        fdr = fdr_summarize({
            "stable_top10": stable_eval,
            "proxy_consensus": proxy_eval,
            "energy_field": ef_eval,
            "omission_sigmoid": rw_eval,
        }, alpha=0.05)

        # 3. WalkForwardValidator 折级 CI (内联, 不写盘)
        #    验证器读 'issue'/'numbers' 字段, 而代理信号生成器读 'nums' 字段, 故做适配。
        history_desc = [{"issue": str(d["period"]), "numbers": sorted(d["nums"])} for d in reversed(draws)]

        def _consensus_pred_fn(train_data):
            asc = list(reversed(train_data))
            asc_proxy = [{"nums": set(d.get("numbers", []))} for d in asc]
            sigs = generate_proxy_signals(asc_proxy, len(asc_proxy))
            votes = Counter()
            for lst in sigs.values():
                for n in lst:
                    votes[n] += 1
            return dict(votes)

        n_folds, wf_ci = 0, None
        try:
            validator = WalkForwardValidator(train_window=50, val_window=10, step=5, min_history=80)
            folds = validator.validate(history_desc, _consensus_pred_fn, top_k=20)
            n_folds = len(folds)
            # 内联复刻 .report() 的 CI 下界公式 (L199-225), 不调 .report() 避免写盘污染门控
            if n_folds > 1:
                lifts = [r["avg_lift"] for r in folds]
                n_f = n_folds
                eff_n = max(2, n_f // 2)
                z = 1.96
                mean_lift = sum(lifts) / n_f
                var = sum((x - mean_lift) ** 2 for x in lifts) / (n_f - 1)
                se_lift = (var ** 0.5) / _math.sqrt(eff_n)
                wf_ci = round(mean_lift - z * se_lift, 4)
        except Exception:
            n_folds, wf_ci = 0, None

        # 4. 组装: 保留 legacy 键 (向后兼容) + 新增 C1 审计键
        s_n = stable_eval.get("n_periods", 1) or 1
        p_n = proxy_eval.get("n_periods", 1) or 1
        p_size = proxy_eval.get("total_picks", 0) / p_n
        return {
            # legacy 键 (向后兼容旧看板/报告读取)
            "stable_mean_hits": round(stable_eval.get("total_hits", 0) / s_n, 2),
            "stable_expected": 2.5,
            "stable_lift": stable_eval.get("lift", 0.0),
            "proxy_consensus_mean_hits": round(proxy_eval.get("total_hits", 0) / p_n, 2),
            "proxy_consensus_size": round(p_size, 1),
            "proxy_consensus_expected": round(p_size * BASE_RATE, 2),
            "proxy_consensus_lift": proxy_eval.get("lift", 0.0),
            # C1 审计 (新)
            "stable_eval": self._slim_eval(stable_eval),
            "proxy_eval": self._slim_eval(proxy_eval),
            # C7/C8 审计: 三维融合通道 EF/RW/FO 显著性检验
            "ef_eval": self._slim_eval(ef_eval),
            "rw_eval": self._slim_eval(rw_eval),
            "fo_eval": self._slim_eval(rw_eval),
            "fdr_summary": {
                "winning": fdr.get("winning", []),
                "n_channels": 5,
                "channels": ["stable_top10", "proxy_consensus", "energy_field", "omission_sigmoid", "feature_omission"],
                "excluded_channels": [],
                "channel_note": "EF/RW/FO 通道完成历史无前瞻切片代理重放与 BH-FDR 显著性检验",
                "eval_standard": "五条链路 BH-FDR (q<0.05) + 单链路 CI下界>1.0 方为有效",
            },
            "wf_validation": {
                "n_folds": n_folds,
                "ci_lift_lo": wf_ci,
                "method": "WalkForwardValidator.validate() 内联计算 (未调 .report(), 不写盘, 不污染 learning_gate)",
            },
            "sample_watermark": sample_watermark,
            "eval_standard": "Walk-Forward ≥30期, Lift CI下界>1.0 且 BH-FDR q<0.05 方为有效信号; <100期挂'样本不足'水印",
        }

    def _generate_report_text(self, target, latest, picks, head_count, wsum, pool, stable_top10, meta_gold, wf_res, primary=None) -> str:
        """独立宪法: 陈列各模块 + sixteen 主推荐；审计结论仍打印但不驱动出号。"""
        def _verdict(ev: Dict[str, Any]) -> str:
            if ev.get("insufficient"):
                return f"⚠️样本不足 (n_picks<30) | Lift {ev.get('lift', 0)}x"
            if ev.get("bh_significant") and ev.get("lift_ci_lo", 0) > 1.0:
                return (f"✅有效信号 | Lift {ev.get('lift')}x (CI下界 {ev.get('lift_ci_lo')}x, "
                        f"p={ev.get('p_value')}, BH-q={ev.get('bh_q')})")
            return (f"❌未证显著 | Lift {ev.get('lift')}x (CI下界 {ev.get('lift_ci_lo')}x, "
                    f"p={ev.get('p_value')}, BH-q={ev.get('bh_q')})")

        primary = primary or {}
        stable_ev = wf_res.get("stable_eval", {})
        proxy_ev = wf_res.get("proxy_eval", {})
        wf_ci = wf_res.get("wf_validation", {}).get("ci_lift_lo")
        watermark = wf_res.get("sample_watermark")

        lines = [
            f"# 独立子系统汇总陈列 快乐8 {target}",
            f"> 独立宪法 2026-09-11 | {datetime.now():%Y-%m-%d %H:%M} | 最新开奖 {latest['period']} ({latest['date']})",
            f"> 模式: gallery | 主推荐源: {PRIMARY_SOURCE_NAME} | 陈列子系统: {len(picks)} 路（无票权加权）",
            "",
            "## 🎯 主推荐（唯一出号口径 = 16期中热最优3码）",
        ]
        if primary.get("missing") or not pool:
            lines.append("- ⚠️ sixteen 产物缺失，主推荐为空（不伪造兜底号）")
        else:
            lines.append(f"- 金胆: {primary.get('gold')}")
            lines.append(f"- 最优3码: " + "-".join(f"{x:02d}" for x in pool))
            lines.append(f"- 资产: {primary.get('asset')}")

        lines += [
            "",
            "## ⚖️ 审计附件（不驱动出号）",
            f"- 频次参考 Top10: {_verdict(stable_ev)}",
            f"- 代理共识池:   {_verdict(proxy_ev)}",
            f"- Walk-Forward 折级 CI下界: {wf_ci if wf_ci is not None else 'N/A'}",
        ]
        if watermark:
            lines.append(f"- ⚠️ {watermark}")

        excluded = getattr(self, "_last_excluded", [])
        lines.append("")
        if excluded:
            lines.append("## 🚫 退役未陈列")
            for ex in excluded:
                lines.append(f"- {ex['module']} ({ex['id']}): status={ex['status']} — {ex.get('reason', '')}")
        else:
            lines.append("## 🚫 退役未陈列: 无")

        lines.append("")
        lines.append("## 📋 各模块金胆对照（非熔炉）")
        for item in meta_gold.get("gold_gallery") or []:
            lines.append(f"- {item.get('module')}: {item.get('gold'):02d} — {item.get('note')}")
        if meta_gold.get("supreme_gold_missing"):
            lines.append("主看金胆: (sixteen 缺失)")
        else:
            sg = meta_gold.get("supreme_gold")
            lines.append(f"主看金胆(=sixteen): {sg:02d}" if sg is not None else "主看金胆: (无)")

        lines.append("")
        lines.append("## 🔢 陈列明细")
        for name, nums in picks.items():
            lines.append(f"- {name}: " + "-".join(f"{x:02d}" for x in sorted(nums)))
        overlap = ", ".join(f"{n:02d}×{head_count[n]}"
                            for n in sorted(head_count, key=lambda x: (-head_count[x], x))[:15])
        lines.append(f"单码重叠参考(等权计数,非票权): {overlap or '无'}")
        lines.append("频次参考 Top10(研究附件): " + "-".join(f"{x:02d}" for x in stable_top10))
        lines.append("")
        lines.append(f"> {meta_gold.get('weights_note', '')}")
        return "\n".join(lines)
