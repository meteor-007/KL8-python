#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
3D彩票网站数据监控脚本
======================
功能：
  1. 抓取指定文章ID的页面数据（内容、发布时间、创建时间、更新时间）
  2. 每次抓取记录保存为一条日志，带时间戳
  3. 支持多次抓取对比，自动检测数据是否发生变化
  4. 支持手动单次抓取 或 定时自动抓取模式

使用方法：
  方式1 - 手动单次抓取（推荐配合闹钟使用）:
    python data_monitor.py grab 145
    python data_monitor.py grab 145 19:00

  方式2 - 定时自动抓取（到点自动执行）:
    python data_monitor.py auto 145 19:00 21:14 21:25

  方式3 - 查看今天的抓取记录:
    python data_monitor.py show 145

  方式4 - 对比今天的所有抓取记录:
    python data_monitor.py diff 145

数据保存在: <项目根目录>/records/
日志文件名: {文章ID}_{日期}.jsonl  (每行一个JSON记录)
"""

import sys
import os
import io
import json
import time
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 修复 Windows PowerShell 中文输出编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==================== 配置 ====================
BASE_URL = "http://abc1984.m.wd8989.com/nd.jsp?id={}&_sc=3"
RECORD_DIR = Path(__file__).resolve().parent / "records"
TZ_BEIJING = timezone(timedelta(hours=8))


# ==================== 核心抓取函数 ====================
def fetch_article(article_id):
    """
    抓取文章详情页，提取完整数据。
    返回 dict 包含: id, title, summary, content, date, createTime, updateTime, http_update_time, fetch_time
    """
    url = BASE_URL.format(article_id)

    # 用 curl 下载页面 (自动处理 gzip), 带超时防止站点无响应时永久阻塞
    try:
        result = subprocess.run(
            ['curl.exe', '-s', '--compressed', '--max-time', '10', '-D', '-', url],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=20
        )
    except (FileNotFoundError, OSError) as e:
        # 系统缺少 curl.exe 或无法启动: 返回明确错误而非崩溃
        return {
            'error': f'curl 执行失败(可能未安装 curl): {e}',
            'fetch_time': datetime.now(TZ_BEIJING).isoformat(),
            'article_id': article_id,
        }
    raw_output = result.stdout

    # 分离 HTTP 头和 HTML body
    header_body_split = raw_output.split('\r\n\r\n', 1)
    if len(header_body_split) == 2:
        headers_raw, html = header_body_split
    else:
        headers_raw, html = '', raw_output

    # 提取 HTTP 头中的 Update-Time
    http_update_time = None
    for line in headers_raw.split('\n'):
        if line.lower().startswith('update-time:'):
            try:
                http_update_time = int(line.split(':')[1].strip())
            except ValueError:
                pass
            break

    # 提取 __INITIAL_STATE__ JSON
    start_marker = 'window.__INITIAL_STATE__ = '
    start_idx = html.find(start_marker)
    if start_idx == -1:
        return {
            'error': '未找到 __INITIAL_STATE__',
            'fetch_time': datetime.now(TZ_BEIJING).isoformat(),
            'article_id': article_id,
        }

    try:
        json_start = html.index('{', start_idx)
    except ValueError:
        # 页面格式变化: 找到标记但无 JSON 起始, 返回明确错误而非崩溃
        return {
            'error': '__INITIAL_STATE__ 后未找到 JSON 起始 {',
            'fetch_time': datetime.now(TZ_BEIJING).isoformat(),
            'article_id': article_id,
        }

    # 字符串感知的括号匹配
    depth = 0
    in_string = False
    escape = False
    json_end = json_start

    for i in range(json_start, len(html)):
        ch = html[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                json_end = i + 1
                break

    try:
        state = json.loads(html[json_start:json_end])
    except json.JSONDecodeError as e:
        return {
            'error': f'JSON解析失败: {e}',
            'fetch_time': datetime.now(TZ_BEIJING).isoformat(),
            'article_id': article_id,
        }

    # 提取文章信息
    mod = state.get('currentPageModuleIdMap', {}).get('27', {})
    news_info = mod.get('renderOptions', {}).get('newsInfo', {})

    def ts_to_str(ts_ms):
        """毫秒时间戳转北京时间字符串"""
        if not ts_ms:
            return None
        return datetime.fromtimestamp(ts_ms / 1000, TZ_BEIJING).strftime('%Y-%m-%d %H:%M:%S')

    def ts_sec_to_str(ts_s):
        """秒时间戳转北京时间字符串"""
        if not ts_s:
            return None
        return datetime.fromtimestamp(ts_s, TZ_BEIJING).strftime('%Y-%m-%d %H:%M:%S')

    record = {
        'article_id': article_id,
        'fetch_time': datetime.now(TZ_BEIJING).strftime('%Y-%m-%d %H:%M:%S'),
        'fetch_timestamp': int(time.time()),
        'title': news_info.get('title', ''),
        'summary': news_info.get('summary', ''),
        'content': news_info.get('content', ''),
        'date': news_info.get('date', 0),
        'date_str': ts_to_str(news_info.get('date', 0)),
        'createTime': news_info.get('createTime', 0),
        'createTime_str': ts_to_str(news_info.get('createTime', 0)),
        'updateTime': news_info.get('updateTime', 0),
        'updateTime_str': ts_to_str(news_info.get('updateTime', 0)),
        'http_update_time': http_update_time,
        'http_update_time_str': ts_sec_to_str(http_update_time) if http_update_time else None,
        'views': news_info.get('views', 0),
        'hasPublished': news_info.get('hasPublished', False),
    }

    return record


# ==================== 记录保存 ====================
def save_record(record):
    """将抓取记录追加保存到 JSONL 文件"""
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(TZ_BEIJING).strftime('%Y%m%d')
    filepath = RECORD_DIR / f"{record['article_id']}_{today}.jsonl"

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    return filepath


# ==================== 命令: grab ====================
def cmd_grab(article_id, scheduled_time=None):
    """手动抓取一次数据"""
    now = datetime.now(TZ_BEIJING)

    if scheduled_time:
        # 等待到指定时间
        target_hour, target_min = map(int, scheduled_time.split(':'))
        target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        if target < now:
            print(f"⚠ 指定时间 {scheduled_time} 已过，立即执行抓取")
        else:
            wait_seconds = (target - now).total_seconds()
            print(f"⏰ 等待到 {scheduled_time} 执行抓取（还需等待 {wait_seconds:.0f} 秒）...")
            time.sleep(wait_seconds)

    print(f"\n{'='*60}")
    print(f"  开始抓取文章 ID={article_id}")
    print(f"  当前时间: {datetime.now(TZ_BEIJING).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    record = fetch_article(article_id)

    if 'error' in record:
        print(f"❌ 抓取失败: {record['error']}")
        return

    filepath = save_record(record)

    print(f"\n📊 抓取结果:")
    print(f"  文章ID:     {record['article_id']}")
    print(f"  标题:       {record['title']}")
    print(f"  内容:       {record['summary']}")
    print(f"  发布时间:   {record['date_str']}")
    print(f"  创建时间:   {record['createTime_str']}")
    print(f"  更新时间:   {record['updateTime_str'] or '(无更新)'}")
    print(f"  HTTP更新:   {record['http_update_time_str'] or '(无)'}")
    print(f"  抓取时间:   {record['fetch_time']}")
    print(f"\n💾 记录已保存到: {filepath}")


# ==================== 命令: auto ====================
def cmd_auto(article_id, *times):
    """定时自动抓取，在指定的时间点执行"""
    if not times:
        print("❌ 请至少指定一个时间点，例如: python data_monitor.py auto 145 19:00 21:14 21:25")
        return

    print(f"\n{'='*60}")
    print(f"  定时监控模式 - 文章 ID={article_id}")
    print(f"  计划抓取时间点: {', '.join(times)}")
    print(f"{'='*60}")

    for i, t in enumerate(times):
        if i > 0:
            now = datetime.now(TZ_BEIJING)
            target_hour, target_min = map(int, t.split(':'))
            target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if target > now:
                wait = (target - now).total_seconds()
                print(f"\n⏳ 下一次抓取: {t}，等待 {wait:.0f} 秒...")
                time.sleep(wait)

        cmd_grab(article_id, t)

    # 所有抓取完成后自动对比
    print(f"\n{'='*60}")
    print(f"  所有抓取完成，自动生成对比报告")
    print(f"{'='*60}")
    cmd_diff(article_id)


# ==================== 命令: show ====================
def cmd_show(article_id):
    """显示今天的所有抓取记录"""
    today = datetime.now(TZ_BEIJING).strftime('%Y%m%d')
    filepath = RECORD_DIR / f"{article_id}_{today}.jsonl"

    if not filepath.exists():
        print(f"❌ 今天还没有抓取记录 (文件不存在: {filepath})")
        return

    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                # 单行损坏(如写入中断)时跳过, 不阻断整个记录查看
                print(f"  ⚠ 跳过损坏记录: {line[:60]}...")
                continue

    print(f"\n{'='*60}")
    print(f"  文章 ID={article_id} 今天的抓取记录 ({len(records)} 条)")
    print(f"{'='*60}")

    for i, r in enumerate(records, 1):
        print(f"\n--- 第{i}次抓取 ---")
        print(f"  抓取时间:   {r.get('fetch_time', 'N/A')}")
        print(f"  标题:       {r.get('title', 'N/A')}")
        print(f"  内容:       {r.get('summary', 'N/A')}")
        print(f"  发布时间:   {r.get('date_str', 'N/A')}")
        print(f"  创建时间:   {r.get('createTime_str', 'N/A')}")
        print(f"  更新时间:   {r.get('updateTime_str', '(无更新)')}")
        print(f"  HTTP更新:   {r.get('http_update_time_str', '(无)')}")


# ==================== 命令: diff ====================
def cmd_diff(article_id):
    """对比今天的所有抓取记录，检测数据变化"""
    today = datetime.now(TZ_BEIJING).strftime('%Y%m%d')
    filepath = RECORD_DIR / f"{article_id}_{today}.jsonl"

    if not filepath.exists():
        print(f"❌ 今天还没有抓取记录")
        return

    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                # 单行损坏(如写入中断)时跳过, 不阻断整个记录对比
                print(f"  ⚠ 跳过损坏记录: {line[:60]}...")
                continue

    if len(records) < 2:
        print(f"\n⚠ 只有 {len(records)} 条记录，至少需要 2 条才能对比")
        cmd_show(article_id)
        return

    print(f"\n{'='*70}")
    print(f"  文章 ID={article_id} 数据变化对比报告 ({len(records)} 次抓取)")
    print(f"{'='*70}")

    # 对比关键字段
    fields = [
        ('summary',          '内容'),
        ('content',          '完整内容'),
        ('updateTime_str',   'updateTime'),
        ('http_update_time_str', 'HTTP更新时间'),
        ('createTime_str',   'createTime'),
        ('title',            '标题'),
        ('views',            '浏览量'),
    ]

    print(f"\n{'抓取时间':<22} {'内容':<30} {'updateTime':<22} {'变化'}")
    print("-" * 100)

    prev = None
    for r in records:
        fetch_t = r.get('fetch_time', 'N/A')
        summary = r.get('summary', 'N/A')
        upd_t = r.get('updateTime_str') or '(无更新)'
        http_upd = r.get('http_update_time_str') or '(无)'

        if prev is None:
            change = '(首次)'
        else:
            changes = []
            for field, label in fields:
                old_val = prev.get(field)
                new_val = r.get(field)
                if old_val != new_val:
                    changes.append(label)
            change = '🔴 变化: ' + ', '.join(changes) if changes else '✅ 无变化'

        print(f"{fetch_t:<22} {summary:<30} {upd_t:<22} {change}")
        prev = r

    # 详细变化
    print(f"\n{'='*70}")
    print(f"  详细字段变化:")
    print(f"{'='*70}")

    for i in range(1, len(records)):
        prev = records[i - 1]
        curr = records[i]
        has_change = False

        print(f"\n--- 第{i}次({prev['fetch_time']}) → 第{i+1}次({curr['fetch_time']}) ---")

        for field, label in fields:
            old_val = prev.get(field)
            new_val = curr.get(field)
            if old_val != new_val:
                has_change = True
                print(f"  🔴 {label}:")
                print(f"     旧: {old_val}")
                print(f"     新: {new_val}")

        if not has_change:
            print(f"  ✅ 所有字段均无变化")

    # 总结
    print(f"\n{'='*70}")
    print(f"  总结:")
    print(f"{'='*70}")
    total_changes = 0
    for i in range(1, len(records)):
        prev = records[i - 1]
        curr = records[i]
        for field, label in fields:
            if prev.get(field) != curr.get(field):
                total_changes += 1
                break

    if total_changes == 0:
        print(f"  ✅ 共 {len(records)} 次抓取，数据从未变化")
    else:
        print(f"  🔴 共 {len(records)} 次抓取，检测到 {total_changes} 次数据变化")

    # 最终状态
    last = records[-1]
    print(f"\n  最终数据:")
    print(f"    内容:       {last.get('summary', 'N/A')}")
    print(f"    创建时间:   {last.get('createTime_str', 'N/A')}")
    print(f"    更新时间:   {last.get('updateTime_str', '(无更新)')}")
    print(f"    最后抓取:   {last.get('fetch_time', 'N/A')}")


# ==================== 主入口 ====================
def print_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║          3D彩票网站数据监控脚本 - 使用说明               ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  【方式1】手动单次抓取（配合闹钟使用）                    ║
║  python data_monitor.py grab 145                         ║
║  → 立即抓取 ID=145 的数据                                ║
║                                                          ║
║  python data_monitor.py grab 145 19:00                   ║
║  → 等待到 19:00 再抓取                                   ║
║                                                          ║
║  【方式2】定时自动抓取（到点自动执行，推荐！）            ║
║  python data_monitor.py auto 145 19:00 21:14 21:25       ║
║  → 在 19:00、21:14、21:25 三个时间点自动抓取             ║
║  → 全部完成后自动生成对比报告                            ║
║                                                          ║
║  【方式3】查看今天的抓取记录                              ║
║  python data_monitor.py show 145                         ║
║                                                          ║
║  【方式4】对比今天的所有抓取记录                          ║
║  python data_monitor.py diff 145                         ║
║                                                          ║
║  数据保存在: d:\\Dpanqianyi\\Python-Project\\data\\records\\ ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print_help()
        return

    command = sys.argv[1].lower()

    if command == 'grab':
        if len(sys.argv) < 3:
            print("❌ 用法: python data_monitor.py grab <文章ID> [时间HH:MM]")
            return
        article_id = int(sys.argv[2])
        scheduled_time = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_grab(article_id, scheduled_time)

    elif command == 'auto':
        if len(sys.argv) < 4:
            print("❌ 用法: python data_monitor.py auto <文章ID> <时间1> [时间2] [时间3] ...")
            return
        article_id = int(sys.argv[2])
        times = sys.argv[3:]
        cmd_auto(article_id, *times)

    elif command == 'show':
        if len(sys.argv) < 3:
            print("❌ 用法: python data_monitor.py show <文章ID>")
            return
        article_id = int(sys.argv[2])
        cmd_show(article_id)

    elif command == 'diff':
        if len(sys.argv) < 3:
            print("❌ 用法: python data_monitor.py diff <文章ID>")
            return
        article_id = int(sys.argv[2])
        cmd_diff(article_id)

    else:
        print(f"❌ 未知命令: {command}")
        print_help()


if __name__ == '__main__':
    main()
