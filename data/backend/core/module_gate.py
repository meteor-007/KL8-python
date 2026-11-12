# -*- coding: utf-8 -*-
"""
module_gate.py — 全系统模块投票注册表与上线门禁 (Module Vote Registry & Admission Gate)
=====================================================================================
整改落地: B包(止血) + C6(新模块门禁) + D3(黑名单 live 化)

大白话:
  以前"哪个模块能投票、投多重"散在 20+ 处硬编码数字里, 谁也说不清凭什么。
  本模块建立【唯一权威源】 backend/config/module_vote_registry.json:
    - status: votable / observation / retired（上架徽章与退役过滤）
    - vote_weight / audit_lift_weight: 仅审计展示用 Lift 派生值
  独立宪法 2026-09-11: vote_weight **禁止**驱动号码排序或模块间熔炉；
  主推荐由单引擎（默认 sixteen）独立产出，汇总层只做陈列。
"""
from backend.utils.paths import get_cache_dir
import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Any, Optional

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in (_BACKEND_DIR, _PROJ_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.history_loader import load_history

REGISTRY_FILE = os.path.join(_PROJ_DIR, "backend", "config", "module_vote_registry.json")
DECREE_OVERRIDE_FILE = os.path.join(_PROJ_DIR, "backend", "config", "module_decree_overrides.json")
MODULE_LEDGER_FILE = os.path.join(get_cache_dir(), "paper_trading_modules.jsonl")
MASTER_LEDGER_FILE = os.path.join(_PROJ_DIR, "storage", "reviews", "master_review_ledger.json")

BASELINE = 0.25
MIN_PROSPECTIVE_PERIODS = 200      # C6: 新模块前瞻账门槛
FDR_ALPHA = 0.05
SHRINK_N0 = 30.0                   # C2: 赢家诅咒收缩先验强度
# 独立宪法: 出号路径不得使用票权
SCORING_USES_VOTE_WEIGHT = False


def load_decree_overrides(proj_dir: Optional[str] = None) -> Dict[str, Dict]:
    """人工裁决层 (C4: weekly_advisor --apply 的唯一落点)。

    大白话: 判决层(retired/observation)默认写在代码的 MODULE_SEED 里, 机器每晚
    只能"降级不能升级"。人类看完《周度权重调整建议单》后拍板的事项(比如某个观察
    仓模块满 200 期且显著, 批准升为有票权), 需要一个人写下来的地方 —— 就是本文件。
    覆盖项带 who/when/why/basis(依据哪份建议单), 可追溯; 文件不存在 = 无人工覆盖。
    """
    path = DECREE_OVERRIDE_FILE if proj_dir is None else \
        os.path.join(proj_dir, "backend", "config", "module_decree_overrides.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ov = data.get("overrides", {})
        return ov if isinstance(ov, dict) else {}
    except Exception:
        return {}


def save_decree_overrides(overrides: Dict[str, Dict], proj_dir: Optional[str] = None,
                          entry: Optional[Dict] = None):
    """写回人工裁决层 (保留 applied_log 审计轨迹)。"""
    path = DECREE_OVERRIDE_FILE if proj_dir is None else \
        os.path.join(proj_dir, "backend", "config", "module_decree_overrides.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"note": "C4 周度建议单的人工裁决层; 由 python -m backend.core.weekly_advisor --apply 写入",
            "overrides": overrides, "applied_log": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f)
            data["applied_log"] = old.get("applied_log", [])
        except Exception:
            pass
    if entry:
        data["applied_log"].append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path

# ──────────────────────────────────────────────────────────────
#  模块总册 (种子定义)
#  cohort=legacy    : 2026-09-10 门禁建立前已存在的老模块, 按 live 收缩 Lift 给票权
#  cohort=registered: 门禁建立后上线的新模块, 必须走 200 期前瞻+FDR 才能升 votable
#  decree           : 人类判决层 (带理由与日期); live 证据只能进一步降级, 不能覆盖判决
# ──────────────────────────────────────────────────────────────
MODULE_SEED: Dict[str, Dict[str, Any]] = {
    # ── 老模块 (legacy) · daily 舱 ──
    "sixteen_hot": {
        "name": "16期中热号出窗进窗推演", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "全系统唯一样本外验证正信号 (引擎级诚实回测 top5≈1.22x/top10≈1.11x)"},
        "seed_audit_lift": 1.25,
    },
    "trinity_top12": {
        "name": "Trinity 三维融合 Top 12", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "30期榜 1.22x, 未证显著, 权重按收缩后 Lift 计"},
        "seed_audit_lift": 1.22,
    },
    "aggregation_stable10": {
        "name": "终审共识 Stable Top 10", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "30期榜 1.13x, 未证显著, 权重按收缩后 Lift 计"},
        "seed_audit_lift": 1.13,
    },
    "trinity_top5": {
        "name": "Trinity 三维融合 Top 5", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "30期榜 1.12x, 未证显著, 权重按收缩后 Lift 计"},
        "seed_audit_lift": 1.12,
    },
    "point_suppression": {
        "name": "空间高压反弹与影子追踪", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "30期榜 1.20x 但 z=-0.19 小样本, 权重按收缩后 Lift 计"},
        "seed_audit_lift": 1.20,
    },
    "gold_pick2": {
        "name": "黄金定胆选2搭档", "cohort": "legacy", "kind": "pick2", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-10",
                   "reason": "30期双中率10.0%/Lift 1.65x 但仅3次双中 p≈0.27 未证显著; "
                             "选2玩法盈亏平衡需真实 Lift≥1.75x, 当前仅作研究记账"},
        "seed_audit_lift": 1.65, "pick2_baseline": 0.0607,
    },
    "formula_jingle": {
        "name": "顺口溜 90 条精英口诀", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "retired", "date": "2026-11-12",
                   "reason": "2026-11-12 退役: 全量前瞻账 403票/90中 Lift=0.89x(单侧p=0.118), "
                             "30期 Lift=0.83x; 单模块占全部台账票数 6.1%, 是最大稀释源。"
                             "引擎与产物保留, 撤销判决即可复启"},
        "seed_audit_lift": 1.07,
    },
    "datasource": {
        "name": "数据源1×2 矩阵联动", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-15",
                   "reason": "日常编排舱：出号侧最优3码存档；杀号产品已退役"},
        "aliases": ["datasource_1x2"],
    },
    "tri_high": {
        "name": "三高×点位协同", "cohort": "registered", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-15",
                   "reason": "日常舱：依赖手工三高录入，记前瞻账"},
    },
    "point_omission": {
        "name": "点位与遗漏", "cohort": "registered", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-15",
                   "reason": "日常舱：依赖点位录入"},
    },
    "multi_resonance": {
        "name": "多维共振", "cohort": "registered", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-15",
                   "reason": "日常舱陈列，不作主推"},
    },
    "aggregation": {
        "name": "子系统汇总陈列", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "votable", "date": "2026-09-15",
                   "reason": "陈列层；主推仍=sixteen_hot，不恢复票权熔炉"},
        "aliases": ["aggregation_stable10"],
    },

    # ── 判决退役 (retired, B1/B2/E3/D3) ──
    "lstm": {
        "name": "双层LSTM时序深度学习", "cohort": "legacy", "lane": "research",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "B1: 30期实测 Top10 Lift=0.98x 负贡献; 418项挖掘证实频次/时序类信号无预测力; "
                             "此前所谓'已剥夺出号权'只在文案层, 金胆权重2.5实为全系统最高, 本次真归零"},
        "aliases": ["lstm_deep", "lstm_top10"],
    },
    "datasource_1x2_hot": {
        "name": "数据源1×2 爆发 Top 5 (选号侧)", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "B2: 30期实测 Lift=0.96x 负贡献; docstring 宣称的 43%/1.72x 系编造, "
                             "全历史实测 23.85%/0.954 无一显著; 杀号侧另册保留"},
        "aliases": ["深层关联"],
    },
    "follow_track": {
        "name": "历史条件跟随 Top 5", "cohort": "legacy", "lane": "research",
        # 实际下线日 vs 决议记录日: 9-03 已停跑, 9-10 才把判决写进注册表
        "retired_since": "2026-09-03",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "E3: 实测 Lift 0.90x 跑输大盘, 已于流水线下线; 共现/跟随类信号全量挖掘证伪 (Lift 1.008)"},
    },
    "gemini_pick2": {
        "name": "Gemini 物理算子选2", "cohort": "legacy", "kind": "pick2", "lane": "research",
        "retired_since": "2026-09-03",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "E3: 质劣冗余副牌, 内置WF金胆 1.067x 自评最低档'观望', 已于流水线下线"},
        "pick2_baseline": 0.0607,
    },
    "pure_pool": {
        "name": "纯净池定胆 (冷号回补)", "cohort": "legacy", "lane": "research",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "历史黑名单延续: 纯净池信号无样本外优势"},
    },
    "spatial_points": {
        "name": "空间重点点位分析 Top 5", "cohort": "legacy", "lane": "research",
        "decree": {"status": "retired", "date": "2026-09-10",
                   "reason": "实测 Lift 0.96x 跑输大盘, 自评 278期 Lift=1.023 p=0.25 不显著, 已于流水线下线"},
    },

    # ── 门禁后上线的新模块 (registered, B3: 观察仓) ──
    "hidden_energy5": {
        "name": "Hidden Energy 5 首席特供", "cohort": "legacy", "lane": "daily",
        "decree": {"status": "retired", "date": "2026-11-12",
                   "reason": "2026-11-12 退役: 全量前瞻账 200票/41中 Lift=0.82x(单侧p=0.080), "
                             "30期 Lift=0.83x; B5 降级后仍未跑赢随机基线。引擎保留可复启"},
    },
    "prime_composite": {
        "name": "质合数与尾数香农熵推演", "cohort": "registered", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-10",
                   "reason": "B3: 2026-09-03 上线, 零样本外验证; 信号源(质合1.002/尾数1.015)已被全量挖掘证伪; "
                             "转观察仓, 自今日起记前瞻账, 满200期+FDR通过方可上票"},
        "preregistered": {
            "hypothesis": "质数考勤/尾数熵对下期号码有可复现选择力",
            "frozen_rule": "top5_prime_recommend 5码固定输出, 规则冻结于 2026-09-10",
            "since": "2026-09-10",
        },
    },
    "psychological_game": {
        "name": "心理博弈论逆向推演", "cohort": "registered", "lane": "daily",
        "decree": {"status": "observation", "date": "2026-09-10",
                   "reason": "B3: 2026-09-07 上线, 零样本外验证; 信号源(大小比/分区钟摆)已被证伪; "
                             "转观察仓, 自今日起记前瞻账"},
        "preregistered": {
            "hypothesis": "散户追热避冷的行为偏差可被逆向利用",
            "frozen_rule": "top5_assault 5码固定输出, 规则冻结于 2026-09-10",
            "since": "2026-09-10",
        },
    },

    # ── research 舱（日常票面默认折叠；nightly/rerun 需 --with-research）──
    # 2026-10-22 判决 (B6 精简整改)：以下 7 个研究舱模型整体判 retired ——
    #   ① 日常流水线默认不跑它们 (需 --with-research)，当期产物长期停在 2026274，
    #      每天在收割/研报里制造 7 行「产物目标期不符 / 无当期产物」噪声；
    #   ② 它们在册前瞻账实测全线跑输 (Lift 0.22x~1.00x，无一接近显著)；
    #   ③ 更实质的伤害：在册即进入跨模块 BH-FDR 校正族，虚增试验数 m，
    #      稀释所有真信号的 q 值 (trinity_top5 原始 p=0.014 被 35 元族压成 q=0.497)。
    #   代码/引擎/测试全部保留 (archive 前的观察资产)，只是退出记账与校正族。
    #   如需重启研究：--with-research 跑产物 + 撤本条判决即可重新入册。
    "genetic": {
        "name": "遗传算法", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 日常舱不产出当期票 (仅 --with-research)，前瞻账 Lift=0.889 (n=9, 样本不足); "
                             "在册只虚增 BH-FDR 试验数稀释真信号, 判退役; 引擎与测试保留可复启"},
    },
    "dtw": {
        "name": "DTW 动态时间规整", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=0.444 (n=12) 严重跑输大盘, 当期产物长期停更; 判退役, 引擎保留"},
    },
    "transformer": {
        "name": "Transformer 时序", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=1.000 (n=12) 与随机无异, 近12期实测 9.5% 命中率; 判退役, 引擎保留"},
    },
    "matrix_profile": {
        "name": "Matrix Profile", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=0.222 (n=12) 全系统最差 (近12期 4.8% 命中); 判退役, 引擎保留"},
    },
    "tda": {
        "name": "TDA 拓扑数据分析", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=1.000 (n=12) 与随机无异; 判退役, 引擎保留"},
    },
    "linear_algebra": {
        "name": "线性代数特征", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=0.667 (n=12) 跑输大盘; 判退役, 引擎保留"},
    },
    "random_forest": {
        "name": "随机森林", "cohort": "registered", "lane": "research",
        "retired_since": "2026-10-22",
        "decree": {"status": "retired", "date": "2026-10-22",
                   "reason": "B6: 前瞻账 Lift=0.889 (n=12) 跑输大盘; 判退役, 引擎保留"},
    },
    "error_correction": {
        "name": "残差改错预测", "cohort": "registered", "lane": "research",
        "decree": {"status": "retired", "date": "2026-11-12",
                   "reason": "2026-11-12 退役: 全量前瞻账 111票/20中 Lift=0.72x, 为全部活跃模块最低"
                             "(单侧p=0.052), 30期 Lift=0.69x; research 舱且 vote_weight=0。引擎保留可复启"},
    },
    "consensus_straddle": {
        "name": "三维交集共识定胆与选2冷热对冲", "cohort": "registered", "lane": "daily",
        "decree": {"status": "retired", "date": "2026-11-12",
                   "reason": "2026-11-12 补登记并退役: 全量前瞻账 190票/39中 Lift=0.82x(单侧p=0.088), "
                             "30期 Lift=0.80x。此前未登记注册表却持续计入 BH-FDR 检验族, 虚增试验数 m"},
    },
    "deep_assoc_blast5": {
        "name": "方案2 精选爆发 Top 5", "cohort": "registered", "lane": "daily",
        "decree": {"status": "retired", "date": "2026-11-12",
                   "reason": "2026-11-12 补登记并退役: 全量前瞻账 200票/43中 Lift=0.86x(单侧p=0.144), "
                             "30期 Lift=0.88x。此前未登记注册表却持续计入 BH-FDR 检验族, 虚增试验数 m"},
    },
    "unified_brain": {
        "name": "统一决策脑", "cohort": "registered", "lane": "research",
        "decree": {"status": "observation", "date": "2026-09-15",
                   "reason": "research 舱：不改主推来源"},
    },
}

# 共识投票池里 文件解析出来的展示名 -> 注册表 id
PICK_SOURCE_TO_ID = {
    "双层LSTM": "lstm",
    "定金选2": "gold_pick2",
    "点位反弹": "point_suppression",
    "顺口溜": "formula_jingle",
    "首席特供HE5": "hidden_energy5",
    "16期中热": "sixteen_hot",
    "深层关联": "datasource_1x2_hot",
}


def _wilson_lo(phat: float, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    z2 = z * z
    denom = 1.0 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return max(0.0, (center - margin) / denom)


def _one_sided_p(phat: float, p0: float, n: int) -> float:
    if n <= 0 or phat <= p0:
        return 1.0
    sd = math.sqrt(p0 * (1 - p0) / n)
    if sd <= 0:
        return 1.0
    z = (phat - p0) / sd
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def shrink_lift(lift: float, n_periods: int, n0: float = SHRINK_N0) -> float:
    """C2 赢家诅咒收缩: 把 Lift 往 1.0 拉, 样本越小拉得越狠。
    lift_shrunk = (n*lift + n0*1.0) / (n + n0)
    """
    if n_periods <= 0:
        return 1.0
    return (n_periods * lift + n0) / (n_periods + n0)


def _lift_30_from_detailed(
    mid: str,
    detailed_ledger: List[Dict[str, Any]],
    lb_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """近30窗 Lift：优先**权威前瞻账**，其次 master 详细账，最后才用全窗代理。

    2026-10-21 P1 缺陷修复 (Bug#10)：本函数原先只吃 `detailed_ledger`，
    而 master_reviewer 落盘时只留 10 条、且仅含 4 个有逐期明细的模块，
    导致生效条件 `n >= 20` 恒假 —— 「近30窗 Lift 塌陷即自动转观察仓」这道熔断
    从未真正触发过，100% 掉进 leaderboard_proxy（全窗平均），
    还把 n_30 伪造成 min(30, n) 让人误以为看了 30 期。
    现改为直接从权威前瞻账 (每模块每期都有真实 hits/total) 现算近 30 窗。
    """
    # ── 首选: 权威前瞻账 (paper_trading_modules.jsonl) ──
    try:
        rows = [r for r in _load_module_ledger()
                if r.get("module") == mid and r.get("actual") is not None and r.get("picks")]
        rows.sort(key=lambda x: str(x.get("period")))
        recent = rows[-30:]
        n = len(recent)
        if n >= 20:
            picks = sum(len(r["picks"]) for r in recent)
            hits = sum(int(r.get("hits") or 0) for r in recent)
            if picks > 0:
                lift30 = (hits / picks) / BASELINE if BASELINE else 1.0
                return {
                    "lift_30": round(lift30, 4),
                    "n_30": n,
                    "source": "module_ledger_last30",
                }
    except Exception:
        pass

    # ── 次选: master 详细账逐期明细 ──
    hits_list: List[float] = []
    totals: List[float] = []
    for entry in detailed_ledger or []:
        mods = entry.get("modules") or {}
        if mid not in mods:
            continue
        m = mods[mid] or {}
        if m.get("hits") is None:
            continue
        hits_list.append(float(m.get("hits") or 0))
        totals.append(float(m.get("total") or 0))
    hits_list = hits_list[-30:]
    totals = totals[-30:]
    n = len(hits_list)
    if n >= 20:
        avg_hits = sum(hits_list) / n
        avg_total = (sum(totals) / n) if totals else 5.0
        baseline = avg_total * (20.0 / 80.0)  # 随机基线命中期望
        lift30 = (avg_hits / baseline) if baseline > 0 else 1.0
        return {
            "lift_30": round(lift30, 4),
            "n_30": n,
            "source": "detailed_ledger",
        }
    # 代理分支的 n_30 必须如实回显真实可用期数(此处 0)，不得伪造成 30。
    if lb_row and int(lb_row.get("n_periods") or 0) >= 20:
        return {
            "lift_30": round(float(lb_row.get("lift") or 1.0), 4),
            "n_30": 0,
            "n_30_available": int(lb_row.get("n_periods") or 0),
            "source": "leaderboard_proxy_full_window",
            "note": "近30窗逐期明细不足20条，此处为全窗口平均 Lift 代理值，非最近30期表现",
        }
    return {"lift_30": None, "n_30": n, "source": None}


class ModuleGate:
    """模块投票注册表的唯一读写口"""

    def __init__(self, proj_dir: Optional[str] = None):
        self.proj_dir = proj_dir or _PROJ_DIR
        self.registry_file = REGISTRY_FILE if proj_dir is None else \
            os.path.join(proj_dir, "backend", "config", "module_vote_registry.json")
        self._reg = self._load()

    # ── 读 ──
    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # 无注册表文件: 用种子兜底 (未审计水印), 不阻塞流水线
        return self._seed_registry(evidence=None)

    def _seed_registry(self, evidence: Optional[Dict[str, Dict]]) -> Dict[str, Any]:
        modules = {}
        overrides = load_decree_overrides(self.proj_dir)
        for mid, seed in MODULE_SEED.items():
            decree = overrides.get(mid, seed["decree"])
            status = decree["status"]
            ev = (evidence or {}).get(mid)
            weight = self._compute_weight(mid, seed, status, ev)
            modules[mid] = {
                "id": mid,
                "name": seed["name"],
                "cohort": seed["cohort"],
                "lane": seed.get("lane", "daily"),
                "kind": seed.get("kind", "pick"),
                "status": status,
                "vote_weight": weight,
                "evidence": ev,
                "evidence_source": "live_master_review" if ev else "audit_20260910_seed(30期,未刷新)",
                "decree": decree,
                # 实际下线日与决议记录日是两件事: 模块可能 9-03 就停跑了, 9-10 审计才补判决。
                # 界面要显示的是"它从哪天起不在跑", 所以优先用 retired_since。
                "retired_since": seed.get("retired_since") or (decree.get("date") if status == "retired" else None),
                "preregistered": seed.get("preregistered"),
                "aliases": seed.get("aliases", []),
                "lift_30": None,
                "gate_reason": None,
                "watermark": None if ev else "⚠️ 注册表未经100期榜刷新, 权重为审计种子值",
            }
        return {
            "generated_at": datetime.now().isoformat(),
            "rules": {
                "new_module_gate": f"新模块须预注册+前瞻记账≥{MIN_PROSPECTIVE_PERIODS}期+BH-FDR(q<{FDR_ALPHA})且CI下界>1.0方可投票",
                "vote_weight_formula": "max(0, 收缩后Lift - 1.0), 收缩: (n*lift + 30)/(n+30)",
                "decree_floor": "判决层(retired/observation)为地板: live 证据只能进一步降级, 不能越过判决升级",
            },
            "modules": modules,
        }

    def _compute_weight(self, mid: str, seed: Dict, status: str, ev: Optional[Dict]) -> float:
        if status != "votable":
            return 0.0
        if ev and ev.get("n_periods", 0) > 0:
            lift_s = ev.get("lift_shrunk", 1.0)
            return round(max(0.0, lift_s - 1.0), 4)
        # 无 live 证据: 用审计种子 Lift 粗估 (带水印)
        return round(max(0.0, float(seed.get("seed_audit_lift", 1.0)) - 1.0), 4)

    # ── 对外查询 ──
    def get(self, module_id: str) -> Dict[str, Any]:
        m = self._reg.get("modules", {}).get(module_id)
        if m:
            return m
        # 未登记的模块: 按"未注册新模块"处理 —— 观察仓, 不许投票 (C6)
        return {
            "id": module_id, "name": module_id, "cohort": "unregistered",
            "status": "observation", "vote_weight": 0.0, "evidence": None,
            "decree": {"status": "observation", "date": "auto",
                       "reason": "未在注册表登记, 按 C6 门禁默认进观察仓"},
            "watermark": "未注册模块",
        }

    def status_of(self, module_id: str) -> str:
        return self.get(module_id).get("status", "observation")

    def vote_weight(self, module_id: str) -> float:
        """
        历史 Lift 派生值（审计/展示）。
        独立宪法 2026-09-11：禁止用于号码排序或模块间熔炉；出号请用 is_published + 单引擎产物。
        """
        import logging
        logging.getLogger(__name__).warning(
            f"DEPRECATED_FOR_SCORING: ModuleGate.vote_weight called for '{module_id}'. "
            "Under Independent Constitution, vote_weight is display-only and must NOT be used for scoring."
        )
        return self.audit_lift_weight(module_id)

    def audit_lift_weight(self, module_id: str) -> float:
        """只读审计权重 = max(0, 收缩Lift-1)；不驱动出号。"""
        return float(self.get(module_id).get("vote_weight", 0.0) or 0.0)

    def is_published(self, module_id: str) -> bool:
        """非 retired 即可上架陈列（观察仓也展示，但不进主推荐）。"""
        return self.status_of(module_id) != "retired"

    def is_votable(self, module_id: str) -> bool:
        """
        兼容旧调用。独立宪法下「votable」不再意味着参与加权投票，
        仅表示注册表状态仍为 votable（可用于徽章）；出号请勿依赖本方法。
        """
        m = self.get(module_id)
        return m.get("status") == "votable"

    def retired_ids(self) -> List[str]:
        """D3: 进化引擎的黑名单不再硬编码, 从这里读 (含别名展开)"""
        ids = []
        for mid, m in self._reg.get("modules", {}).items():
            if m.get("status") == "retired":
                ids.append(mid)
                ids.extend(m.get("aliases", []))
        return ids

    def observation_ids(self) -> List[str]:
        return [mid for mid, m in self._reg.get("modules", {}).items()
                if m.get("status") == "observation"]

    def registry(self) -> Dict[str, Any]:
        return self._reg

    # ── 每晚刷新: 由 100 期天梯榜 live 推导 ──
    def refresh_from_master_ledger(self, master_ledger: Optional[Dict] = None) -> Dict[str, Any]:
        """读 master_review_ledger.json, 重算各模块证据与权重, 落盘注册表。

        返回 (registry, changes): changes 记录状态/权重变化, 供 D4 展示真实 diff。
        """
        if master_ledger is None:
            master_ledger = {}
            if os.path.exists(MASTER_LEDGER_FILE):
                try:
                    with open(MASTER_LEDGER_FILE, "r", encoding="utf-8") as f:
                        master_ledger = json.load(f)
                except Exception:
                    master_ledger = {}

        lb = {m.get("id"): m for m in master_ledger.get("leaderboard", [])}
        detailed = master_ledger.get("detailed_ledger") or []
        prev = self._reg.get("modules", {})

        # 1) 汇总证据 (含 BH-FDR 跨模块校正)
        evidence: Dict[str, Dict] = {}
        p_map: Dict[str, float] = {}
        for mid in MODULE_SEED:
            row = lb.get(mid)
            if not row:
                continue
            n = int(row.get("n_periods") or 0)
            lift = float(row.get("lift") or 1.0)
            ci_lo = row.get("lift_ci_lo")
            p_val = row.get("p_value")
            evidence[mid] = {
                "n_periods": n,
                "lift": lift,
                "lift_shrunk": round(shrink_lift(lift, n), 4),
                "lift_ci_lo": ci_lo,
                "p_value": p_val,
                "insufficient": bool(row.get("insufficient", n < 100)),
            }
            if isinstance(p_val, (int, float)):
                p_map[mid] = float(p_val)

        # BH-FDR (C1 同款口径)
        if p_map:
            try:
                from core.multiple_testing import bh_fdr
                ids = list(p_map.keys())
                sig, qs = bh_fdr([p_map[i] for i in ids], alpha=FDR_ALPHA)
                for i, q, s in zip(ids, qs, sig):
                    evidence[i]["bh_q"] = round(q, 6)
                    evidence[i]["bh_significant"] = bool(s)
                    evidence[i]["significant"] = bool(
                        s and not evidence[i].get("insufficient")
                        and (evidence[i].get("lift_ci_lo") or 0) > 1.0)
            except Exception:
                pass

        # 2) 逐模块推导 status 与 weight (判决层为地板)
        modules: Dict[str, Any] = {}
        changes: List[str] = []
        overrides = load_decree_overrides(self.proj_dir)
        for mid, seed in MODULE_SEED.items():
            decree = overrides.get(mid, seed["decree"])
            ev = evidence.get(mid)
            old = prev.get(mid, {})
            lane = seed.get("lane", "daily")
            lift30_info = _lift_30_from_detailed(mid, detailed, lb.get(mid))
            lift_30 = lift30_info.get("lift_30")
            n_30 = int(lift30_info.get("n_30") or 0)

            status = decree["status"]
            auto_note = None
            gate_reason = None
            # decree override 仍优先：retired 不可被 live 升级；observation 判决可被进一步标注
            if status == "votable":
                # live 降级规则 (D3: 黑名单 live 化)
                if ev and ev.get("n_periods", 0) >= 60 and ev.get("lift_shrunk", 1.0) < 1.0:
                    status = "observation"
                    auto_note = (f"live 降级: 收缩后 Lift {ev['lift_shrunk']:.3f}<1.0 "
                                 f"(n={ev['n_periods']}), 自动转观察仓")
                    gate_reason = auto_note
                elif lift_30 is not None and n_30 >= 20 and float(lift_30) < 0.95:
                    status = "observation"
                    auto_note = (
                        f"last30 降级: lift_30={lift_30:.3f}<0.95 (n={n_30}), 自动转观察仓"
                    )
                    gate_reason = auto_note
                elif seed["cohort"] == "registered":
                    # C6: 新模块必须前瞻满 200 期且显著
                    prosp = module_ledger_count(mid)
                    if not (prosp >= MIN_PROSPECTIVE_PERIODS and ev and ev.get("significant")):
                        status = "observation"
                        auto_note = (f"C6 门禁: 前瞻账 {prosp}/{MIN_PROSPECTIVE_PERIODS} 期"
                                     f"{'且未达显著' if not (ev and ev.get('significant')) else ''}")
                        gate_reason = auto_note
            elif status == "observation" and decree.get("status") == "observation":
                gate_reason = decree.get("reason")
            elif status == "retired":
                gate_reason = decree.get("reason")

            if gate_reason is None and auto_note:
                gate_reason = auto_note

            weight = self._compute_weight(mid, seed, status, ev)
            modules[mid] = {
                "id": mid, "name": seed["name"], "cohort": seed["cohort"],
                "lane": lane,
                "kind": seed.get("kind", "pick"),
                "status": status, "vote_weight": weight,
                "evidence": ev,
                "evidence_source": "live_master_review" if ev else "audit_20260910_seed(30期,未刷新)",
                "decree": decree,
                "preregistered": seed.get("preregistered"),
                "aliases": seed.get("aliases", []),
                "auto_note": auto_note,
                "lift_30": lift_30,
                "n_30": n_30,
                "lift_30_source": lift30_info.get("source"),
                "gate_reason": gate_reason,
                "watermark": "样本不足100期" if (ev and ev.get("insufficient")) else
                             (None if ev else "⚠️ 注册表未经100期榜刷新, 权重为审计种子值"),
                "prospective_periods": module_ledger_count(mid),
            }
            if old.get("status") != status:
                changes.append(f"{seed['name']}: 状态 {old.get('status', '-') } → {status}")
            if old and abs(float(old.get("vote_weight", 0) or 0) - weight) > 1e-9:
                changes.append(f"{seed['name']}: 票权 {old.get('vote_weight')} → {weight}")

        reg = {
            "generated_at": datetime.now().isoformat(),
            "basis": "master_review_ledger.json(100期) + BH-FDR + 前瞻账 + last30 Lift",
            "rules": self._seed_registry(None)["rules"],
            "modules": modules,
        }
        os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        self._reg = reg
        return reg, changes


# ══════════════════════════════════════════════════════════════
#  C5: 全员独立前瞻账 (每模块一本账)
# ══════════════════════════════════════════════════════════════

def _load_module_ledger() -> List[Dict]:
    rows = []
    if os.path.exists(MODULE_LEDGER_FILE):
        with open(MODULE_LEDGER_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def _save_module_ledger(rows: List[Dict]):
    os.makedirs(os.path.dirname(MODULE_LEDGER_FILE), exist_ok=True)
    with open(MODULE_LEDGER_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def record_module_picks(target_period: int, picks_by_id: Dict[str, List[int]]):
    """开奖前: 把每个模块当期的前瞻号码记入账 (幂等: 同期同模块不重复)。"""
    rows = _load_module_ledger()
    existing = {(r["period"], r["module"]) for r in rows}
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    for mid, picks in picks_by_id.items():
        key = (str(target_period), mid)
        if key in existing or not picks:
            continue
        rows.append({
            "period": str(target_period), "module": mid, "timestamp": ts,
            "picks": [int(x) for x in picks],
            "actual": None, "hits": None,
        })
        added += 1
    if added:
        _save_module_ledger(rows)
    return added


def refresh_module_picks(target_period: int, picks_by_id: Dict[str, List[int]]) -> int:
    """显式重收: 覆盖同期同模块的旧账 (用于口径修正)。

    大白话: `record_module_picks` 是"先到先得", 一旦某模块某期记错口径, 后面再收也进不去。
    这个接口专门用来**显式点名**修正指定模块 —— 只删/重写被点名的 (期号, 模块), 其余账一行不动。
    开奖后已对账(actual 已填)的账禁止重写, 防止事后篡改历史战绩。
    """
    rows = _load_module_ledger()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refreshed = 0
    keep: List[Dict] = []
    for r in rows:
        mid = r.get("module")
        if str(r.get("period")) == str(target_period) and mid in picks_by_id:
            if r.get("actual") is not None:
                keep.append(r)  # 已开奖对账的账不许改
                continue
            continue  # 丢弃旧账, 下面重写
        keep.append(r)
    for mid, picks in picks_by_id.items():
        if not picks:
            continue
        keep.append({
            "period": str(target_period), "module": mid, "timestamp": ts,
            "picks": [int(x) for x in picks],
            "actual": None, "hits": None,
        })
        refreshed += 1
    if refreshed:
        _save_module_ledger(keep)
    return refreshed


def reconcile_module_ledger(limit_periods: int = 400) -> int:
    """开奖后: 把已开奖的账补上 actual/hits。返回新对账条数。"""
    hist = load_history(limit=limit_periods)
    actual_map = {str(h["issue"]): sorted(h["numbers"]) for h in hist}
    rows = _load_module_ledger()
    filled = 0
    for r in rows:
        if r.get("actual") is None and r["period"] in actual_map:
            actual = actual_map[r["period"]]
            r["actual"] = actual
            r["hits"] = len(set(r["picks"]) & set(actual))
            filled += 1
    if filled:
        _save_module_ledger(rows)
    return filled


def module_ledger_count(module_id: str) -> int:
    """该模块已开奖对账的前瞻账期数 (C6 门禁用)。"""
    return sum(1 for r in _load_module_ledger()
               if r["module"] == module_id and r.get("actual") is not None)


def module_ledger_report(min_n: int = 30) -> Dict[str, Any]:
    """C5: 每模块一本前瞻账的汇总 (走 wf_hit_engine 同口径: lift/CI/p/BH-FDR)。

    大白话: 每个模块单独记账, 各算各的命中率。已开奖的期数才算得进 Lift;
    还没开奖的只算"进度"。所以一个刚上线的模块会显示 0 期 + N 条待对账, 而不是凭空消失
    (凭空消失会让人误以为"没这个模块")。
    """
    from core.wf_hit_engine import evaluate_series, fdr_summarize
    rows = _load_module_ledger()

    by_mod: Dict[str, List[Dict]] = {}
    recorded: Dict[str, int] = {}
    pending: Dict[str, int] = {}
    for r in rows:
        mid = r.get("module")
        if not mid:
            continue
        recorded[mid] = recorded.get(mid, 0) + 1
        if r.get("actual") is None:
            pending[mid] = pending.get(mid, 0) + 1
            continue
        by_mod.setdefault(mid, []).append({
            "period": r["period"], "recommended": r["picks"], "actual": r["actual"],
        })

    evals = {}
    for mid, series in by_mod.items():
        series.sort(key=lambda x: x["period"])
        evals[mid] = evaluate_series(series, baseline=BASELINE, min_n=min_n)

    # 2026-10-21 P1 缺陷修复 (Bug#9 连带)：已退役模块不参与票权竞争，
    # 却一直被拉进跨模块 BH-FDR 检验族，虚增试验数 m 从而抬高所有真信号的 q 值。
    # 现把退役模块从 FDR 族中剔除（指标照常如实回显并标注 retired，但不参与校正族比较），
    # 使「过 BH-FDR」这个结论只由真正在册的模块之间比较得出。
    try:
        retired_in_ledger = set(ModuleGate().retired_ids())
    except Exception:
        retired_in_ledger = set()
    active_evals = {k: v for k, v in evals.items() if k not in retired_in_ledger}
    summary = fdr_summarize(active_evals) if active_evals else {"results": {}, "winning": []}

    out = {}
    for mid, ev in summary["results"].items():
        seed = MODULE_SEED.get(mid, {})
        out[mid] = {
            "name": seed.get("name", mid),
            "n_periods": ev["n_periods"],
            "total_picks": ev["total_picks"],
            "total_hits": ev["total_hits"],
            "pooled_rate": ev["pooled_rate"],
            "lift": ev["lift"],
            "lift_ci_lo": ev["lift_ci_lo"],
            "p_value": ev["p_value"],
            "bh_q": ev.get("bh_q"),
            # 2026-10-21 缺陷修复 (Bug#7)：`significant` 是**单模块未校正**的判据
            # (n≥min_n 且 CI下界>1 且 p≤α)，而展示层把它印成「✓FDR显著」，
            # 与同表已给出的 bh_q 自相矛盾 —— 实测 trinity_top5 原始 p=0.019 被判
            # 「FDR显著」，而跨 37 个模块做 BH 校正后 q=0.713 根本不显著。
            # 补一个显式的跨模块校正位，供展示层取用，杜绝再拿未校正当 FDR 结论。
            "significant": ev.get("significant", False),
            "raw_significant": bool(ev.get("significant", False)),
            "bh_significant": bool(ev.get("bh_significant", False)),
            "winner": bool(ev.get("winner", False)),
            "insufficient": ev.get("insufficient", True),
            "gate_progress": f"{ev['n_periods']}/{MIN_PROSPECTIVE_PERIODS}",
        }

    # 只在记账、还没到 min_n (甚至一条都还没开奖) 的模块也要露面, 否则页面上会凭空少人
    for mid in recorded:
        if mid in out:
            continue
        seed = MODULE_SEED.get(mid, {})
        # 2026-10-21 Bug#9 连带：退役模块已被剔出 FDR 校正族，但它的真实历史指标
        # 仍要如实露面并标 retired —— 不能因为不参与校正就把数字抹成 0 (那是另一种造假)。
        ev = evals.get(mid)
        if ev is not None:
            out[mid] = {
                "name": seed.get("name", mid),
                "n_periods": ev["n_periods"],
                "total_picks": ev["total_picks"],
                "total_hits": ev["total_hits"],
                "pooled_rate": ev["pooled_rate"],
                "lift": ev["lift"],
                "lift_ci_lo": ev["lift_ci_lo"],
                "p_value": ev["p_value"],
                "bh_q": None,
                "significant": False,
                "raw_significant": bool(ev.get("significant", False)),
                "bh_significant": False,
                "winner": False,
                "insufficient": ev.get("insufficient", True),
                "retired": True,
                "fdr_note": "已退役：不参与票权竞争，也不纳入 BH-FDR 校正族 (指标仅为历史留档)",
                "gate_progress": f"{ev['n_periods']}/{MIN_PROSPECTIVE_PERIODS}",
            }
            continue
        out[mid] = {
            "name": seed.get("name", mid),
            "n_periods": 0, "total_picks": 0, "total_hits": 0,
            "pooled_rate": None, "lift": None, "lift_ci_lo": None,
            "p_value": None, "bh_q": None,
            "significant": False, "insufficient": True,
            "gate_progress": f"0/{MIN_PROSPECTIVE_PERIODS}",
        }

    # 在册模块统一补 retired=False，供展示层区分「未过校正」与「不参与校正」
    for mid, info in out.items():
        info.setdefault("retired", mid in retired_in_ledger)
        if info.get("retired") and mid in summary["results"]:
            info["fdr_note"] = "已退役：不参与票权竞争，也不纳入 BH-FDR 校正族"

    # 校正族规模如实回显：q 值是按多少个模块校正出来的，不能是黑箱
    summary["fdr_family_size"] = len(active_evals)
    summary["fdr_excluded_retired"] = sorted(
        k for k in evals if k in retired_in_ledger)

    for mid, info in out.items():
        info["recorded"] = recorded.get(mid, 0)
        info["pending"] = pending.get(mid, 0)

    return {
        "generated_at": datetime.now().isoformat(),
        "baseline": BASELINE,
        "gate_rule": f"前瞻≥{MIN_PROSPECTIVE_PERIODS}期 且 BH-FDR 显著 且 CI下界>1.0 → 方可申请票权",
        # 校正族规模透明化：q 值是由多少个在册模块相互比较校正出来的
        "fdr_family_size": len(active_evals),
        "fdr_excluded_retired": sorted(k for k in evals if k in retired_in_ledger),
        "modules": out,
    }



if __name__ == "__main__":
    gate = ModuleGate()
    reg, changes = gate.refresh_from_master_ledger()
    print(f"注册表已刷新: {len(reg['modules'])} 个模块")
    for c in changes:
        print("  Δ", c)
    for mid, m in reg["modules"].items():
        print(f"  {mid:24s} {m['status']:11s} w={m['vote_weight']:.3f} "
              f"ev={m['evidence']['lift_shrunk'] if m.get('evidence') else '-'}")
