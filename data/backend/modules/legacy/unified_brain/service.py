# -*- coding: utf-8 -*-
"""UnifiedBrainServiceMixin: methods extracted from QuantDataService"""
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


class UnifiedBrainServiceMixin:
    def get_evolution_status(self) -> Dict[str, Any]:
        """获取元学习自动进化模型当前代数、各模块元权重与三维参数，以及对下一期预测的实操因果影响"""
        try:
            from backend.core.evolution_engine import MetaEvolutionEngine
            engine = MetaEvolutionEngine(self.proj_dir)
            state_data = dict(engine.state)
            
            # 保证 rationales 100% 不为空 (若 state 缺少则从总账本最新笔回溯)
            if not state_data.get("rationales"):
                ledger_file = os.path.join(self.proj_dir, "storage", "evolution", "evolution_ledger.json")
                if os.path.exists(ledger_file):
                    try:
                        with open(ledger_file, "r", encoding="utf-8") as lf:
                            records = json.load(lf)
                            if records and isinstance(records, list) and len(records) > 0:
                                state_data["rationales"] = records[-1].get("rationales", [])
                    except Exception:
                        pass
            
            # 结构化注入【自进化如何直接决定今日预测出号】大白话因果影响
            thresh = state_data.get("resonance_threshold", 3)
            kill_sz = state_data.get("kill_defense_size", 14)
            muted = state_data.get("muted_subsystems", ["pure_pool"])
            active = state_data.get("active_subsystems", [])

            # ── D4 整改 (2026-09-10): 代数说人话 + 真实参数差异 + 学习状态 ──
            # 1) "代数"= 门禁迭代计数, 不是参数学习代数 (自学习被门控冻结)
            state_data["generation_meaning"] = state_data.get(
                "generation_meaning",
                "门禁迭代计数 (非参数学习; 自学习调参由 learning_gate 门控, 当前冻结)")
            # 2) 本代真实参数变化 (优先取 state, 缺失则对比 ledger 末两条)
            last_param_diff = state_data.get("params_changed")
            if not last_param_diff:
                try:
                    ledger_file = os.path.join(self.proj_dir, "storage", "evolution", "evolution_ledger.json")
                    with open(ledger_file, "r", encoding="utf-8") as lf:
                        recs = json.load(lf) or []
                    if len(recs) >= 2:
                        cur, prev = recs[-1], recs[-2]
                        diff = []
                        if cur.get("resonance_threshold") != prev.get("resonance_threshold"):
                            diff.append(f"共振门禁 {prev.get('resonance_threshold')} → {cur.get('resonance_threshold')}")
                        if cur.get("kill_defense_size") != prev.get("kill_defense_size"):
                            diff.append(f"杀号池 {prev.get('kill_defense_size')}码 → {cur.get('kill_defense_size')}码")
                        _a = sorted(set(cur.get("active_subsystems", [])) - set(prev.get("active_subsystems", [])))
                        _r = sorted(set(prev.get("active_subsystems", [])) - set(cur.get("active_subsystems", [])))
                        if _a:
                            diff.append(f"新准入: {', '.join(_a)}")
                        if _r:
                            diff.append(f"退出表决: {', '.join(_r)}")
                        last_param_diff = diff or ["门禁参数与上一代完全一致 (阈值/杀号池/表决名单均未变化)"]
                    elif len(recs) == 1:
                        last_param_diff = ["首代记录, 无上一代可比对"]
                except Exception:
                    last_param_diff = []
            state_data["last_param_diff"] = last_param_diff or ["无记录"]

            # 3) 自学习状态显式化 (锁定 vs 在学)
            _learn_status, _learn_note = "unknown", ""
            try:
                from backend.core.learning_gate import is_learning_enabled, gate_status
                _enabled = is_learning_enabled()
                _learn_status = "active" if _enabled else "frozen"
                _gs = gate_status() or {}
                _learn_note = (f"自学习调参: {'开启' if _enabled else '冻结中'} "
                               f"(WF 95%CI 下界={_gs.get('last_wf_ci_lo', _gs.get('last_wf_lift'))}, "
                               f"阈值={_gs.get('lift_threshold', 1.0)})")
            except Exception:
                _learn_note = "自学习门控状态读取失败"
            state_data["learning_status"] = _learn_status
            state_data["learning_status_note"] = _learn_note
            # 4) 偏差/Platt 是否在动 (冻结时它们只是"待命", 不许假装在学)
            try:
                # 2026-11-10：AutonomousLearner 已退役且其状态文件已归档。
                # 这里只需要读两个 Platt 参数做状态展示 —— 直接读文件即可，
                # 绝不能再实例化（实例化会 _ensure_defaults + _save_state，
                # 在缓存目录里凭空重建一个学习状态文件）。
                from backend.utils.paths import get_cache_dir
                _sf = os.path.join(get_cache_dir(), 'learner_state.json')
                _st = {}
                if os.path.exists(_sf):
                    try:
                        with open(_sf, 'r', encoding='utf-8') as _f:
                            _st = json.load(_f) or {}
                    except Exception:
                        _st = {}
                state_data["number_bias_status"] = {
                    "active": _learn_status == "active",
                    "note": ("偏差校准在跑" if _learn_status == "active"
                             else "偏差未激活 (门控冻结, 代码在位但不更新)"),
                    "platt_a": _st.get("platt_a"), "platt_b": _st.get("platt_b"),
                }
            except Exception:
                pass

            muted_names_map = {"pure_pool": "纯净池定胆 (冷号回补)"}
            muted_str = "、".join([muted_names_map.get(m, m) for m in muted]) if muted else "暂无"

            state_data["prediction_impact"] = {
                "resonance_summary": f"门禁收紧为【≥ {thresh} 路共振】",
                "resonance_detail": f"今日只有被 {thresh} 个及以上实战达标专家同时举手点亮的号码才准进入金胆/主力突击池，过滤掉噪音假突破。",
                "kill_summary": f"硬防守拦截【{kill_sz} 码一票否决】",
                "kill_detail": f"防守雷区已将 {kill_sz} 个冷寂/险恶号码能量打入负无穷，任凭单项指标怎么吹也绝不出票，守住防守基本盘。",
                "whitelist_summary": f"【{len(active)} 席】专家表决，【{muted_str}】一票静音",
                "whitelist_detail": f"实测胜率落后随机基线的【{muted_str}】已被系统一票否决打入冷宫，今日所有出号决策完全屏蔽其干扰，只听胜率超标专家表决。",
                # D4: 原此处硬编码"时序半衰记忆率升至 0.95 (重号追涨模式)"——该数值并无当日计算出处,
                # 属与审计同类的"假数字", 现改为如实说明这是静态配置而非进化产物。
                "momentum_summary": "时序半衰记忆率 (静态配置, 非自进化产物)",
                "momentum_detail": "该参数由配置文件决定, 不随门禁迭代变动; 门禁迭代只决定'谁能投票、共振几路放行、杀几码'。"
            }

            return {"status": "ok", "data": state_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_evolution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取每日夜间流水线与模型自进化历史记录 (倒序排列)
        
        @param limit 最大返回记录数
        @return 格式化后的每日执行与进化历史列表
        """
        ledger_file = os.path.join(self.proj_dir, "storage", "evolution", "evolution_ledger.json")
        if not os.path.exists(ledger_file):
            return []

        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            
            if not isinstance(raw_list, list):
                return []

            module_names = {
                "trinity_top5": "Trinity Top 5",
                "trinity_top12": "Trinity Top 12",
                "hidden_energy5": "Hidden Energy 5 (首席特供)",
                "datasource_1x2_hot": "数据源1×2 爆发码",
                "formula_jingle": "顺口溜口诀",
                "spatial_points": "重点点位分析",
                "sixteen_hot": "16期中热",
                "point_suppression": "点位高压反弹",
                "aggregation_stable10": "终审稳健 Top 10",
                "pure_pool": "纯净池定胆 (冷号)",
                "follow_track": "条件跟随",
                "lstm_deep": "双层LSTM时序"
            }

            formatted = []
            for item in raw_list:
                raw_time = item.get("evolved_at", "")
                dt_str = raw_time.replace("T", " ")[:19] if raw_time else "未知时间"
                
                # 判断触发方式 (21:55 ~ 22:15 视为夜间定时自动执行)
                trigger_type = "⚡ 手动立即执行"
                trigger_badge = "manual"
                if raw_time and len(raw_time) >= 16:
                    try:
                        time_part = raw_time.split("T")[1][:5]
                        hour, minute = [int(x) for x in time_part.split(":")]
                        if (hour == 21 and minute >= 55) or (hour == 22 and minute <= 15):
                            trigger_type = "⏰ 22:00 夜间定时"
                            trigger_badge = "scheduled"
                    except Exception:
                        pass

                actives = item.get("active_subsystems", [])
                muted = item.get("muted_subsystems", [])
                active_display = [module_names.get(m, m) for m in actives]
                muted_display = [module_names.get(m, m) for m in muted]
                
                rationales = item.get("rationales", [])
                summary_rationale = rationales[0] if rationales else "正常多维物理共振解算完成"

                status_code = item.get("status", "SUCCESS")
                status_ok = "SUCCESS" in status_code.upper() or "OK" in status_code.upper()

                target_period_val = str(item.get("target_period", "N/A"))
                last_drawn_val = str(item.get("last_drawn_period", ""))
                if not last_drawn_val and target_period_val.isdigit():
                    last_drawn_val = str(int(target_period_val) - 1)

                formatted.append({
                    "generation": item.get("generation", 1),
                    "evolved_at": dt_str,
                    "last_drawn_period": last_drawn_val,
                    "last_drawn_date": item.get("last_drawn_date", dt_str.split(" ")[0]),
                    "target_period": target_period_val,
                    "target_date": item.get("target_date", "次日"),
                    "target_display": item.get("target_display", f"第 {target_period_val} 期"),
                    "architecture": item.get("architecture", "纯物理共振门禁架构"),
                    "trigger_type": trigger_type,
                    "trigger_badge": trigger_badge,
                    "status": "SUCCESS" if status_ok else "FAILED",
                    "status_label": "✅ 执行圆满成功" if status_ok else "❌ 执行异常",
                    "resonance_threshold": item.get("resonance_threshold", 3),
                    "kill_defense_size": item.get("kill_defense_size", 14),
                    "active_subsystems": actives,
                    "active_display": active_display,
                    "active_count": len(actives),
                    "muted_subsystems": muted,
                    "muted_display": muted_display,
                    "muted_count": len(muted),
                    "rationales": rationales,
                    "summary_rationale": summary_rationale,
                    "n_reviewed": item.get("n_reviewed", 30)
                })

            # 倒序排列：最新的在最前
            formatted.reverse()
            return formatted[:limit]
        except Exception as e:
            return []

    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取 22:00 夜间调度器实时状态与倒计时"""
        try:
            from backend.scheduler.nightly_scheduler import scheduler_instance
            return scheduler_instance.get_status()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_unified_brain_latest(self) -> Dict[str, Any]:
        """
        获取全栈统一决策主脑最新推演结果 (尖刀金胆、黄金选2、最优3码等)
        优先读取 outputs/unified_brain 下最新的 unified_decision_*.json 文件；
        若文件不存在或读取失败，则自动启动 UnifiedDecisionBrain 进行实时推演解算并返回。
        
        @return 统一决策主脑数据字典
        """
        brain_dir = os.path.join(get_outputs_dir(), "unified_brain")
        os.makedirs(brain_dir, exist_ok=True)

        # 步骤 1: 扫描 outputs/unified_brain 下所有标准解算资产
        decision_files = []
        if os.path.exists(brain_dir):
            for fname in os.listdir(brain_dir):
                if fname.startswith("unified_decision_") and fname.endswith(".json") and not fname.startswith("unified_decision_report"):
                    m = re.search(r"unified_decision_(\d+)\.json", fname)
                    if m:
                        period_int = int(m.group(1))
                        fpath = os.path.join(brain_dir, fname)
                        mtime = os.path.getmtime(fpath)
                        decision_files.append((period_int, mtime, fpath))

        # 降序排列取期号与修改时间最新的一笔（过滤单测合成数据）
        if decision_files:
            decision_files.sort(key=lambda x: (x[0], x[1]), reverse=True)
            for period_int, _, fpath in decision_files:
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        cached_data = json.load(fp)
                        # 跳过虚构单测文件
                        if cached_data.get("meta_info", {}).get("test_synthetic"):
                            continue
                        return {
                            "status": "ok",
                            "source": "cache",
                            "period": period_int,
                            "data": cached_data
                        }
                except Exception as read_err:
                    logger.warning(f"读取统一决策主脑缓存失败 ({fpath}): {read_err}")

        # 步骤 2: 静态降级资产兼容检查 (frontend/static/unified_decision_latest.json)
        static_fallback = os.path.join(self.proj_dir, "frontend", "static", "unified_decision_latest.json")
        if os.path.exists(static_fallback):
            try:
                with open(static_fallback, "r", encoding="utf-8") as fp:
                    static_data = json.load(fp)
                    return {
                        "status": "ok",
                        "source": "static_fallback",
                        "period": static_data.get("target_period", 0),
                        "data": static_data
                    }
            except Exception as static_err:
                logger.warning(f"读取静态统一决策主脑失败: {static_err}")

        # 步骤 3: 缓存缺失或异常时，实时现场调用主脑进行高阶解算
        try:
            from backend.core.unified_brain.unified_brain import UnifiedDecisionBrain
            brain = UnifiedDecisionBrain(self.proj_dir)
            fresh_res = brain.solve_and_export()
            return {
                "status": "ok",
                "source": "live",
                "period": fresh_res.get("target_period"),
                "data": fresh_res
            }
        except Exception as e:
            logger.error(f"统一决策主脑实时推演解算失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"统一决策主脑推演解算异常: {str(e)}"
            }

    def get_unified_brain(self) -> Dict[str, Any]:
        """Alias for get_unified_brain_latest (API/facade compatibility)."""
        return self.get_unified_brain_latest()

