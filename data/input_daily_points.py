#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日最新点位录入与全模块联动终端 (Daily Points Input & Dispatcher Terminal v2.0)
================================================================================
遵循老派量化操盘手大白话执行协议：
  - 智能推断目标期号与日期
  - 任意格式粘贴（空格/逗号/顿号/连字符/换行/Excel多行）
  - 20码严格契约校验 + 8分区/奇偶/大小/和值特征画像
  - 安全原子落盘与带时间戳备份
  - 一键联动热码加权、Excel上色、空间点位打分与未开点位高压反弹推演

用法：
  交互模式：
    python input_daily_points.py
  命令行直接写入并自动联动：
    python input_daily_points.py --points "04 12 17 19 24 25 34 35 39 40 44 45 49 50 54 59 60 67 69 74" --auto-run
  查看最近点位记录：
    python input_daily_points.py --list 10
  校验点位库健康度：
    python input_daily_points.py --check
  单独触发下游点位联动：
    python input_daily_points.py --run-downstream
"""
import os
import sys
import re
import argparse
from datetime import datetime

# 路径自适应 (Dual-Root Bootstrap)
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
PROJ_DIR = _PROJ_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.data_acquisition.daily_points_manager import (
    parse_points_input,
    validate_points_list,
    load_daily_points,
    get_latest_points_entry,
    get_next_target_info,
    analyze_points_distribution,
    save_daily_points,
    run_downstream_task,
    run_all_points_downstream,
    POINTS_FILE,
    HISTORY_FILE,
    POINTS_COUNT,
    NUM_BALLS
)

# 颜色控制
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_GRAY = "\033[90m"

LINE = "═" * 76
THIN = "─" * 76


def banner(txt: str, color: str = C_CYAN):
    print(f"\n{color}{LINE}")
    print(f"  {txt}")
    print(f"{LINE}{C_RESET}")


def print_analysis_report(target_period_str: str, target_date: str, analysis: dict):
    """打印点位大白话量化分析报告"""
    banner(f"📊 目标期 [{target_period_str}] ({target_date}) 点位多维特征画像", C_GREEN)
    pts_str = analysis["points_str"]
    print(f"  💎 输入点位 (20码) : {C_BOLD}{C_CYAN}{pts_str}{C_RESET}")
    print(f"  📈 基础指标统计   : 和值 = {C_BOLD}{analysis['total_sum']}{C_RESET} | 均值 = {analysis['mean_val']} | 奇偶比 = {analysis['odd_even_ratio']} | 大小比 = {analysis['big_small_ratio']} | 质数 = {analysis['prime_count']}个")
    
    # 8 分区覆盖
    print(f"\n  🧭 8 分区空间能量分布 (大白话：看哪个区域出号最密):")
    row1 = []
    row2 = []
    for idx, (z_name, z_data) in enumerate(analysis["zone_dist"].items()):
        cnt = z_data["count"]
        cnt_color = C_GREEN if cnt >= 3 else (C_YELLOW if cnt in (1, 2) else C_RED)
        block = f"{z_name}: {cnt_color}{cnt:2d}码{C_RESET}"
        if idx < 4:
            row1.append(block)
        else:
            row2.append(block)
    print("     " + "  │  ".join(row1))
    print("     " + "  │  ".join(row2))
    
    if analysis["missing_zones"]:
        print(f"     ⚠️  {C_RED}存在轮空分区{C_RESET}: {' '.join(analysis['missing_zones'])}")
    else:
        print(f"     ✅  {C_GREEN}8 分区全域覆盖平衡{C_RESET}")
        
    # 连号与尾数
    if analysis["consecutive_pairs"]:
        pairs_s = "、".join(f"{a:02d}-{b:02d}" for a, b in analysis["consecutive_pairs"])
        print(f"\n  🔗 连号/最佳搭档 ({analysis['consecutive_count']}组) : {C_YELLOW}{pairs_s}{C_RESET}")
    else:
        print(f"\n  🔗 连号状态 : 无连号 (全盘离散分布)")
        
    top_tails = [f"{t}尾({c}个)" for t, c in analysis["hot_tails"][:4] if c > 0]
    print(f"  🎯 强势热出尾数 : {' │ '.join(top_tails)}")
    
    # 昨日对比
    if analysis["repeat_from_prev_pts"]:
        rep_s = " ".join(f"{x:02d}" for x in analysis["repeat_from_prev_pts"])
        print(f"  🔁 与昨日点位重码 ({len(analysis['repeat_from_prev_pts'])}个) : {C_MAGENTA}{rep_s}{C_RESET}")
        
    if analysis["repeat_from_latest_draw"]:
        drw_s = " ".join(f"{x:02d}" for x in analysis["repeat_from_latest_draw"])
        print(f"  ✨ 与昨日实际开奖重码 ({len(analysis['repeat_from_latest_draw'])}个) : {C_CYAN}{drw_s}{C_RESET}")


def interactive_wizard():
    """交互式录入向导"""
    banner("🎯 快乐8 每日最新点位录入与全系统联动操盘终端", C_CYAN)
    
    info = get_next_target_info()
    print(f"  📁 历史开奖最新期: {C_BOLD}{info['latest_history_period']}{C_RESET} ({info['latest_history_date']})")
    print(f"  📝 点位库已录最新: {C_BOLD}{info['latest_points_period']}{C_RESET} ({info['latest_points_date']})")
    print(f"  🎯 系统推荐目标期: {C_BOLD}{C_GREEN}{info['target_period']}{C_RESET} (推荐日期: {info['target_date']})")
    
    if info["already_input"]:
        exist_str = " ".join(f"{x:02d}" for x in info["existing_points"])
        print(f"  ⚠️  {C_YELLOW}检测到目标期 [{info['target_period']}] 库中已存在点位数据:{C_RESET}")
        print(f"     {exist_str}")
        
    print(f"\n{THIN}")
    
    # 1. 确认期号
    period_in = input(f"👉 请输入或确认目标期号 [直接回车默认: {info['target_period']}]: ").strip()
    target_period_str = period_in if period_in else info["target_period_str"]
    
    # 2. 确认日期
    date_in = input(f"👉 请输入或确认目标日期 (YYYY-MM-DD) [直接回车默认: {info['target_date']}]: ").strip()
    target_date_str = date_in if date_in else info["target_date"]
    
    # 3. 输入 20 个点位号码
    print(f"\n{THIN}")
    print("👉 请输入今日 20 个点位号码 (可直接复制粘贴，支持空格/逗号/连字符/换行):")
    
    points_list = []
    while True:
        raw_pts = input("点位号码 > ").strip()
        if not raw_pts:
            print("⚠️ 输入为空，请重新输入 20 个点位号码。")
            continue
            
        parsed = parse_points_input(raw_pts)
        valid, msg = validate_points_list(parsed)
        if valid:
            points_list = parsed
            break
        else:
            print(f"❌ {C_RED}{msg}{C_RESET}")
            print(f"   (当前已识别有效号码 {len(parsed)} 个: {' '.join(f'{x:02d}' for x in parsed)})")
            print("   请检查后重新完整输入 20 个号码：")
            
    # 4. 分析与画像
    prev_entry = get_latest_points_entry()
    prev_pts = prev_entry["points"] if prev_entry else None
    
    latest_draw_nums = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for l in f:
                if "numbers:" in l:
                    nums_part = l.split("numbers:")[1].strip()
                    latest_draw_nums = [int(x) for x in nums_part.split("-") if x.isdigit()]
                    break
                    
    analysis = analyze_points_distribution(points_list, prev_points=prev_pts, latest_draw=latest_draw_nums)
    print_analysis_report(target_period_str, target_date_str, analysis)
    
    # 5. 确认保存
    print(f"\n{THIN}")
    save_confirm = input(f"💾 是否确认将上述 20 个点位保存至 daily_points.txt？ [Y/n]: ").strip().lower()
    if save_confirm in ["", "y", "yes"]:
        res = save_daily_points(target_date_str, target_period_str, points_list)
        if res["status"] == "ok":
            action_desc = "更新" if res["action"] == "updated" else "新增"
            print(f"✅ {C_GREEN}点位数据已安全落盘！({action_desc}期号 {target_period_str}, 库中总记录: {res['total_records']} 期){C_RESET}")
        else:
            print(f"❌ {C_RED}保存失败: {res.get('message')}{C_RESET}")
            return
    else:
        print("🛑 已取消保存。")
        return
        
    # 6. 后续联动菜单
    banner("🚀 下游量化预测与格式同步联动中心", C_MAGENTA)
    print("  [1] 🚀 一键跑完全部点位联动预测 (热码加权 + 格式上色 + 空间点位 + 未开反弹) (推荐)")
    print("  [2] 🔮 仅运行空间重点点位分析 (run_points_daily.py)")
    print("  [3] 🪞 仅运行未开点位反弹追踪 (run_suppression_daily.py)")
    print("  [4] 📊 仅同步 Excel 点位粉色底色与中奖边框 (apply_formats.py)")
    print("  [5] ⚡ 运行每日完整量化全流水线 (run_full_pipeline.py)")
    print("  [0] 🚪 保存完毕，直接退出")
    
    action_in = input("\n👉 请选择操作编号 [默认: 1]: ").strip()
    if action_in in ["", "1"]:
        run_all_points_downstream(verbose=True)
    elif action_in == "2":
        run_downstream_task("spatial_points", verbose=True)
    elif action_in == "3":
        run_downstream_task("suppression", verbose=True)
    elif action_in == "4":
        run_downstream_task("format", verbose=True)
    elif action_in == "5":
        run_downstream_task("full_pipeline", verbose=True)
    else:
        print("✅ 操作完成，再见！")


def list_records(n: int = 10):
    """列出最近 N 期点位记录"""
    banner(f"📋 最近 {n} 期 daily_points.txt 点位记录", C_CYAN)
    pts_dict = load_daily_points()
    if not pts_dict:
        print("  ⚠️ 点位库暂无记录。")
        return
        
    sorted_issues = sorted(pts_dict.keys(), key=int, reverse=True)[:n]
    print("  期号        日期         点位号码 (20码)")
    print(f"  {THIN}")
    for iss in sorted_issues:
        item = pts_dict[iss]
        pts_s = " ".join(f"{x:02d}" for x in item["points"])
        print(f"  {iss}   {item['date']:<10}   {pts_s}")
    print(f"  {THIN}")
    print(f"  总记录数: {len(pts_dict)} 期")


def check_integrity():
    """检查 daily_points.txt 数据完整性与格式健康度"""
    banner("🔍 daily_points.txt 数据健康度审计", C_YELLOW)
    if not os.path.exists(POINTS_FILE):
        print(f"  ❌ 找不到点位文件: {POINTS_FILE}")
        return
        
    total_lines = 0
    valid_lines = 0
    errors = []
    seen_issues = set()
    
    with open(POINTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            
            m_iss = re.search(r"period:(\d+)", line)
            m_date = re.search(r"date:([0-9\-]+)", line)
            m_pts = re.search(r"points:([\d\s]+)", line)
            
            if not (m_iss and m_date and m_pts):
                errors.append(f"第 {idx} 行格式缺失: {line[:50]}")
                continue
                
            iss = m_iss.group(1)
            if iss in seen_issues:
                errors.append(f"第 {idx} 行存在重复期号: {iss}")
            seen_issues.add(iss)
            
            pts = [int(x) for x in m_pts.group(1).strip().split() if x.isdigit()]
            valid, msg = validate_points_list(pts)
            if not valid:
                errors.append(f"第 {idx} 行 (期号 {iss}) {msg}")
            else:
                valid_lines += 1
                
    print(f"  📁 扫描总行数 : {total_lines}")
    print(f"  ✅ 完美合规行 : {valid_lines}")
    if errors:
        print(f"  ⚠️  {C_RED}发现 {len(errors)} 个异常项:{C_RESET}")
        for e in errors[:10]:
            print(f"     ❌ {e}")
    else:
        print(f"  🎉 {C_GREEN}点位文件 100% 合规无瑕疵！{C_RESET}")


def main():
    parser = argparse.ArgumentParser(description="快乐8 每日点位录入与全模块联动终端")
    parser.add_argument("--points", "-p", type=str, help="直接传入 20 个点位号码（空格/逗号分隔）")
    parser.add_argument("--period", "-i", type=str, help="指定期号（默认自动推断）")
    parser.add_argument("--date", "-d", type=str, help="指定日期 YYYY-MM-DD（默认自动推断）")
    parser.add_argument("--auto-run", "-r", action="store_true", help="保存后自动触发全部下游点位联动")
    parser.add_argument("--list", "-l", type=int, nargs="?", const=10, help="查看最近 N 条点位记录")
    parser.add_argument("--check", "-c", action="store_true", help="校验 daily_points.txt 文件健康度")
    parser.add_argument("--run-downstream", action="store_true", help="直接执行全部下游点位联动分析")
    
    args = parser.parse_args()
    
    if args.list:
        list_records(args.list)
        return
        
    if args.check:
        check_integrity()
        return
        
    if args.run_downstream:
        run_all_points_downstream(verbose=True)
        return
        
    if args.points:
        # CLI 模式
        parsed = parse_points_input(args.points)
        valid, msg = validate_points_list(parsed)
        if not valid:
            print(f"❌ {C_RED}点位输入校验失败: {msg}{C_RESET}")
            sys.exit(1)
            
        info = get_next_target_info()
        target_period = args.period or info["target_period_str"]
        target_date = args.date or info["target_date"]
        
        analysis = analyze_points_distribution(parsed)
        print_analysis_report(target_period, target_date, analysis)
        
        res = save_daily_points(target_date, target_period, parsed)
        if res["status"] == "ok":
            print(f"✅ {C_GREEN}点位已成功保存至 daily_points.txt (期号: {target_period}){C_RESET}")
            if args.auto_run:
                run_all_points_downstream(verbose=True)
        else:
            print(f"❌ {C_RED}保存失败: {res.get('message')}{C_RESET}")
            sys.exit(1)
        return
        
    # 无参数时进入交互式向导
    interactive_wizard()


if __name__ == "__main__":
    main()
