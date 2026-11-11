# -*- coding: utf-8 -*-
"""
012路与质合数底层开奖数据全量提取与统计引擎
=====================================================
【业务背景与架构定位】:
本模块读取全部历史开奖数据 (kl8_history_final.txt)，为系统提供底层的分类特征数据：
1. 012路特征汇总表 (kl8_012_roads_summary.csv):
   - 0路 (余0): 3, 6, 9, 12, ... 共26个号码
   - 1路 (余1): 1, 4, 7, 10, ... 共27个号码
   - 2路 (余2): 2, 5, 8, 11, ... 共27个号码
   - 记录每期的012路数量比、具体号码分布及偏态。

2. 质数与合数特征汇总表 (kl8_prime_composite_summary.csv):
   - 质数池 (1-80内共22个标准素数): 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79
   - 01处理: 严格遵循数学定义 (1既非质数也非合数)，同时独立标记 是否包含01 字段供彩市传统口径对齐
   - 合数池 (共57个): 除1和质数外的所有正整数
   - 记录每期质数数量、合数数量、质合比、具体出号明细。

@author Antigravity Quantitative Team
@since 2026-09-03
"""

from backend.utils.paths import data_path, get_stats_dir
import os
import sys
import re
import csv
from typing import List, Dict, Tuple, Set

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PRIME_SET: Set[int] = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79
}

COMPOSITE_SET: Set[int] = {
    num for num in range(2, 81) if num not in PRIME_SET
}

def get_paths() -> Tuple[str, str, str]:
    """活数据统一落盘 storage/：历史在 raw，汇总表在 stats（禁止写根目录）。"""
    history_file = data_path('kl8_history_final.txt')
    stats_dir = get_stats_dir()
    road_out_file = os.path.join(stats_dir, 'kl8_012_roads_summary.csv')
    prime_out_file = os.path.join(stats_dir, 'kl8_prime_composite_summary.csv')
    return history_file, road_out_file, prime_out_file

def parse_history(history_file: str) -> List[Dict]:
    records: List[Dict] = []
    if not os.path.exists(history_file):
        raise FileNotFoundError(f'历史开奖数据文件不存在: {history_file}')

    with open(history_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            period_match = re.search(r'period:(\d+)', line)
            numbers_match = re.search(r'numbers:([\d-]+)', line)
            date_match = re.search(r'date:([\d-]+)', line)
            
            if period_match and numbers_match:
                period_str = period_match.group(1)
                num_tokens = numbers_match.group(1).split('-')
                numbers = sorted(int(token) for token in num_tokens if token.isdigit())
                if len(numbers) >= 15:
                    date_str = date_match.group(1) if date_match else ''
                    records.append({
                        'period': period_str,
                        'date': date_str,
                        'numbers': numbers,
                        'raw_str': '-'.join(f'{n:02d}' for n in numbers)
                    })
    return records

def _atomic_write_csv(path: str, headers: List[str], rows: List[List]) -> str:
    """写入 CSV；若目标被占用则落到 .latest，避免污染根目录或静默失败。"""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = f"{path}.__tmp_{os.getpid()}"
    try:
        with open(tmp, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        try:
            os.replace(tmp, path)
            return path
        except OSError:
            latest = path + '.latest'
            try:
                if os.path.exists(latest):
                    os.remove(latest)
            except OSError:
                pass
            os.replace(tmp, latest)
            print(f"⚠️ 目标被占用，已写入兜底文件: {latest}")
            return latest
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def generate_012_roads_data(records: List[Dict], target_paths: List[str]) -> Dict:
    headers = [
        '期号', '开奖日期', '0路个数', '1路个数', '2路个数', 
        '012路比', '0路号码', '1路号码', '2路号码', '开奖全号'
    ]
    rows = []
    stats_summary = {
        'total_periods': len(records),
        'sum_0': 0, 'sum_1': 0, 'sum_2': 0,
        'max_0': 0, 'min_0': 99,
        'max_1': 0, 'min_1': 99,
        'max_2': 0, 'min_2': 99
    }
    for rec in records:
        nums = rec['numbers']
        r0 = [n for n in nums if n % 3 == 0]
        r1 = [n for n in nums if n % 3 == 1]
        r2 = [n for n in nums if n % 3 == 2]
        c0, c1, c2 = len(r0), len(r1), len(r2)
        ratio_str = f'{c0}:{c1}:{c2}'
        
        stats_summary['sum_0'] += c0
        stats_summary['sum_1'] += c1
        stats_summary['sum_2'] += c2
        stats_summary['max_0'] = max(stats_summary['max_0'], c0)
        stats_summary['min_0'] = min(stats_summary['min_0'], c0)
        stats_summary['max_1'] = max(stats_summary['max_1'], c1)
        stats_summary['min_1'] = min(stats_summary['min_1'], c1)
        stats_summary['max_2'] = max(stats_summary['max_2'], c2)
        stats_summary['min_2'] = min(stats_summary['min_2'], c2)
        
        r0_str = ' '.join(f'{n:02d}' for n in r0)
        r1_str = ' '.join(f'{n:02d}' for n in r1)
        r2_str = ' '.join(f'{n:02d}' for n in r2)
        
        rows.append([
            rec['period'], rec['date'], c0, c1, c2, ratio_str,
            r0_str, r1_str, r2_str, rec['raw_str']
        ])
    for path in target_paths:
        _atomic_write_csv(path, headers, rows)
    return stats_summary

def generate_prime_composite_data(records: List[Dict], target_paths: List[str]) -> Dict:
    headers = [
        '期号', '开奖日期', '质数个数', '合数个数', '是否包含01', 
        '质合比', '质数号码', '合数号码', '特别说明', '开奖全号'
    ]
    rows = []
    stats_summary = {
        'total_periods': len(records),
        'sum_prime': 0, 'sum_comp': 0, 'count_01': 0,
        'max_prime': 0, 'min_prime': 99,
        'max_comp': 0, 'min_comp': 99
    }
    for rec in records:
        nums = rec['numbers']
        primes = [n for n in nums if n in PRIME_SET]
        composites = [n for n in nums if n in COMPOSITE_SET]
        has_01 = 1 in nums
        cp, cc = len(primes), len(composites)
        
        stats_summary['sum_prime'] += cp
        stats_summary['sum_comp'] += cc
        if has_01:
            stats_summary['count_01'] += 1
        stats_summary['max_prime'] = max(stats_summary['max_prime'], cp)
        stats_summary['min_prime'] = min(stats_summary['min_prime'], cp)
        stats_summary['max_comp'] = max(stats_summary['max_comp'], cc)
        stats_summary['min_comp'] = min(stats_summary['min_comp'], cc)
        
        note_str = '含01(既非质也非合)' if has_01 else '标准质合组合'
        ratio_str = f'{cp}:{cc}'
        p_str = ' '.join(f'{n:02d}' for n in primes)
        c_str = ' '.join(f'{n:02d}' for n in composites)
        
        rows.append([
            rec['period'], rec['date'], cp, cc,
            '是' if has_01 else '否', ratio_str,
            p_str, c_str, note_str, rec['raw_str']
        ])
    for path in target_paths:
        _atomic_write_csv(path, headers, rows)
    return stats_summary

def sync_roads_and_prime_stats(history_file: str = None, force_full: bool = False) -> Dict:
    """
    开奖数据同步联动引擎:
    自动比对 kl8_history_final.txt 与 kl8_prime_composite_summary.csv / kl8_012_roads_summary.csv
    若开奖历史更新，自动重新同步生成，确保期号、号码明细与开奖号码 100% 绝对一致。
    
    @param history_file 历史开奖文件路径 (可选)
    @param force_full 是否强制全量覆盖同步
    @return 同步结果状态字典
    """
    default_hist, road_out, prime_out = get_paths()
    hist_path = history_file or default_hist

    if not os.path.exists(hist_path):
        return {"status": "error", "message": f"开奖历史文件未找到: {hist_path}"}

    records = parse_history(hist_path)
    total_draws = len(records)
    if total_draws == 0:
        return {"status": "error", "message": "开奖历史记录为空"}

    latest_draw_period = str(records[0]['period'])

    # 校验现有 CSV 是否已是最新且期数一致（含 .latest 兜底）
    need_sync = force_full
    if not need_sync:
        for target_csv in [road_out, prime_out]:
            candidates = [target_csv, target_csv + '.latest']
            readable = next((p for p in candidates if os.path.exists(p)), None)
            if not readable:
                need_sync = True
                break
            try:
                with open(readable, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    first_row = next(reader, None)
                    if not first_row or str(first_row[0]) != latest_draw_period:
                        need_sync = True
                        break
            except Exception:
                need_sync = True
                break

    if not need_sync:
        return {
            "status": "up_to_date",
            "message": f"012路与质合汇总表已是最新 (期号 {latest_draw_period}, 共 {total_draws} 期)",
            "total_periods": total_draws,
            "latest_period": latest_draw_period
        }

    # 执行同步生成（仅写入 storage/stats，不再污染根目录）
    road_stats = generate_012_roads_data(records, [road_out])
    prime_stats = generate_prime_composite_data(records, [prime_out])

    print(f"✅ [012路与质合汇总表同步] 已成功与开奖号码保持一致！总期数: {total_draws} 期，最新期号: {latest_draw_period}")
    return {
        "status": "synced",
        "message": f"成功同步更新 012路与质合汇总数据 (共 {total_draws} 期，最新期号: {latest_draw_period})",
        "total_periods": total_draws,
        "latest_period": latest_draw_period,
        "road_stats": road_out,
        "prime_stats": prime_out
    }


def main():
    res = sync_roads_and_prime_stats(force_full=True)
    print(res["message"])


if __name__ == '__main__':
    main()

