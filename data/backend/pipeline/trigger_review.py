# -*- coding: utf-8 -*-
"""
自动复盘触发脚本 (Trigger Review)
=================================
对应 data-每日分析脚本.txt 任务2：深度复盘 + 闭环学习触发

流程:
  1. 读取 kl8_history_final.txt 获取上一期期号和实际开奖号码
  2. 读取上一期预测报告，对账统计各模块命中情况
  3. 调用 AutonomousLearner.on_new_result() 触发闭环学习
  4. 输出学习引擎诊断报告

使用方式:
    python trigger_review.py
"""
import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

# 确保项目路径
_PROJ = os.path.dirname(os.path.abspath(__file__))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from utils.paths import get_project_root, _ensure_project_path
_ensure_project_path()
_ROOT = get_project_root()

HISTORY_FILE = os.path.join(_ROOT, 'kl8_history_final.txt')
REPORTS_DIR = os.path.join(_ROOT, 'reports')


def load_history_lines():
    """读取历史文件，返回按行解析的列表（最新在前）"""
    if not os.path.exists(HISTORY_FILE):
        print("[ERROR] kl8_history_final.txt 不存在")
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    parsed = []
    for line in lines:
        period_m = re.search(r'period:(\d+)', line)
        nums_m = re.search(r'numbers:([\d-]+)', line)
        date_m = re.search(r'date:(\d{4}-\d{2}-\d{2})', line)
        if period_m and nums_m:
            nums = [int(x) for x in nums_m.group(1).split('-') if x.isdigit()]
            parsed.append({
                'period': period_m.group(1),
                'numbers': nums,
                'date': date_m.group(1) if date_m else '',
                'raw': line,
            })
    return parsed


def find_prev_period_and_actual(history_lines):
    """获取上一期的期号和实际开奖号码"""
    if len(history_lines) < 2:
        print("[WARN] 历史数据不足2期，无法复盘")
        return None, None
    # 第一行是最新期（今天预测的目标期的上一期开奖）
    # 第二行是上上一期（即昨天预测的目标期，需要复盘的期）
    # 实际上：最新期 = 昨天开奖的，需要复盘的就是最新期
    latest = history_lines[0]
    prev_period = latest['period']
    prev_actual = latest['numbers']
    prev_date = latest['date']
    print(f"[复盘] 目标期号: {prev_period} (日期: {prev_date})")
    print(f"[复盘] 实际开奖: {prev_actual}")
    return prev_period, prev_actual


def load_yesterday_report(prev_period):
    """读取上一期的预测报告"""
    if not os.path.exists(REPORTS_DIR):
        return None
    # 尝试按日期匹配报告文件
    files = sorted(Path(REPORTS_DIR).glob("daily_analysis_report_*.md"), reverse=True)
    if not files:
        return None
    # 读取最近的报告（倒数第二个，因为最新的是今天刚生成的或还没生成）
    # 如果今天还没生成报告，最新的就是昨天的
    content = None
    for f in files[:3]:  # 检查最近3个报告
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                c = fh.read()
            # 检查报告中的目标期号是否匹配
            m = re.search(r'目标期号[：:]\s*\**\s*(\d+)', c)
            if m and m.group(1) == prev_period:
                content = c
                print(f"[复盘] 找到匹配报告: {f.name}")
                break
        except Exception:
            continue
    if not content and files:
        # 如果没找到匹配的，用最新的报告
        try:
            with open(files[0], 'r', encoding='utf-8') as fh:
                content = fh.read()
            print(f"[复盘] 使用最近报告: {files[0].name}")
        except Exception:
            pass
    return content


def review_report(report_content, actual_nums):
    """对账统计：报告中的预测 vs 实际开奖"""
    if not report_content or not actual_nums:
        return {}
    actual_set = set(actual_nums)
    review = {}

    # 三维融合 Top5
    m = re.search(r'极秘 Top 5.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['trinity_top5'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    # 三维融合 Top12
    m = re.search(r'极秘 Top 12.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['trinity_top12'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    # AI Top5
    m = re.search(r'Top 5 置信度精选.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['ai_top5'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    # Hidden Energy 5
    m = re.search(r'最终推荐.*?5.*?码.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['he5'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    # Golden Core
    m = re.search(r'高频共振集群.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['golden_core'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    # mRMR Top12
    m = re.search(r'mRMR Top 12.*?\[([^\]]+)\]', report_content)
    if m:
        nums = [int(x) for x in re.findall(r'\d+', m.group(1)) if 1 <= int(x) <= 80]
        hits = set(nums) & actual_set
        review['mrmr_top12'] = {'total': len(nums), 'hits': len(hits), 'hit_nums': sorted(hits)}

    return review


def main():
    print("=" * 60)
    print("  自动复盘 + 闭环学习触发 (Task 2)")
    print("=" * 60)

    # Step 1: 读取历史数据
    history_lines = load_history_lines()
    if not history_lines:
        print("[ERROR] 无法加载历史数据，复盘终止")
        return

    print(f"\n[数据] 历史记录 {len(history_lines)} 期")
    print(f"[数据] 最新期号: {history_lines[0]['period']}")
    print(f"[数据] 最新开奖: {history_lines[0]['numbers']}")

    # Step 2: 获取上一期期号和实际开奖
    prev_period, prev_actual = find_prev_period_and_actual(history_lines)
    if not prev_period or not prev_actual:
        print("[ERROR] 无法确定复盘目标，终止")
        return

    # Step 3: 读取上一期预测报告并对账
    report_content = load_yesterday_report(prev_period)
    if report_content:
        print("\n═══ 对账统计 ═══")
        review = review_report(report_content, prev_actual)
        for module, data in review.items():
            total = data['total']
            hits = data['hits']
            lift = round(hits / total / 0.25, 2) if total > 0 else 0
            status = "✅" if lift >= 1.0 else "❌"
            print(f"  {status} {module}: {hits}/{total} (Lift={lift}x) 命中: {data['hit_nums']}")
    else:
        print("[WARN] 未找到匹配的预测报告，跳过对账统计")

    # Step 4: 触发闭环学习
    print("\n═══ 触发闭环学习 ═══")
    try:
        from learning.autonomous_learner import AutonomousLearner
        learner = AutonomousLearner()

        # 构建history参数（AutonomousLearner.on_new_result 需要）
        history_for_learner = [{'issue': h['period'], 'numbers': h['numbers']} for h in history_lines]

        report = learner.on_new_result(prev_period, prev_actual, history_for_learner)

        print("\n[闭环学习报告]")
        print(json.dumps({k: v for k, v in report.items()},
                         ensure_ascii=False, indent=2, default=str))

        # Step 5: 输出学习引擎诊断
        print("\n═══ 学习引擎诊断 ═══")
        learner.print_diagnosis()

    except Exception as e:
        print(f"[ERROR] 闭环学习触发失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n✅ 自动复盘+闭环学习完成")


if __name__ == '__main__':
    main()
