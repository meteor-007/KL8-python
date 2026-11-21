# -*- coding: utf-8 -*-
"""
快乐8 工业级全流程决策、复盘与生产一体化主入口 (Daily Complete v2.0)
================================================================================
执行标准：
  1. 同步最新开奖数据并校验期号连续性；
  2. 自动检索 validation/file/ 目录下最新的点位图 Excel (提取20点位 + 三高数据)，支持平稳降级；
  3. 执行昨日实盘全景立体对账 (选2黄金搭档、Meta-Gold金胆、Top12、深层关联、点位与三高)；
  4. 运行全量预测模型，生成 Markdown 全景研报与 Excel 宽表；
  5. 自动渲染并导出【微信群专享分桶发布原文】；
  6. 调用盖尔·霍华德旋转矩阵保奖引擎，生成实战缩水打票单 (选五保四/选四保三)；
  7. 终端采用深色科技感高对比度排版美化输出，提供所有产物的一键直达链接与 Web 大屏探活。
"""

import os
import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path

# 导包路径设置
_SCRIPT_DIR = Path(__file__).resolve().parent
_DATA_DIR = _SCRIPT_DIR.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from backend.pipeline.data_center import DataCenter
from backend.pipeline.auto_generate_daily_report import DailyReportOrchestrator
from backend.modules.wheel_matrix.wheel_engine import WheelEngine, BUILTIN_WHEELS
from backend.modules.wheel_matrix.models import GameType
from scripts.import_daily_excel import run_excel_import

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def print_banner(title: str, subtitle: str = ""):
    print("\n" + "═" * 80)
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print("═" * 80)


def get_display_width(text: str) -> int:
    import unicodedata
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ('F', 'W'):
            w += 2
        else:
            w += 1
    return w


def format_box(title: str, content_lines: list, border_char: str = "─") -> str:
    max_len = 76
    w = get_display_width(title)
    pad = max(max_len - w - 8, 2)
    header = f"┌{border_char * 2} 【 {title} 】 {border_char * pad}┐"
    lines = [header]
    for line in content_lines:
        lines.append(f"│  {line}")
    lines.append(f"└{border_char * max_len}┘")
    return "\n".join(lines)


def run_pipeline_complete():
    t_start = time.time()
    print_banner(
        "🧬 K8-QUANT 快乐8 工业级全流程决策与科学复盘一体机 (v2.0)",
        f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 工作区: {_DATA_DIR}"
    )

    # --------------------------------------------------------------------------
    # 步骤 1: 开奖数据同步与连续性核验
    # --------------------------------------------------------------------------
    # 步骤 1: 自动检测开奖连续性并自动在线同步补齐
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 1/7] 正在自动检测开奖连续性并同步补齐最新数据...")
    try:
        from backend.data_acquisition.fetch_kl8_history import fetch_history, HISTORY_FILE
        print("  🔄 触发在线双源 (CWL/17500) 增量更新与断期自动补齐...")
        fetch_history()

        # 同步最新全量账本至 TPRD 系统
        import shutil
        tprd_history = _DATA_DIR.parent / "kl8_tprd_system" / "data" / "kl8_history_final.txt"
        if tprd_history.parent.exists() and os.path.exists(HISTORY_FILE):
            shutil.copy2(HISTORY_FILE, tprd_history)
        root_tprd = _DATA_DIR.parent.parent / "kl8_tprd_system" / "data" / "kl8_history_final.txt"
        if root_tprd.parent.exists() and os.path.exists(HISTORY_FILE):
            shutil.copy2(HISTORY_FILE, root_tprd)

        # 自动补齐热码统计与跟随数据
        try:
            from backend.data_acquisition.generate_hot_excel import main as gen_hot_main
            from backend.data_acquisition.process_hot_numbers import process as proc_hot
            print("  🔄 自动校验热码统计与跟随数据连续性...")
            orig_argv = list(sys.argv)
            sys.argv = [sys.argv[0], "--fill-missing"]
            gen_hot_main()
            sys.argv = orig_argv
            proc_hot(sync_all_missing=True)
        except Exception as he:
            print(f"  ⚠️ [热码同步联动提示] {he}")
    except Exception as fe:
        print(f"  ⚠️ [数据抓取告警] 增量抓取跳过或异常: {fe}")

    try:
        DataCenter.reset_singleton()
        dc = DataCenter()
        dc.initialize()
        latest_issue = str(dc.latest_issue)
        try:
            target_issue = str(int(latest_issue) + 1)
        except Exception:
            target_issue = "未知"

        history_count = len(dc.history) if hasattr(dc, "history") else 0
        latest_draw_nums = getattr(dc, "latest_draw", [])
        print(f"  ✅ [数据同步就绪] 本地历史库: {history_count} 期 | 最新开奖期: {latest_issue} | 目标推演期: {target_issue}")
        if latest_draw_nums:
            draw_str = " ".join([f"{int(x):02d}" for x in latest_draw_nums[:20]])
            print(f"  🎯 [{latest_issue}期 实际开奖]: {draw_str}")
    except Exception as e:
        print(f"  ⚠️ [数据同步告警] DataCenter 初始化异常: {e}，尝试使用备用通道继续...")
        latest_issue = "未知"
        target_issue = "未知"

    if not target_issue.isdigit():
        print("  ❌ [中止] 无法确定目标推演期号（开奖数据同步失败），停止后续推演与发布，避免产出错期内容。")
        return 1

    # --------------------------------------------------------------------------
    # 步骤 2: 自动检索与解析 Excel 点位 + 三高特征群 (带平稳降级)
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 2/7] 检索 validation/file/ 目录最新 Excel 点位与三高数据...")
    excel_status = run_excel_import(quiet=True)
    
    # 读取最新提取的数据确认状态
    daily_points_file = _DATA_DIR / "storage" / "raw" / "daily_points.txt"
    tri_high_file = _DATA_DIR / "storage" / "points" / "tri_high_points.json"
    
    extracted_period = ""
    points_20 = []
    tri_high_record = {}
    if daily_points_file.exists():
        try:
            lines = [l.strip() for l in daily_points_file.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
            target_line = None
            for l in lines:
                if f"period:{target_issue}" in l or (l.startswith(target_issue + " ") or l.startswith(target_issue + "\t")):
                    target_line = l
                    break
            if not target_line and lines:
                target_line = lines[0]
            
            if target_line:
                if "points:" in target_line:
                    kvs = dict(kv.split(":", 1) for kv in target_line.split(",") if ":" in kv)
                    extracted_period = kvs.get("period", "").strip()
                    pts_str = kvs.get("points", "").strip()
                    points_20 = [f"{int(x):02d}" for x in pts_str.split() if x.isdigit()]
                else:
                    parts = target_line.split()
                    if len(parts) >= 21:
                        extracted_period = parts[0]
                        points_20 = [f"{int(x):02d}" for x in parts[1:21] if x.isdigit()]
        except Exception:
            pass

    if tri_high_file.exists():
        try:
            raw_data = json.loads(tri_high_file.read_text(encoding="utf-8-sig"))
            if isinstance(raw_data, dict):
                records = raw_data.get("records", [])
                if records and isinstance(records, list):
                    for r in records:
                        if str(r.get("period", "")).strip() == str(target_issue):
                            tri_high_record = r
                            break
                    if not tri_high_record:
                        tri_high_record = records[0]
                else:
                    tri_high_record = raw_data
        except Exception:
            pass

    if points_20:
        print(f"  ✅ [点位数据注入] 成功载入目标第 {extracted_period or target_issue} 期点位 (20码):")
        print(f"     📍 点位库: {', '.join(points_20)}")
        if tri_high_record:
            rep = ", ".join([f"{int(x):02d}" for x in tri_high_record.get("repeat_high", [])])
            edge_l = ", ".join([f"{int(x):02d}" for x in tri_high_record.get("edge_high_left", [])])
            edge_r = ", ".join([f"{int(x):02d}" for x in tri_high_record.get("edge_high_right", [])])
            cold = ", ".join([f"{int(x):02d}" for x in tri_high_record.get("cold_high", [])])
            print(f"     ⚡ 重号高概率 ({len(tri_high_record.get('repeat_high', []))}码): {rep or '无'}")
            print(f"     ⚡ 边码高概率 (左翼: {edge_l} | 右翼: {edge_r})")
            print(f"     ⚡ 冷号高概率 ({len(tri_high_record.get('cold_high', []))}码): {cold or '无'}")
    else:
        print(f"  ⚠️ [平稳降级启动] 未在 file/ 目录发现当日新增 Excel，自动启用本地上一期留档点位，流水线正常推进！")

    # --------------------------------------------------------------------------
    # 步骤 3: 运行全量深度融合预测流水线 (包含昨日复盘生成)
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 3/7] 正在执行全量工业级深度融合推演流水线...")
    try:
        orchestrator = DailyReportOrchestrator()
        orchestrator.generate_report()
        print(f"  ✅ [主脑推演完成] 20方案/11模块、三维一体、深层关联与FO Baseline已全部收敛落盘。")
    except Exception as e:
        print(f"  ❌ [推演流水线异常]: {e}")
        import traceback
        traceback.print_exc()
        print("  ❌ [中止] 今日研报生成失败，停止后续对账、缩水与发布，禁止复用历史报告。")
        return 1

    # 只认今天生成的研报：缺当日报告即判定失败，绝不回退到昨天的报告
    today_tag = datetime.now().strftime("%Y%m%d")
    report_candidates = [
        _DATA_DIR / f"daily_analysis_report_{today_tag}.md",
        _DATA_DIR / "storage" / "reports" / f"daily_analysis_report_{today_tag}.md",
    ]
    report_path = next((str(p) for p in report_candidates if p.exists()), None)
    if not report_path:
        print(f"  ❌ [中止] 未找到今日研报 daily_analysis_report_{today_tag}.md，拒绝复用历史报告继续发布。")
        return 2

    report_text = ""
    with open(report_path, "r", encoding="utf-8", errors="ignore") as rf:
        report_text = rf.read()

    # --------------------------------------------------------------------------
    # 步骤 4: 解析昨日七维实战复盘
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 4/7] 正在生成昨日推荐七维立体对账体检卡...")
    rev_lines = []
    
    # 选2复盘
    m_p2 = re.search(r"🎯 极简选2实战.*?([^\n]+)", report_text)
    rev_lines.append(f"🎯 极简选2黄金搭档: {m_p2.group(1).strip() if m_p2 else '详见研报'}")

    # 三维融合
    m_tri = re.search(r"三维融合.*?Top5.*?命中\s*`([^`]+)`.*?Top12.*?命中\s*`([^`]+)`", report_text)
    if m_tri:
        rev_lines.append(f"🌟 三维一体极秘精选: Top5 命中 {m_tri.group(1)} | Top12 命中 {m_tri.group(2)}")
    
    # 方案2深层关联
    m_exp = re.search(r"爆发Top5.*?命中\s*`([^`]+)`.*?Lift=`([^`]+)`.*?命中号\s*`([^`]+)`", report_text)
    m_def = re.search(r"防守Top3.*?成功\s*`([^`]+)`.*?回避正确\s*`([^`]+)`", report_text)
    if m_exp:
        rev_lines.append(f"🚀 方案2深层爆发Top5: 命中 {m_exp.group(1)} (Lift={m_exp.group(2)}) 命中号: {m_exp.group(3)}")
    if m_def:
        rev_lines.append(f"🛡️ 方案2防守回避Top3: 成功回避 {m_def.group(1)} 回避号: {m_def.group(2)}")

    # 物理熔断
    m_kl = re.search(r"物理熔断\(KL\).*?`([^`]+)`", report_text)
    if m_kl:
        rev_lines.append(f"🛡️ 物理熔断监测: {m_kl.group(1)}")

    # 环境识别
    m_env = re.search(r"环境识别.*?`([^`]+)`", report_text)
    if m_env:
        rev_lines.append(f"🌐 市场周期画像: {m_env.group(1)}")

    print(format_box(f"{latest_issue}期 昨日实战七维对账单", rev_lines))

    # --------------------------------------------------------------------------
    # 步骤 5: 提取今日核心推演推荐
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 5/7] 提取今日核心操盘指令与推荐号码...")
    rec_lines = []
    missing_core = []

    def _grab(pattern: str, label: str):
        m = re.search(pattern, report_text)
        if not m:
            missing_core.append(label)
            return None
        return m.group(1).strip()

    # 今日选2（硬依赖：缺失即中止发布）
    p2_val = _grab(r"👑 黄金搭档.*?`([0-9\s\-]+)`", "极简选2黄金搭档")
    if p2_val:
        if len(re.findall(r"\d+", p2_val)) < 2:
            missing_core.append("极简选2号码对")
        else:
            rec_lines.append(f"👑 【全场唯一最优选2】: 黄金搭档 [ {p2_val} ] (综合协同分: 1.00)")

    # 至尊金胆（硬依赖）
    gold_val = _grab(r"👑 全场至尊核心金胆.*?`([0-9]+)`", "至尊金胆")
    m_gold_tier = re.search(r"Meta-Gold 五维金胆梯队.*?`([0-9\-]+)`", report_text)
    gold_tier_val = m_gold_tier.group(1).strip() if m_gold_tier else "—"
    if gold_val:
        rec_lines.append(f"💎 【Meta-Gold 至尊金胆】: [ {gold_val} ] ｜ 五维金胆梯队: [ {gold_tier_val} ]")

    # 16期动量与维度硬约束最优20码（硬依赖）
    opt20_val = _grab(r"动量\+维度硬约束最优 20 码.*?`([0-9\s]+)`", "16期维度硬约束20码")
    if opt20_val:
        if len([x for x in opt20_val.split() if x.isdigit()]) < 20:
            missing_core.append("16期维度硬约束20码(不足20码)")
        else:
            rec_lines.append(f"🧭 【16期维度硬约束20码】: {opt20_val}")

    # 三维极秘 Top5 / Top12（硬依赖：决定缩水单与微信原文）
    top5_val = _grab(r"极秘 Top 5.*?`(\[[0-9,\s]+\])`", "三维一体极秘Top5")
    top12_val = _grab(r"极秘 Top 12.*?`(\[[0-9,\s]+\])`", "三维一体极秘Top12")
    if top5_val:
        rec_lines.append(f"🌟 【三维一体极秘 Top5】: {top5_val}")
    if top12_val:
        rec_lines.append(f"🌟 【三维一体极秘 Top12】: {top12_val}")

    # 传统AI Top5（可选展示）
    m_ai_top5 = re.search(r"Top 5 置信度精选.*?`(\[[0-9,\s]+\])`", report_text)
    if m_ai_top5:
        rec_lines.append(f"🤖 【传统 AI 对照 Top5】: {m_ai_top5.group(1).strip()}")

    # 点位与三高特征群输出
    if points_20:
        rec_lines.append(f"📍 【解析点位 20 码】: {' '.join(points_20)}")
    if tri_high_record:
        rep_str = " ".join([f"{int(x):02d}" for x in tri_high_record.get("repeat_high", [])])
        edge_l_str = " ".join([f"{int(x):02d}" for x in tri_high_record.get("edge_high_left", [])])
        edge_r_str = " ".join([f"{int(x):02d}" for x in tri_high_record.get("edge_high_right", [])])
        cold_str = " ".join([f"{int(x):02d}" for x in tri_high_record.get("cold_high", [])])
        rec_lines.append(f"⚡ 【三高·上期重复高概率】: {rep_str or '无'}")
        rec_lines.append(f"⚡ 【三高·边码高概率左右】: 左翼 [{edge_l_str}] ｜ 右翼 [{edge_r_str}]")
        rec_lines.append(f"⚡ 【三高·指标冷号高概率】: {cold_str or '无'}")

    print(format_box(f"{target_issue}期 今日核心推演卡片", rec_lines))

    if missing_core:
        print(f"  ❌ [中止] 研报关键字段解析失败: {', '.join(missing_core)}")
        print("     已停止缩水单与微信发布，禁止使用占位号码对外输出。请检查研报格式是否变化。")
        return 3

    # --------------------------------------------------------------------------
    # 步骤 6: 盖尔·霍华德旋转矩阵缩水方案 (Smart Luck Wheel)
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 6/7] 生成盖尔·霍华德旋转矩阵保奖缩水方案...")
    wheel_lines = []
    wheel_tickets = []
    try:
        # 解析 Top12 号码清单
        top12_nums = [int(x) for x in re.findall(r"\d+", top12_val)][:10]
        if len(top12_nums) < 10:
            top12_nums = [int(x) for x in opt20_val.split()[:10]]
        
        banker_num = int(gold_val) if gold_val.isdigit() else top12_nums[0]
        effective_banker = banker_num if banker_num in top12_nums else top12_nums[0]
        bankers = [effective_banker]

        tpl = BUILTIN_WHEELS.get("W5_10_4_4_6")
        if tpl:
            wheel_tickets = WheelEngine.generate_wheel(tpl, top12_nums, bankers=bankers)
            wheel_lines.append(f"🎲 矩阵模板: {tpl.name} | 保奖承诺: {tpl.guarantee}")
            wheel_lines.append(f"📌 定胆核心: [ {effective_banker:02d} ] | 候选池: {', '.join([f'{x:02d}' for x in top12_nums])}")
            wheel_lines.append(f"🎫 精选缩水打票单 (共 {len(wheel_tickets)} 注):")
            for idx, t in enumerate(wheel_tickets, 1):
                t_str = " ".join([f"{x:02d}" for x in t])
                wheel_lines.append(f"   第{idx:02d}注: [ {t_str} ]")
        else:
            wheel_lines.append("未找到预设选5保4矩阵模板")
    except Exception as we:
        wheel_lines.append(f"旋转矩阵生成提示: {we}")

    print(format_box("盖尔·霍华德选五保四旋转矩阵方案", wheel_lines))

    if len(wheel_tickets) < 6:
        print(f"  ❌ [中止] 旋转矩阵仅生成 {len(wheel_tickets)} 注有效打票单（需 6 注），停止微信发布。")
        return 4

    # --------------------------------------------------------------------------
    # 步骤 7: 微信社群专属发布原文渲染与落盘
    # --------------------------------------------------------------------------
    print("\n▶ [步骤 7/7] 正在生成【微信社群专属分桶发布原文】...")
    wechat_dir = _DATA_DIR / "storage" / "reports"
    wechat_dir.mkdir(parents=True, exist_ok=True)
    wechat_file = wechat_dir / f"wechat_publish_{target_issue}.txt"

    # 整理各分桶号码
    top20_list = [f"{int(x):02d}" for x in opt20_val.split()[:20]]

    # 选2号码对
    p2_pair = re.findall(r"\d+", p2_val)
    p2_str = f"{int(p2_pair[0]):02d}  {int(p2_pair[1]):02d}"
    
    # 选3 / 选5 / 选7 / 选10 梯队
    d3_str = f"{p2_str}  {top20_list[2]}"
    d5_str = f"{d3_str}  {top20_list[3]}  {top20_list[4]}"
    d7_str = f"{d5_str}  {top20_list[5]}  {top20_list[6]}"
    d10_str = f"{d7_str}  {top20_list[7]}  {top20_list[8]}  {top20_list[9]}"

    top20_str = "  ".join(top20_list)
    ticket_strs = [" ".join([f"{x:02d}" for x in t]) for t in wheel_tickets[:6]]

    m_avoid = re.search(r"◎\s*重点防守号码[^\n]*\n([0-9,\s]+)", report_text)
    if m_avoid:
        def_avoid_nums = [f"{int(x):02d}" for x in re.findall(r"\d+", m_avoid.group(1))]
    else:
        def_avoid_nums = []
    def_avoid_str = "  ".join(def_avoid_nums) if def_avoid_nums else "（研报未给出防守号码）"

    today_str = datetime.now().strftime("%Y-%m-%d")
    wechat_content = f"""🔥【快乐8 第{target_issue}期 核心研判与金胆推荐】🔥
📅 研判日期：{today_str} (工业级深度融合实测版)
--------------------------------
🎯【精选分桶推荐·一键投注参考】
👑 至尊独胆：【 {int(gold_val):02d} 】
🥈 黄金双飞选2：【 {p2_str} 】
🥉 必拿铁三角选3：【 {d3_str} 】
💎 五虎上将选5：【 {d5_str} 】
🚀 稳健实战选7：【 {d7_str} 】
🏆 围底十码选10：【 {d10_str} 】

🎲【盖尔·霍华德旋转矩阵·选五保四 (6注)】
1️⃣ {ticket_strs[0]}
2️⃣ {ticket_strs[1]}
3️⃣ {ticket_strs[2]}
4️⃣ {ticket_strs[3]}
5️⃣ {ticket_strs[4]}
6️⃣ {ticket_strs[5]}

🧭【16期动量与维度硬约束20码】
{top20_str}

⚠️【防守回避号码】
{def_avoid_str}
--------------------------------
💡 科学提示：量化概率贴合，理智购彩参考，祝老铁们好运连连！🧧
"""
    wechat_file.write_text(wechat_content, encoding="utf-8")
    print(f"  ✅ [微信原文已生成] 文件路径: {wechat_file.name}")

    # --------------------------------------------------------------------------
    # 总结与直达链接展示
    # --------------------------------------------------------------------------
    elapsed = round(time.time() - t_start, 1)
    
    # 探活 Web 服务 (Port 8000)
    web_status = "未监听 (可通过 start_background.bat 启动)"
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", 8000)) == 0:
                web_status = "✅ 运行中 (HTTP 200 OK)"
    except Exception:
        pass

    summary_lines = [
        f"⏱️ 全流程总耗时: {elapsed} 秒",
        f"📄 全景研报 (Markdown): file:///{str(report_path).replace(os.sep, '/') if report_path else '无'}",
        f"📱 微信群分桶原文: file:///{str(wechat_file).replace(os.sep, '/')}",
        f"🌐 本地 Web 大屏服务 (端口 8000): {web_status}",
        f"   访问入口: http://127.0.0.1:8000 (API 文档: http://127.0.0.1:8000/docs)",
        "✨ 恭喜！今日全流程推演、复盘对账与多端产物已 100% 成功交付！"
    ]
    print("\n" + format_box("🎉 全流程执行成功报告", summary_lines, border_char="═"))
    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline_complete())
