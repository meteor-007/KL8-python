# -*- coding: utf-8 -*-
"""
快乐8 决策树驱动 012路 × 质合智能缩水系统 CLI 每日运行入口 (Run Daily Entrypoint)
================================================================================
【业务功能】:
1. 物理加载全历史开奖账本 (kl8_history_final.txt)；
2. 调度 TreeRoadPrimeShrinkEngine 机器学习决策树大脑；
3. 自动将结果持久化至 outputs/predictions/ 与 outputs/reports/；
4. 在控制台全息输出老派操盘手大白话推演战报及手机端一键复制文本块。

@author Antigravity Quant Team
@since 2026-10-23
"""

from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime

# 解决 Windows 控制台 GBK 编码输出 emoji 异常
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 保证根路径可被正确引用
_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURR_DIR, "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.modules.road_prime_shrink.tree_engine import TreeRoadPrimeShrinkEngine
from backend.utils.paths import get_outputs_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("k8quant.road_prime_shrink.cli")


def load_raw_history(history_path: str) -> list[dict]:
    """物理读取官方开奖全历史文本"""
    if not os.path.exists(history_path):
        raise FileNotFoundError(f"历史数据文件不存在: {history_path}")

    records = []
    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                date_str = parts[0].split(":")[1] if ":" in parts[0] else ""
                period_str = parts[1].split(":")[1] if ":" in parts[1] else ""
                nums_str = parts[2].split(":")[1] if ":" in parts[2] else ""
                nums = [int(x) for x in nums_str.split("-") if x.isdigit()]
                if len(nums) == 20:
                    records.append({
                        "date": date_str,
                        "period": period_str,
                        "numbers": nums,
                    })
    return records


def format_console_output(res: dict) -> str:
    """老派操盘手全息控制台输出"""
    meta = res["meta"]
    macro = res["macro_diagnosis"]
    card = res["analysis_card"]
    rankings = res["feature_ranking"][:6]
    top3 = res["top3_gold"]
    top5 = res["top5_gold"]
    top20 = res["top20_core_base"]
    top25 = res["top25_mid_base"]
    top30 = res["top30_large_base"]
    pairs = res["pick2_pairs"]
    pools = res["pool_distribution"]
    pools25 = res.get("pool_distribution_25", {})
    pools20 = res.get("pool_distribution_20", {})

    c0 = macro["cnt_road"][0]
    c1 = macro["cnt_road"][1]
    c2 = macro["cnt_road"][2]
    cp = macro["cnt_prime"]

    lines = []
    lines.append("=" * 82)
    lines.append(f"  🧬 快乐8 决策树驱动 012路 × 质合正交多梯度智能缩水推演系统 (TPRD v1.0)")
    lines.append(f"  🎯 目标期号: 第 {meta['target_period']} 期 | 基准基石: 第 {meta['latest_period']} 期开奖 | 决策树样本: {meta['train_samples']} 组")
    lines.append("=" * 82)

    # 〇、大盘体检
    lines.append("\n【〇、大盘宏观偏态体检卡 (Macro Skew Diagnosis)】")
    lines.append(f"  * 上期开奖基准实开 20 码: {' '.join(f'{x:02d}' for x in macro['last_draw'])}")
    lines.append(f"  * 012路结构分布: [0路: {c0} 码, 1路: {c1} 码, 2路: {c2} 码] (理论均衡基线 6.67 码)")
    lines.append(f"  * 质合结构分布: [质数: {cp} 码, 合数: {20 - cp} 码] (理论基线 5.50 码)")
    lines.append(f"  * 老派操盘手战术建议: {card['tactical_advice']}")

    # 一、看谁最管用
    lines.append("\n【一、AI 海选团特征重要性大典 (看谁最管用 / Feature Importance)】")
    lines.append("  序号  特征指标名称                  重要性权重   业务操盘大白话解读")
    lines.append("  " + "-" * 76)
    for item in rankings:
        desc = ""
        if "遗漏弹性" in item["feature"]:
            desc = "找憋到极限、蓄势待发的冷号回补"
        elif "频次" in item["feature"]:
            desc = "量化号码短期内是正热还是正凉"
        elif "动能" in item["feature"]:
            desc = "算算号码是正在迅速爆发还是热过头"
        elif "邻居" in item["feature"]:
            desc = "昨天的号码今天左右邻居沾不沾光"
        elif "012路" in item["feature"]:
            desc = "大盘模3余数分布防撞与跨路对冲"
        elif "重号" in item["feature"]:
            desc = "判断上期开出号码今天连击概率"
        elif "质合" in item["feature"]:
            desc = "质数合数空间正交防守"
        else:
            desc = "大盘物理属性参考指标"
        lines.append(f"  #{item['rank']:<2}   {item['feature']:<26} {item['weight_percent']:<10} {desc}")

    # 二、高胜率规则
    lines.append("\n【二、决策树提取的最管用出号规则路径 (Decision Rules Preview)】")
    for r_line in res["tree_rules_text"].splitlines()[:12]:
        if r_line.strip():
            lines.append(f"  {r_line}")

    # 三、多梯度实战缩水矩阵 (20码 / 25码 / 30码)
    lines.append("\n【三、多梯度实战正交缩水矩阵 (20码 / 25码 / 30码)】")
    lines.append(f"  🔥 1. 【20 码极致主力阵列】(与开奖号码 1:1 等量，命中率要求极高):")
    for i in range(0, len(top20), 10):
        chunk = top20[i:i+10]
        lines.append("     " + " ".join(f"[{x:02d}]" for x in chunk))

    lines.append(f"\n  🎯 2. 【25 码精选进阶大底】(高性价比实操方案):")
    for i in range(0, len(top25), 10):
        chunk = top25[i:i+10]
        lines.append("     " + " ".join(f"[{x:02d}]" for x in chunk))

    lines.append(f"\n  🛡️ 3. 【30 码黄金稳健大底】(宽幅防守兜底保本):")
    for i in range(0, len(top30), 10):
        chunk = top30[i:i+10]
        lines.append("     " + " ".join(f"[{x:02d}]" for x in chunk))

    # 四、核心胆码
    lines.append("\n【四、尖刀金胆 (Top3) 与 主力精选 (Top5)】")
    lines.append(f"  * 尖刀三胆 (Top3): {' '.join(f'★{x:02d}' for x in top3)}")
    lines.append(f"  * 主力五胆 (Top5): {' '.join(f'◆{x:02d}' for x in top5)}")

    # 五、黄金选2搭档
    lines.append("\n【五、跨路对冲黄金选 2 搭档 (3组实战组合拳)】")
    for idx, p_info in enumerate(pairs, 1):
        p_nums = p_info["pair"]
        lines.append(f"  组合 {idx}: 【 {p_nums[0]:02d} , {p_nums[1]:02d} 】 -- {p_info['label']} ({p_info['desc']})")

    # 六、微信速发
    lines.append("\n【六、操盘速查一键复制文本块 (手机微信极简版)】")
    lines.append("-" * 50)
    lines.append(f"【快乐8 第{meta['target_period']}期 决策树智能精选】")
    lines.append(f"🥇尖刀金胆: {' '.join(f'{x:02d}' for x in top3)}")
    lines.append(f"🥈主力五码: {' '.join(f'{x:02d}' for x in top5)}")
    lines.append(f"🎯选2搭档: {pairs[0]['pair'][0]:02d}-{pairs[0]['pair'][1]:02d} | {pairs[1]['pair'][0]:02d}-{pairs[1]['pair'][1]:02d}")
    lines.append(f"🔥20码主力: {' '.join(f'{x:02d}' for x in top20)}")
    lines.append(f"🎯25码精选: {' '.join(f'{x:02d}' for x in top25)}")
    lines.append(f"🛡️30码大底: {' '.join(f'{x:02d}' for x in top30)}")
    lines.append("-" * 50)
    lines.append("-" * 50)

    return "\n".join(lines)


def main():
    root = _PROJECT_ROOT
    history_file = os.path.join(root, "storage", "raw", "kl8_history_final.txt")
    out_dir = os.path.join(get_outputs_dir(), "predictions")
    reports_dir = os.path.join(get_outputs_dir(), "reports")
    storage_out_dir = os.path.join(root, "storage", "outputs", "road_prime_shrink")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(storage_out_dir, exist_ok=True)

    records = load_raw_history(history_file)
    engine = TreeRoadPrimeShrinkEngine(records, train_window=120)
    res = engine.execute_inference()
    target_period = str(res["meta"]["target_period"])

    # 控制台全息输出
    console_text = format_console_output(res)
    print(console_text)

    # 物理落盘 JSON (双路径保真：outputs/predictions/ 与 storage/outputs/road_prime_shrink/)
    json_path = os.path.join(out_dir, "tree_shrink_latest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    json_storage_period = os.path.join(storage_out_dir, f"road_prime_shrink_{target_period}.json")
    with open(json_storage_period, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    json_storage_latest = os.path.join(storage_out_dir, "road_prime_shrink_latest.json")
    with open(json_storage_latest, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    logger.info(f"已生成最新推演 JSON 资产: {json_path} 及 {json_storage_period}")

    # 物理落盘 Markdown 研报
    md_path = os.path.join(reports_dir, "tree_shrink_report_latest.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 快乐8 决策树驱动 012路 × 质合智能缩水推演战报\n\n```text\n{console_text}\n```\n")
    logger.info(f"已生成最新推演 MD 战报: {md_path} ({os.path.getsize(md_path)} bytes)")

    return res


if __name__ == "__main__":
    main()
