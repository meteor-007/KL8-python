# -*- coding: utf-8 -*-
"""
evolution_engine.py — 快乐8 纯物理共振与门禁自进化引擎 (Zero-Weight Resonance & Gatekeeper Evolution Engine)
=======================================================================================================
【彻底废除人造权重比分配，回归纯粹物理量化本质】：
  1. 废除所谓的 "0.15/0.20 小数权重加权"：各子系统各司其职，靠物理共振，不靠加权切片。
  2. 进化子系统【准入白名单 (Admission Gate)】：
     - 实战 Lift >= 1.0 (胜率超越随机基线) 的系统获得【举手资格 (Active)】；
     - 胜率低于随机基线的系统被【一票静音 (Muted)】，杜绝平庸团队稀释信号！
  3. 进化【物理共振门禁阈值 (Resonance Threshold)】：
     - 顺风爆发期: 2 路独立物理系统点亮即放行；
     - 混沌震荡期: 必须 3 路以上独立物理系统点亮才放行金胆 (收紧门禁防洗盘)！
  4. 进化【防守杀号硬拦截边界 (Defense Kill Scope)】：
     - 动态收放杀号池规模 (10~20码)，实施 0/1 硬拦截一票否决。
  5. 记录进化代数 (Generation N) 与传承总账本。
"""
from backend.utils.paths import get_outputs_dir
import os
import sys
import json
import math
from datetime import datetime
from typing import Dict, List, Any, Optional, Set

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import data_path, get_project_root
from core.master_reviewer import MasterReviewEngine

EVOLUTION_DIR = os.path.join(_PROJ_DIR, "storage", "evolution")
os.makedirs(EVOLUTION_DIR, exist_ok=True)
EVOLUTION_LEDGER_FILE = os.path.join(EVOLUTION_DIR, "evolution_ledger.json")
EVOLUTION_STATE_FILE = os.path.join(_PROJ_DIR, "backend", "config", "evolution_state.json")


class MetaEvolutionEngine:
    """
    纯物理共振与门禁自进化引擎 (无权重架构)
    """
    def __init__(self, proj_dir: str = None):
        self.proj_dir = proj_dir or _PROJ_DIR
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(EVOLUTION_STATE_FILE):
            try:
                with open(EVOLUTION_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "generation": 1,
            "architecture": "Zero-Weight Pure Resonance & Hard Gate Pipeline",
            "last_evolved": datetime.now().isoformat(),
            "target_period": 2026234,
            "resonance_threshold": 2,          # 至少几路独立物理系统点亮才算金胆共振 (2~3)
            "min_lift_admission": 1.0,         # 准入基线 Lift 门槛
            "active_subsystems": [             # 获得举手资格的白名单系统
                "trinity_top5", "hidden_energy5", "datasource_1x2_hot", 
                "formula_jingle", "spatial_points", "sixteen_hot", "point_suppression"
            ],
            "muted_subsystems": ["pure_pool"], # 处于休眠观察期的系统 (Lift < 1.0)
            "kill_defense_size": 15,           # 硬防守拦截杀号池深度
            "evolution_history": [],
            "status": "ZERO_WEIGHT_OPTIMAL"
        }

    def _save_state(self):
        try:
            with open(EVOLUTION_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存进化状态失败: {e}")

    def run_evolution(self, n_review: int = 100) -> Dict[str, Any]:
        """执行一次无权重纯物理门禁自进化

        B5/D3/D4 整改 (2026-09-10):
          - 退役/观察仓名单不再硬编码, 由 module_gate 注册表 live 读取 (D3);
          - "一级共振决议权"改为统计显著性授予: n≥100期 且 BH-FDR 显著 且 收缩后Lift≥1.25 (B5);
          - 记录与上一代的真实参数差异 params_changed (D4: 不再只涨代数不改参数);
          - 清理 meta_weights/trinity_3d/fitness_history 死字段。
        """
        reviewer = MasterReviewEngine(self.proj_dir)
        review_res = reviewer.run_master_review(n_review=n_review)
        leaderboard = review_res.get("leaderboard", [])

        if not leaderboard:
            return {"status": "error", "message": "未能获取复盘数据，进化中止"}

        # D4: 记录上一代参数快照, 用于真实 diff
        prev_state = {
            "resonance_threshold": self.state.get("resonance_threshold"),
            "kill_defense_size": self.state.get("kill_defense_size"),
            "active_subsystems": list(self.state.get("active_subsystems", [])),
            "muted_subsystems": list(self.state.get("muted_subsystems", [])),
        }

        current_gen = self.state.get("generation", 1)
        next_gen = current_gen + 1

        # 目标研判期永远锚定当前最新开奖期号 + 1 (防错位防滞后)
        from utils.history_loader import load_history
        _latest_hist = load_history(limit=1)
        if _latest_hist and "issue" in _latest_hist[0]:
            target_period = int(_latest_hist[0]["issue"]) + 1
        else:
            target_period = review_res.get("target_period", 2026236) + 1

        active_list = []
        muted_list = []
        observation_list = []
        rationales = []

        # D3: 黑名单/观察仓由 module_gate 注册表 live 驱动, 不再硬编码
        try:
            from core.module_gate import ModuleGate
            _gate = ModuleGate(self.proj_dir)
            DISCARDED_SUBSYSTEMS = set(_gate.retired_ids())
            OBSERVATION_SUBSYSTEMS = set(_gate.observation_ids())
        except Exception:
            DISCARDED_SUBSYSTEMS = {
                "pure_pool", "follow_track", "spatial_points", "gemini_pick2",
                "lstm_deep", "lstm_top10", "lstm", "datasource_1x2_hot"
            }
            OBSERVATION_SUBSYSTEMS = {"hidden_energy5", "prime_composite", "psychological_game"}

        # B5: "一级共振决议权"的统计门槛
        def _is_super_beacon(m: Dict[str, Any]) -> bool:
            return (not m.get("insufficient", True)
                    and (m.get("p_value") or 1.0) <= 0.05
                    and m.get("lift_shrunk", m.get("lift", 0.0)) >= 1.25)

        # 1. 评估各模块是否具备【准入资格】
        # 坚决废除权重加权，只做 0/1 准入准出; 评级一律用收缩后 Lift
        for m in leaderboard:
            mod_id = m.get("id")
            name = m.get("name")
            lift_raw = m.get("lift", 1.0)
            lift_s = m.get("lift_shrunk", lift_raw)
            mtype = m.get("type", "pick_set")
            n_p = m.get("n_periods", 0)

            if mod_id in DISCARDED_SUBSYSTEMS:
                # 退役: 人类判决层, 数据再好也不自动复活
                continue
            if mod_id in OBSERVATION_SUBSYSTEMS:
                # 观察仓: 记账不表决 (B3/B5)
                observation_list.append(mod_id)
                rationales.append(
                    f"🔭 【{name}】观察仓: 实测 Lift={lift_raw:.2f}x (收缩 {lift_s:.2f}x, n={n_p})，"
                    f"小样本未证显著，撤销决议权，继续记账观察。")
                continue

            if mtype == "pick_set" or mtype == "pick2_pair":
                if lift_s >= 1.0:
                    active_list.append(mod_id)
                    if _is_super_beacon(m):
                        rationales.append(
                            f"🟢 【{name}】实测 Lift={lift_raw:.2f}x (收缩 {lift_s:.2f}x, "
                            f"n={n_p}, p={m.get('p_value', 1):.4f})【统计显著】，授予【一级共振决议权】。")
                    else:
                        _why = "样本不足100期" if m.get("insufficient", True) else f"未证显著 (p={m.get('p_value', 1):.3f})"
                        rationales.append(
                            f"🟡 【{name}】实测 Lift={lift_raw:.2f}x (收缩 {lift_s:.2f}x, n={n_p})，"
                            f"{_why}，保留【共振表决权】但不得授予一级决议权。")
                else:
                    muted_list.append(mod_id)
                    rationales.append(
                        f"🔴 【{name}】实测 Lift={lift_raw:.2f}x (收缩 {lift_s:.2f}x, n={n_p}) 落后基线，"
                        f"触发【一票静音机制】，本代自动休眠！")

        # 2. 自进化共振门禁阈值 (Resonance Gate Threshold)
        # B5: "顺风爆发"只数统计显著的超强信标, 不再数原始 Lift≥1.20 的小样本噪声
        super_beacons = sum(1 for m in leaderboard
                            if _is_super_beacon(m)
                            and m.get("id") not in DISCARDED_SUBSYSTEMS
                            and m.get("id") not in OBSERVATION_SUBSYSTEMS)

        if super_beacons >= 3:
            new_threshold = 2
            rationales.append("🔥 大盘处于强信号顺风期 (3+路子系统统计显著爆发)，共振门禁设定为【2路物理共振】即锁定金胆。")
        else:
            new_threshold = 3
            rationales.append("🛡️ 大盘未达统计显著顺风 (超强信标<3路)，门禁维持【3路及以上共振】才准出票，坚决防洗盘。")

        # 3. 自进化防守杀号池规模
        kill_modules = [m for m in leaderboard if m.get("type") == "kill_set"]
        if kill_modules and kill_modules[0].get("kill_accuracy", 75.0) >= 78.0:
            new_kill_size = 18
            rationales.append("🛡️ 杀号引擎回避率高达 78%+，动态扩张防守杀号硬拦截池至【18码一票否决】。")
        else:
            new_kill_size = 14
            rationales.append("🛡️ 杀号引擎维持标准防守拦截池【14码一票否决】。")

        # D4: 真实参数差异
        params_changed = []
        if prev_state["resonance_threshold"] != new_threshold:
            params_changed.append(f"共振门禁 {prev_state['resonance_threshold']} → {new_threshold}")
        if prev_state["kill_defense_size"] != new_kill_size:
            params_changed.append(f"杀号池 {prev_state['kill_defense_size']}码 → {new_kill_size}码")
        added_mods = sorted(set(active_list) - set(prev_state["active_subsystems"]))
        removed_mods = sorted(set(prev_state["active_subsystems"]) - set(active_list))
        if added_mods:
            params_changed.append(f"新准入: {', '.join(added_mods)}")
        if removed_mods:
            params_changed.append(f"退出表决: {', '.join(removed_mods)}")
        if not params_changed:
            params_changed.append("门禁参数与上一代完全一致 (阈值/杀号池/表决名单均未变化)")

        # 4. 构建无权重自进化记录
        evolution_record = {
            "generation": next_gen,
            "architecture": "Zero-Weight Pure Resonance & Hard Gate Pipeline",
            "evolved_at": datetime.now().isoformat(),
            "target_period": target_period,
            "n_reviewed": n_review,
            "resonance_threshold": new_threshold,
            "active_subsystems": active_list,
            "muted_subsystems": muted_list,
            "observation_subsystems": observation_list,
            "kill_defense_size": new_kill_size,
            "rationales": rationales,
            "params_changed": params_changed,
            "generation_meaning": "门禁迭代计数 (非参数学习; 自学习调参由 learning_gate 门控, 当前冻结)",
            "design_principle": "彻底断绝人造权重加权比，采用多维拓扑物理共振与硬门禁拦截",
            "status": "ZERO_WEIGHT_EVOLUTION_SUCCESS"
        }

        # 更新状态 (D3: 清理 meta_weights/trinity_3d/fitness_history 死字段)
        self.state.pop("meta_weights", None)
        self.state.pop("trinity_3d", None)
        self.state.pop("fitness_history", None)
        self.state["generation"] = next_gen
        self.state["last_evolved"] = evolution_record["evolved_at"]
        self.state["target_period"] = target_period
        self.state["resonance_threshold"] = new_threshold
        self.state["active_subsystems"] = active_list
        self.state["muted_subsystems"] = muted_list
        self.state["observation_subsystems"] = observation_list
        self.state["kill_defense_size"] = new_kill_size
        self.state["rationales"] = rationales
        self.state["params_changed"] = params_changed
        self.state["learning_gate_note"] = "权重学习效率由 learning_gate 独立门控; 当前 197折WF的CI下界<1.0, 调参冻结, 本引擎只做门禁准入"
        self._save_state()

        # 归档总账本
        self._append_evolution_ledger(evolution_record)
        self._generate_evolution_report_md(evolution_record)

        return evolution_record

    def _append_evolution_ledger(self, record: Dict[str, Any]):
        ledger = []
        if os.path.exists(EVOLUTION_LEDGER_FILE):
            try:
                with open(EVOLUTION_LEDGER_FILE, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []
        target_p = record.get("target_period")
        updated = False
        if target_p is not None:
            for idx, item in enumerate(ledger):
                if item.get("target_period") == target_p:
                    ledger[idx] = record
                    updated = True
                    break
        if not updated:
            ledger.append(record)
        if len(ledger) > 100:
            ledger = ledger[-100:]
        try:
            with open(EVOLUTION_LEDGER_FILE, "w", encoding="utf-8") as f:
                json.dump(ledger, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存进化总账本失败: {e}")

    def _generate_evolution_report_md(self, rec: Dict[str, Any]):
        out_dir = os.path.join(get_outputs_dir(), "reports")
        os.makedirs(out_dir, exist_ok=True)
        report_file = os.path.join(out_dir, "evolution_report_latest.md")

        lines = [
            f"# 🧬 快乐8 纯物理共振门禁模型第 {rec['generation']} 次迭代报告",
            f"> 目标期号: {rec.get('target_period')} | 演进时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 架构模式: **无权重 · 纯门禁准入流水线**",
            "> ⚠️ 语义说明: 本'代数'是门禁准入的迭代计数，**不是参数学习代数**；权重学习由 learning_gate 独立门控（当前冻结）。",
            "",
            "## 🔧 0. 本次迭代真实参数变化 (D4)",
        ]
        for pc in rec.get("params_changed", ["无记录"]):
            lines.append(f"- {pc}")
        lines.extend([
            "",
            "## 🎯 1. 为什么坚决废除“权重比分配”？(底层设计原理)",
            "- **拒绝虚假精度**: 0.15 还是 0.18 的加权乘法没有任何物理依据，反而会把极其精准的金胆信号稀释成温水；",
            "- **专业分工各司其职**: 定胆由物理共振定、搭档由连体婴顺藤摸瓜带、防守由杀号一票否决，不再搞大杂烩加权！",
            "- **多维物理共振**: 只有当多路完全独立的物理系统（时序、空间、能量场、口诀）同时点亮同一个号码时，才是真金胆！",
            "",
            "## ⚖️ 2. 本代自进化物理门禁决策 (大白话)",
        ])
        for r in rec.get("rationales", []):
            lines.append(f"- {r}")

        lines.extend([
            "",
            "## 🗳️ 3. 子系统准入名单与状态 (0/1 准入机制, 名单由 module_gate 注册表驱动)",
            "| 状态分类 | 包含子系统 | 判定标准 | 权限 |",
            "| :--- | :--- | :--- | :---: |",
            f"| 🟢 **准入名单 (Active)** | `{', '.join(rec.get('active_subsystems', []))}` | 近100期收缩后 Lift $\\ge 1.0$ | **参与共振表决** |",
            f"| 🔴 **静音冷宫 (Muted)** | `{', '.join(rec.get('muted_subsystems', [])) if rec.get('muted_subsystems') else '无'}` | 收缩后 Lift $< 1.0$ 落后基准 | **一票休眠** |",
            f"| 🔭 **观察仓 (Observation)** | `{', '.join(rec.get('observation_subsystems', [])) if rec.get('observation_subsystems') else '无'}` | 新模块/小样本未证显著 (B3/B5) | **记账不表决** |",
            f"| ⛔ **已退役 (Retired)** | 见 module_vote_registry.json | 审计判决 (负贡献/已证伪) | **永久不表决** |",
            "",
            "> 📌 '一级共振决议权'自 2026-09-10 起改为统计授予：须 n≥100期 且 BH-FDR 显著 且 收缩后 Lift≥1.25x；小样本高 Lift 一律按噪声处理。",
            "",
            f"**当前物理共振门禁**: `≥ {rec.get('resonance_threshold')} 路独立点亮` | **硬拦截杀号池**: `{rec.get('kill_defense_size')} 码一票否决`",
        ])

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            pass


def print_evolution_table(rec: Dict[str, Any]):
    print("\n" + "=" * 80)
    print(f"  🧬 快乐8 纯物理共振门禁模型第 {rec['generation']} 次门禁迭代 (Zero-Weight Pipeline)")
    print("  ⚠️ 注意: 此为门禁准入迭代计数, 非参数学习代数; 权重学习由 learning_gate 门控")
    print("=" * 80)
    print(f"  🎯 目标期号: {rec.get('target_period')} | 核心设计: 彻底废除权重比，采用纯物理共振与门禁")
    print("-" * 80)
    print("  🔧 本次迭代真实参数变化:")
    for pc in rec.get("params_changed", ["无记录"]):
        print(f"    · {pc}")
    print("-" * 80)
    print("  💡 本代门禁决策:")
    for r in rec.get("rationales", []):
        print(f"    · {r}")
    print("-" * 80)
    print(f"  🟢 准入名单 ({len(rec.get('active_subsystems', []))}路): {', '.join(rec.get('active_subsystems', []))}")
    print(f"  🔴 静音休眠区 ({len(rec.get('muted_subsystems', []))}路): {', '.join(rec.get('muted_subsystems', [])) if rec.get('muted_subsystems') else '无'}")
    print(f"  🔭 观察仓 ({len(rec.get('observation_subsystems', []))}路): {', '.join(rec.get('observation_subsystems', [])) if rec.get('observation_subsystems') else '无'}")
    print(f"  ⚡ 物理共振门禁: ≥ {rec.get('resonance_threshold')} 路独立系统点亮 ➔ 判定为核心金胆")
    print(f"  🛡️ 防守硬拦截池: {rec.get('kill_defense_size')} 码一票否决")
    print("=" * 80 + "\n")
