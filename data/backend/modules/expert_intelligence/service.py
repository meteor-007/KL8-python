# -*- coding: utf-8 -*-
"""
快乐8 专家情报、杀号对冲与逐期自动复盘服务
Expert Intelligence, Kill-Number Hedge & Automated Review Service
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from backend.utils.paths import get_storage_dir
from backend.utils.history_loader import load_history

logger = logging.getLogger("k8quant.expert_service")

STORAGE_FILE = os.path.join(get_storage_dir(), "expert_records.json")

def _ensure_storage_dir():
    os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)

class ExpertIntelligenceService:
    def __init__(self):
        _ensure_storage_dir()
        self._init_default_data()

    def _init_default_data(self):
        """如果存储文件不存在，初始化包含 2026304 期（9位专家+15码绝杀）的初始档案"""
        if not os.path.exists(STORAGE_FILE):
            default_records = {
                "2026304": {
                    "period": "2026304",
                    "date": "2026-11-14",
                    "kill_numbers": [1, 6, 16, 17, 24, 25, 31, 34, 47, 48, 58, 59, 62, 69, 72],
                    "experts": {
                        "发如雪": {
                            "type": "选三 / 选四",
                            "pick3": [12, 14, 66],
                            "pick4": [12, 47, 66, 74],
                            "notes": "红底快手风，重合骨架码 12, 66"
                        },
                        "小巷": {
                            "type": "选三单式",
                            "pick3": [9, 20, 32],
                            "notes": "绿底精选选三"
                        },
                        "妹妹": {
                            "type": "点位 / 连号 / 尾号",
                            "focus_point": 12,
                            "trio": [30, 31, 32],
                            "tail_pairs": [79, 80],
                            "notes": "微信 breeze 推荐，看好12点位与79/80连号"
                        },
                        "北哥": {
                            "type": "选二单式 (主胆拖5码)",
                            "dan": 52,
                            "combos": [[52, 7], [52, 10], [52, 17], [52, 30], [52, 64]],
                            "notes": "粉橙卡片，52主胆拖5码"
                        },
                        "雨滴": {
                            "type": "主胆 + 二选一对决",
                            "dans": [52, 5],
                            "duels": [
                                {"pair": [11, 25], "label": "第1组"},
                                {"pair": [32, 39], "label": "第2组"},
                                {"pair": [51, 78], "label": "第3组"},
                                {"pair": [2, 9], "label": "第4组"},
                                {"pair": [12, 38], "label": "第5组"},
                                {"pair": [50, 73], "label": "第6组"}
                            ],
                            "notes": "黄底双表格对决推荐"
                        },
                        "娟子": {
                            "type": "银胆 + 独荐4码",
                            "dan": 39,
                            "pick4": [24, 39, 58, 76],
                            "notes": "强推定海银胆 39"
                        },
                        "大哥": {
                            "type": "精选6码",
                            "pick6": [24, 27, 33, 37, 25, 68],
                            "notes": "中后区6码出击"
                        },
                        "老赵": {
                            "type": "选三实战",
                            "pick3": [17, 22, 23],
                            "notes": "前区小跨度选三"
                        },
                        "管家": {
                            "type": "同尾特色6码",
                            "pick6": [28, 38, 48, 68, 77, 20],
                            "notes": "主打 8 尾大梯队共振 (28,38,48,68) + 20, 77"
                        }
                    },
                    "created_at": "2026-11-14 20:55:00"
                }
            }
            self._save_all_records(default_records)

    def _load_all_records(self) -> Dict[str, Any]:
        if not os.path.exists(STORAGE_FILE):
            self._init_default_data()
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load expert records: {e}")
            return {}

    def _save_all_records(self, records: Dict[str, Any]):
        _ensure_storage_dir()
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def get_history_periods(self) -> List[Dict[str, Any]]:
        """获取所有已录入的期次概览列表"""
        records = self._load_all_records()
        periods = []
        for p, data in sorted(records.items(), key=lambda x: str(x[0]), reverse=True):
            exp_count = len(data.get("experts", {}))
            kill_count = len(data.get("kill_numbers", []))
            periods.append({
                "period": p,
                "date": data.get("date", ""),
                "expert_count": exp_count,
                "kill_count": kill_count,
                "created_at": data.get("created_at", "")
            })
        return periods

    def get_period_data(self, period: Optional[str] = None) -> Dict[str, Any]:
        """获取指定期次或最新期次的完整情报与杀号对冲计算"""
        records = self._load_all_records()
        if not records:
            return {"status": "error", "message": "暂无专家情报记录"}

        if not period or period not in records:
            # 默认取最大期号
            sorted_keys = sorted(records.keys(), reverse=True)
            period = sorted_keys[0]

        target_data = records[period]
        experts = target_data.get("experts", {})
        kill_nums = set(target_data.get("kill_numbers", []))

        # 1. 统计专家号码频次与共振雷达
        num_freq: Dict[int, List[str]] = {}
        for exp_name, exp_info in experts.items():
            nums_in_exp = set()
            for k, val in exp_info.items():
                if isinstance(val, int):
                    nums_in_exp.add(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, int):
                            nums_in_exp.add(item)
                        elif isinstance(item, list):
                            for sub in item:
                                if isinstance(sub, int):
                                    nums_in_exp.add(sub)
                        elif isinstance(item, dict) and "pair" in item:
                            for sub in item["pair"]:
                                if isinstance(sub, int):
                                    nums_in_exp.add(sub)
            for n in nums_in_exp:
                num_freq.setdefault(n, []).append(exp_name)

        # 排序共振雷达：推荐次数 >= 2 的号码
        resonance_list = []
        for n, exp_list in sorted(num_freq.items(), key=lambda x: len(x[1]), reverse=True):
            is_killed = n in kill_nums
            resonance_list.append({
                "number": n,
                "count": len(exp_list),
                "experts": exp_list,
                "is_killed": is_killed,
                "status": "被杀剔除 ❌" if is_killed else "极度安全 🔥" if len(exp_list) >= 3 else "共振优选 ✨" if len(exp_list) == 2 else "单推"
            })

        # 2. 杀号碰撞与各专家过滤
        expert_cards = []
        for exp_name, exp_info in experts.items():
            card = {
                "name": exp_name,
                "type": exp_info.get("type", "普通推单"),
                "notes": exp_info.get("notes", ""),
                "raw_info": exp_info,
                "killed_hits": [],
                "safe_numbers": []
            }
            # 扫描该专家所有号码
            all_n = []
            for k, val in exp_info.items():
                if isinstance(val, int) and k != "focus_point":
                    all_n.append(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, int):
                            all_n.append(item)
                        elif isinstance(item, list):
                            all_n.extend([x for x in item if isinstance(x, int)])
                        elif isinstance(item, dict) and "pair" in item:
                            all_n.extend([x for x in item["pair"] if isinstance(x, int)])
            
            unique_n = sorted(list(set(all_n)))
            card["killed_hits"] = [x for x in unique_n if x in kill_nums]
            card["safe_numbers"] = [x for x in unique_n if x not in kill_nums]
            card["safety_rate"] = f"{(len(card['safe_numbers']) / len(unique_n) * 100):.1f}%" if unique_n else "100%"
            expert_cards.append(card)

        # 3. 幸存金胆池
        all_safe_pool = sorted([item["number"] for item in resonance_list if not item["is_killed"]])

        return {
            "status": "success",
            "period": period,
            "date": target_data.get("date", ""),
            "kill_numbers": sorted(list(kill_nums)),
            "expert_count": len(experts),
            "experts": experts,
            "expert_cards": expert_cards,
            "resonance_radar": resonance_list,
            "safe_gold_pool": all_safe_pool,
            "created_at": target_data.get("created_at", "")
        }

    def save_period_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """保存或更新专家推码与杀号（手机端/前端录入）"""
        period = str(payload.get("period", "")).strip()
        if not period:
            return {"status": "error", "message": "期号不能为空"}

        records = self._load_all_records()
        records[period] = {
            "period": period,
            "date": payload.get("date", datetime.now().strftime("%Y-%m-%d")),
            "kill_numbers": sorted(list(set([int(x) for x in payload.get("kill_numbers", []) if str(x).isdigit()]))),
            "experts": payload.get("experts", {}),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self._save_all_records(records)
        return {"status": "success", "message": f"第 {period} 期专家情报与杀号已成功保存！", "period": period}

    def get_period_review(self, period: str) -> Dict[str, Any]:
        """获取某一期的详细开奖复盘对账"""
        records = self._load_all_records()
        if period not in records:
            return {"status": "error", "message": f"未找到第 {period} 期的专家记录"}

        target_data = records[period]
        experts = target_data.get("experts", {})
        kill_nums = set(target_data.get("kill_numbers", []))

        # 从官方历史库中查找该期开奖号码
        hist = load_history(limit=100)
        draw_match = next((h for h in hist if str(h.get("issue")) == str(period)), None)

        if not draw_match:
            return {
                "status": "pending",
                "period": period,
                "date": target_data.get("date", ""),
                "is_drawn": False,
                "message": f"第 {period} 期官方尚未开奖，当前处于赛前推演状态！开奖后将自动计算红球对账。",
                "kill_numbers": sorted(list(kill_nums)),
                "experts": experts
            }

        draw_numbers = set(draw_match.get("numbers", []))
        draw_list = sorted(list(draw_numbers))

        # 1. 杀号复盘（绝杀准确率）
        kill_hits = kill_nums.intersection(draw_numbers) # 不幸开出的（误杀）
        kill_success = kill_nums - draw_numbers         # 成功杀掉的
        kill_accuracy = (len(kill_success) / len(kill_nums) * 100) if kill_nums else 100.0

        # 2. 专家对账明细
        review_cards = []
        total_hit_points = 0
        mvp_expert = ""
        max_score = -1

        for exp_name, exp_info in experts.items():
            score = 0
            details = {}

            # 选三
            if "pick3" in exp_info:
                p3 = exp_info["pick3"]
                p3_hits = [x for x in p3 if x in draw_numbers]
                details["pick3"] = {
                    "numbers": p3,
                    "hits": p3_hits,
                    "hit_count": len(p3_hits),
                    "status": "🎯 中三 (全中!)" if len(p3_hits) == 3 else "✨ 中二" if len(p3_hits) == 2 else "中一" if len(p3_hits) == 1 else "未中"
                }
                score += len(p3_hits) * 3

            # 选四
            if "pick4" in exp_info:
                p4 = exp_info["pick4"]
                p4_hits = [x for x in p4 if x in draw_numbers]
                details["pick4"] = {
                    "numbers": p4,
                    "hits": p4_hits,
                    "hit_count": len(p4_hits),
                    "status": "🎉 中四 (全中!)" if len(p4_hits) == 4 else "🎯 中三" if len(p4_hits) == 3 else "✨ 中二" if len(p4_hits) == 2 else "中一" if len(p4_hits) == 1 else "未中"
                }
                score += len(p4_hits) * 3

            # 选六
            if "pick6" in exp_info:
                p6 = exp_info["pick6"]
                p6_hits = [x for x in p6 if x in draw_numbers]
                details["pick6"] = {
                    "numbers": p6,
                    "hits": p6_hits,
                    "hit_count": len(p6_hits),
                    "status": f"命中 {len(p6_hits)}/6"
                }
                score += len(p6_hits) * 2

            # 选二单式
            if "combos" in exp_info:
                combos_res = []
                win_combos = 0
                for c in exp_info["combos"]:
                    c_hits = [x for x in c if x in draw_numbers]
                    is_win = len(c_hits) == 2
                    if is_win:
                        win_combos += 1
                    combos_res.append({
                        "combo": c,
                        "hits": c_hits,
                        "hit_count": len(c_hits),
                        "is_win": is_win
                    })
                details["combos"] = {
                    "list": combos_res,
                    "win_count": win_combos,
                    "total": len(combos_res),
                    "status": f"🏆 命中选二 {win_combos} 注!" if win_combos > 0 else "未中选二"
                }
                score += win_combos * 10

            # 主胆
            if "dan" in exp_info:
                dan_hit = exp_info["dan"] in draw_numbers
                details["dan"] = {
                    "dan": exp_info["dan"],
                    "hit": dan_hit,
                    "status": "🔥 主胆命中!" if dan_hit else "主胆未开"
                }
                if dan_hit:
                    score += 5

            if "dans" in exp_info:
                dans_hits = [d for d in exp_info["dans"] if d in draw_numbers]
                details["dans"] = {
                    "dans": exp_info["dans"],
                    "hits": dans_hits,
                    "status": f"命中主胆: {dans_hits}" if dans_hits else "主胆未开"
                }
                score += len(dans_hits) * 5

            # 二选一对决
            if "duels" in exp_info:
                duels_res = []
                correct_duels = 0
                for d in exp_info["duels"]:
                    pair = d.get("pair", [])
                    pair_hits = [x for x in pair if x in draw_numbers]
                    is_correct = len(pair_hits) >= 1
                    if is_correct:
                        correct_duels += 1
                    duels_res.append({
                        "label": d.get("label", ""),
                        "pair": pair,
                        "hits": pair_hits,
                        "is_correct": is_correct,
                        "result": "精准单中 ✔" if len(pair_hits) == 1 else "双出爆开 🔥" if len(pair_hits) == 2 else "全挂 ❌"
                    })
                details["duels"] = {
                    "list": duels_res,
                    "correct_count": correct_duels,
                    "total": len(duels_res),
                    "accuracy": f"{(correct_duels / len(duels_res) * 100):.1f}%" if duels_res else "0%"
                }
                score += correct_duels * 3

            # 妹妹三连号/尾号
            if "trio" in exp_info:
                trio_hits = [x for x in exp_info["trio"] if x in draw_numbers]
                details["trio"] = {
                    "trio": exp_info["trio"],
                    "hits": trio_hits,
                    "hit_count": len(trio_hits)
                }
                score += len(trio_hits) * 3

            if "tail_pairs" in exp_info:
                tp_hits = [x for x in exp_info["tail_pairs"] if x in draw_numbers]
                details["tail_pairs"] = {
                    "pairs": exp_info["tail_pairs"],
                    "hits": tp_hits,
                    "hit_count": len(tp_hits)
                }
                score += len(tp_hits) * 3

            review_cards.append({
                "name": exp_name,
                "type": exp_info.get("type", ""),
                "score": score,
                "details": details
            })

            if score > max_score:
                max_score = score
                mvp_expert = exp_name

        # 按得分降序排序
        review_cards.sort(key=lambda x: x["score"], reverse=True)

        return {
            "status": "success",
            "period": period,
            "date": target_data.get("date", draw_match.get("date", "")),
            "is_drawn": True,
            "draw_numbers": draw_list,
            "kill_review": {
                "total_killed": len(kill_nums),
                "success_count": len(kill_success),
                "hit_count": len(kill_hits), # 误杀数
                "accuracy": f"{kill_accuracy:.1f}%",
                "killed_success_list": sorted(list(kill_success)),
                "killed_failed_list": sorted(list(kill_hits))
            },
            "mvp_expert": mvp_expert,
            "expert_reviews": review_cards
        }

expert_service = ExpertIntelligenceService()
