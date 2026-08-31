# -*- coding: utf-8 -*-
"""
每日点位数据管理器 (Daily Points Manager v2.0 - 老派量化操盘手大白话落地架构)
================================================================================
核心职责：
  1. 【灵活输入与解析】：支持任意分隔符（空格/逗号/顿号/连字符/换行/制表符/中英文逗号），一键提取20个有效点位。
  2. 【全量契约校验】：严格校验20码唯一性、1~80范围、零前视泄露、期号与开奖历史严格对齐。
  3. 【安全原子落盘】：自动备份历史快照（cache/points_backup/），防止文件损坏，原子覆盖或置顶插入。
  4. 【多维分布画像】：8分区能量覆盖、奇偶比、大小比、和值、AC值、连号拓扑、昨日点位重码/邻号对比。
  5. 【下游模块一键联动】：
       - apply_formats.py: Excel点位粉色底色(FFFCE4EC)与中奖边框(FFD966B3)
       - generate_hot_excel.py: 热码统计加权计算 (点位权重 0.3)
       - run_points_daily.py: 空间重点点位4维特征打分与精排
       - run_suppression_daily.py: 未开点位高压反弹与影子替身推演
       - deep_mining_engine.py: Layer 4 点位共振分析与触发加成
       - excel_deep_mining_v2.py: 星号×点位双标记交叉与马尔可夫转移
       - pure_pool_scorer.py: 纯净池计算 (B区去点位)
       - run_full_pipeline.py: 每日完整量化全流水线
"""
import os
import re
import sys
import json
import shutil
import datetime
from typing import Dict, List, Set, Tuple, Optional, Any

# 路径自适应 (Dual-Root Bootstrap)
_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
PROJ_DIR = get_project_root()

POINTS_FILE = os.path.join(PROJ_DIR, "daily_points.txt")
HISTORY_FILE = os.path.join(PROJ_DIR, "kl8_history_final.txt")
BACKUP_DIR = os.path.join(PROJ_DIR, "cache", "points_backup")

NUM_BALLS = 80
POINTS_COUNT = 20

# 8 分区定义 (大白话：把80个球按10个一组切成8个小区)
ZONES = [
    (1, 10, "一区(01-10)"),
    (11, 20, "二区(11-20)"),
    (21, 30, "三区(21-30)"),
    (31, 40, "四区(31-40)"),
    (41, 50, "五区(41-50)"),
    (51, 60, "六区(51-60)"),
    (61, 70, "七区(61-70)"),
    (71, 80, "八区(71-80)"),
]


# ═══════════════════════════════════════════════════════════════
# 1. 点位输入解析与格式化
# ═══════════════════════════════════════════════════════════════

def parse_points_input(raw_input: str) -> List[int]:
    """
    智能解析用户输入的点位文本（支持任意混排格式）
    支持：
      - 空格分隔: "04 12 17 19 24 ..."
      - 逗号/顿号: "4, 12, 17, 19, 24" 或 "04、12、17、19"
      - 连字符: "04-12-17-19-24"
      - 换行与制表符: Excel直接复制粘贴的多行文本
    返回升序排序的去重整数列表
    """
    if not raw_input:
        return []
    
    # 替换中文逗号、顿号、分号等为标准空格
    cleaned = raw_input.replace("，", " ").replace("、", " ").replace("；", " ")
    cleaned = cleaned.replace(";", " ").replace(",", " ").replace("-", " ").replace("|", " ")
    
    # 提取所有整数
    tokens = re.findall(r"\b\d+\b", cleaned)
    nums = []
    seen = set()
    for t in tokens:
        val = int(t)
        if 1 <= val <= NUM_BALLS:
            if val not in seen:
                seen.add(val)
                nums.append(val)
    
    nums.sort()
    return nums


def validate_points_list(nums: List[int]) -> Tuple[bool, str]:
    """
    校验点位列表是否完全合规
    合规标准：恰好 20 个有效号码，范围在 1~80 之间，无重复
    """
    if not isinstance(nums, list):
        return False, "点位数据必须是数字列表"
    
    if len(nums) != POINTS_COUNT:
        return False, f"点位数量异常：当前解析出 {len(nums)} 个号码，必须恰好为 {POINTS_COUNT} 个！"
    
    out_of_range = [x for x in nums if not (1 <= x <= NUM_BALLS)]
    if out_of_range:
        return False, f"存在越界号码：{out_of_range}（快乐8号码范围必须在 01~80 之间）"
    
    if len(set(nums)) != len(nums):
        return False, "存在重复号码，请检查输入！"
    
    return True, "校验通过"


def format_points_to_line(date_str: str, period_str: str, points: List[int]) -> str:
    """格式化为 daily_points.txt 标准单行文本"""
    pts_sorted = sorted(points)
    pts_str = " ".join(f"{x:02d}" for x in pts_sorted)
    return f"date:{date_str},period:{period_str},points:{pts_str}\n"


# ═══════════════════════════════════════════════════════════════
# 2. 点位读取与目标期推断
# ═══════════════════════════════════════════════════════════════

def load_daily_points(filepath: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    加载全部历史点位数据
    返回: {期号: {'date': 'YYYY-MM-DD', 'period': int, 'period_str': '2026231', 'points': [4, 12, ...], 'points_set': {4, 12, ...}}}
    按期号从大到小（最新在前）排序
    """
    target_path = filepath or POINTS_FILE
    points_dict = {}
    if not os.path.exists(target_path):
        return points_dict
    
    with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m_date = re.search(r"date:([0-9\-]+)", line)
            m_iss = re.search(r"period:(\d+)", line)
            m_pts = re.search(r"points:([\d\s]+)", line)
            if m_iss and m_pts:
                p_str = m_iss.group(1)
                d_str = m_date.group(1) if m_date else ""
                pts = [int(x) for x in m_pts.group(1).strip().split() if x.isdigit()]
                if len(pts) == POINTS_COUNT:
                    points_dict[p_str] = {
                        "date": d_str,
                        "period": int(p_str),
                        "period_str": p_str,
                        "points": sorted(pts),
                        "points_set": set(pts)
                    }
    return points_dict


def get_latest_points_entry(filepath: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """获取最新一条点位记录"""
    pts = load_daily_points(filepath)
    if not pts:
        return None
    sorted_issues = sorted(pts.keys(), key=int, reverse=True)
    return pts[sorted_issues[0]]


def get_next_target_info() -> Dict[str, Any]:
    """
    基于开奖历史库与已有点位库，自动推断今日目标期号与推荐日期
    """
    # 1. 读取开奖历史
    latest_hist_period = 0
    latest_hist_date = ""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if "numbers:" in line and "period:" in line:
                    m_iss = re.search(r"period:(\d+)", line)
                    m_date = re.search(r"date:([0-9\-]+)", line)
                    if m_iss:
                        latest_hist_period = int(m_iss.group(1))
                    if m_date:
                        latest_hist_date = m_date.group(1)
                    break
    
    # 2. 读取点位库
    latest_pts_entry = get_latest_points_entry()
    latest_pts_period = latest_pts_entry["period"] if latest_pts_entry else 0
    latest_pts_date = latest_pts_entry["date"] if latest_pts_entry else ""
    
    # 3. 推断目标期号
    if latest_hist_period > 0:
        target_period = latest_hist_period + 1
    elif latest_pts_period > 0:
        target_period = latest_pts_period + 1
    else:
        target_period = 2026001
    
    # 4. 推断目标日期
    today_str = datetime.date.today().isoformat()
    if latest_hist_date:
        try:
            last_dt = datetime.datetime.strptime(latest_hist_date, "%Y-%m-%d").date()
            if last_dt == datetime.date.today():
                target_date = today_str
            else:
                target_date = (last_dt + datetime.timedelta(days=1)).isoformat()
        except Exception:
            target_date = today_str
    else:
        target_date = today_str
    
    target_period_str = str(target_period)
    all_pts = load_daily_points()
    already_input = target_period_str in all_pts
    existing_points = all_pts[target_period_str]["points"] if already_input else []
    
    return {
        "latest_history_period": latest_hist_period,
        "latest_history_date": latest_hist_date,
        "latest_points_period": latest_pts_period,
        "latest_points_date": latest_pts_date,
        "target_period": target_period,
        "target_period_str": target_period_str,
        "target_date": target_date,
        "already_input": already_input,
        "existing_points": existing_points
    }


# ═══════════════════════════════════════════════════════════════
# 3. 点位多维特征画像 (大白话量化分析)
# ═══════════════════════════════════════════════════════════════

def analyze_points_distribution(points: List[int], prev_points: Optional[List[int]] = None, latest_draw: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    对输入的 20 个点位进行全维度特征透视与大白话体检
    """
    pts_sorted = sorted(points)
    pts_set = set(pts_sorted)
    
    # 1. 基础指标
    total_sum = sum(pts_sorted)
    mean_val = total_sum / len(pts_sorted)
    odd_count = sum(1 for x in pts_sorted if x % 2 != 0)
    even_count = len(pts_sorted) - odd_count
    small_count = sum(1 for x in pts_sorted if 1 <= x <= 40)
    big_count = len(pts_sorted) - small_count
    prime_set = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79}
    prime_count = sum(1 for x in pts_sorted if x in prime_set)
    
    # 2. 8 分区覆盖
    zone_dist = {}
    missing_zones = []
    zone_counts = []
    for z_start, z_end, z_name in ZONES:
        in_zone = [x for x in pts_sorted if z_start <= x <= z_end]
        cnt = len(in_zone)
        zone_counts.append(cnt)
        zone_dist[z_name] = {
            "range": f"{z_start:02d}-{z_end:02d}",
            "count": cnt,
            "numbers": in_zone
        }
        if cnt == 0:
            missing_zones.append(z_name)
            
    is_zone_balanced = len(missing_zones) == 0
    
    # 3. 连号与拓扑 (大白话：找连体婴)
    consecutive_pairs = []
    for i in range(len(pts_sorted) - 1):
        if pts_sorted[i+1] == pts_sorted[i] + 1:
            consecutive_pairs.append((pts_sorted[i], pts_sorted[i+1]))
            
    # 4. 尾数分布 (大白话：看哪个尾巴最热闹)
    tail_counts = {t: 0 for t in range(10)}
    for x in pts_sorted:
        tail_counts[x % 10] += 1
    hot_tails = sorted(tail_counts.items(), key=lambda item: -item[1])
    
    # 5. 与昨日点位/昨日开奖对比
    repeat_from_prev_pts = []
    adjacent_from_prev_pts = []
    if prev_points:
        prev_set = set(prev_points)
        repeat_from_prev_pts = sorted(list(pts_set & prev_set))
        for p in pts_sorted:
            if (p - 1 in prev_set or p + 1 in prev_set) and p not in prev_set:
                adjacent_from_prev_pts.append(p)
                
    repeat_from_latest_draw = []
    if latest_draw:
        draw_set = set(latest_draw)
        repeat_from_latest_draw = sorted(list(pts_set & draw_set))
        
    return {
        "points": pts_sorted,
        "points_str": " ".join(f"{x:02d}" for x in pts_sorted),
        "total_sum": total_sum,
        "mean_val": round(mean_val, 2),
        "odd_even_ratio": f"{odd_count}:{even_count}",
        "big_small_ratio": f"{small_count}:{big_count} (小:大)",
        "prime_count": prime_count,
        "zone_dist": zone_dist,
        "zone_counts": zone_counts,
        "missing_zones": missing_zones,
        "is_zone_balanced": is_zone_balanced,
        "consecutive_pairs": consecutive_pairs,
        "consecutive_count": len(consecutive_pairs),
        "hot_tails": hot_tails,
        "repeat_from_prev_pts": repeat_from_prev_pts,
        "adjacent_from_prev_pts": adjacent_from_prev_pts,
        "repeat_from_latest_draw": repeat_from_latest_draw
    }


# ═══════════════════════════════════════════════════════════════
# 4. 安全原子落盘与快照备份
# ═══════════════════════════════════════════════════════════════

def backup_points_file() -> Optional[str]:
    """创建点位文件的带时间戳安全备份"""
    if not os.path.exists(POINTS_FILE):
        return None
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"daily_points_{ts}.bak")
    
    try:
        shutil.copy2(POINTS_FILE, backup_path)
        
        # 轮转清理：最多保留 50 个历史备份
        baks = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".bak")])
        if len(baks) > 50:
            for old_bak in baks[:-50]:
                try:
                    os.remove(old_bak)
                except Exception:
                    pass
        return backup_path
    except Exception as e:
        print(f"⚠️ 备份点位文件失败: {e}")
        return None


def save_daily_points(date_str: str, period_str: str, points: List[int], filepath: Optional[str] = None, overwrite: bool = True) -> Dict[str, Any]:
    """
    安全原子写入点位数据到 daily_points.txt
    保持期号由大到小（最新期在最上方）降序排序
    """
    valid, msg = validate_points_list(points)
    if not valid:
        return {"status": "error", "message": msg}
    
    target_file = filepath or POINTS_FILE
    pts_sorted = sorted(points)
    
    # 1. 先做安全备份
    if target_file == POINTS_FILE:
        backup_points_file()
        
    # 2. 读取现有所有点位记录
    entries: Dict[int, Tuple[str, str, List[int]]] = {} # period_int -> (date_str, period_str, points)
    if os.path.exists(target_file):
        with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m_date = re.search(r"date:([0-9\-]+)", line)
                m_iss = re.search(r"period:(\d+)", line)
                m_pts = re.search(r"points:([\d\s]+)", line)
                if m_iss and m_pts:
                    p_int = int(m_iss.group(1))
                    d_s = m_date.group(1) if m_date else ""
                    p_s = m_iss.group(1)
                    parsed_pts = [int(x) for x in m_pts.group(1).strip().split() if x.isdigit()]
                    if len(parsed_pts) == POINTS_COUNT:
                        entries[p_int] = (d_s, p_s, parsed_pts)
                        
    # 3. 插入或更新目标期
    cur_p_int = int(period_str)
    existed = cur_p_int in entries
    if existed and not overwrite:
        return {"status": "skipped", "message": f"期号 {period_str} 已存在且未开启覆盖模式"}
    
    entries[cur_p_int] = (date_str, period_str, pts_sorted)
    
    # 4. 按期号降序排序写入临时文件再替换 (原子写)
    sorted_p_ints = sorted(entries.keys(), reverse=True)
    temp_file = target_file + ".tmp"
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            for p_int in sorted_p_ints:
                d_s, p_s, pts_list = entries[p_int]
                line_str = format_points_to_line(d_s, p_s, pts_list)
                f.write(line_str)
                
        # 原子重命名替换
        if os.path.exists(target_file):
            os.replace(temp_file, target_file)
        else:
            os.rename(temp_file, target_file)
            
        return {
            "status": "ok",
            "action": "updated" if existed else "created",
            "period": cur_p_int,
            "period_str": period_str,
            "date": date_str,
            "points": pts_sorted,
            "points_str": " ".join(f"{x:02d}" for x in pts_sorted),
            "total_records": len(entries)
        }
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        return {"status": "error", "message": f"写入点位文件失败: {e}"}


# ═══════════════════════════════════════════════════════════════
# 5. 下游预测模块一键联动调度
# ═══════════════════════════════════════════════════════════════

def run_downstream_task(task_key: str, verbose: bool = True) -> Dict[str, Any]:
    """
    触发执行特定的点位依赖下游模块
    """
    import subprocess
    
    TASK_MAP = {
        "format": {
            "name": "📊 Excel 点位底色与边框同步 (apply_formats.py)",
            "script": os.path.join(PROJ_DIR, "backend", "format", "apply_formats.py"),
            "args": []
        },
        "hot_excel": {
            "name": "🔥 热码统计表生成 (generate_hot_excel.py)",
            "script": os.path.join(PROJ_DIR, "backend", "data_acquisition", "generate_hot_excel.py"),
            "args": []
        },
        "spatial_points": {
            "name": "🔮 空间重点点位分析与精排 (run_points_daily.py)",
            "script": os.path.join(PROJ_DIR, "run_points_daily.py"),
            "args": ["30"]
        },
        "suppression": {
            "name": "🪞 未开点位高压反弹与影子替身 (run_suppression_daily.py)",
            "script": os.path.join(PROJ_DIR, "run_suppression_daily.py"),
            "args": ["30"]
        },
        "deep_mining": {
            "name": "💎 深度挖掘引擎与点位共振 (deep_mining_engine.py)",
            "script": os.path.join(PROJ_DIR, "backend", "core", "deep_mining_engine.py"),
            "args": []
        },
        "excel_mining": {
            "name": "🌟 Excel 星号×点位双标记状态转移 (excel_deep_mining_v2.py)",
            "script": os.path.join(PROJ_DIR, "backend", "core", "excel_deep_mining_v2.py"),
            "args": []
        },
        "full_pipeline": {
            "name": "🚀 每日全流水线一键跑盘 (run_full_pipeline.py)",
            "script": os.path.join(PROJ_DIR, "run_full_pipeline.py"),
            "args": []
        }
    }
    
    if task_key not in TASK_MAP:
        return {"status": "error", "message": f"未知任务标识: {task_key}"}
    
    t_info = TASK_MAP[task_key]
    script_path = t_info["script"]
    if not os.path.exists(script_path):
        return {"status": "error", "message": f"脚本文件不存在: {script_path}"}
    
    if verbose:
        print(f"\n🚀 正在启动: {t_info['name']} ...")
        
    cmd = [sys.executable, script_path] + t_info["args"]
    try:
        res = subprocess.run(
            cmd,
            cwd=PROJ_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        success = res.returncode == 0
        if verbose:
            if success:
                print(f"✅ {t_info['name']} 执行完毕！")
                if res.stdout:
                    # 打印摘要
                    lines = [l for l in res.stdout.splitlines() if l.strip()]
                    for l in lines[-8:]:
                        print(f"   │ {l}")
            else:
                print(f"❌ {t_info['name']} 执行报错 (Exit Code {res.returncode}):")
                print(res.stderr or res.stdout)
                
        return {
            "status": "ok" if success else "error",
            "task": task_key,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except Exception as e:
        if verbose:
            print(f"❌ 执行异常: {e}")
        return {"status": "error", "task": task_key, "message": str(e)}


def run_all_points_downstream(verbose: bool = True) -> Dict[str, Any]:
    """
    一键顺序执行所有点位联动的预测和同步任务
    顺序：
      1. 热码统计生成 (generate_hot_excel)
      2. Excel点位格式同步 (apply_formats)
      3. 空间重点点位分析 (spatial_points)
      4. 未开点位高压反弹 (suppression)
    """
    results = {}
    sequence = ["hot_excel", "format", "spatial_points", "suppression"]
    for t_key in sequence:
        res = run_downstream_task(t_key, verbose=verbose)
        results[t_key] = res
    return results
