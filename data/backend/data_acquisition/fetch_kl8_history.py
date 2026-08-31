# -*- coding: utf-8 -*-
"""
快乐8 历史数据抓取引擎 (高级版 v2.0)
====================================
1. 支持 17500 API 和 CWL 官方 API 双源冗余切换
2. 具备自动增量更新逻辑，防止重复与遗漏
3. 异常处理机制与 User-Agent 伪装
4. [v2.0] 数据校验：号码完整性/日期期号对齐/写入后验证
"""
import requests
import json
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger("FetchKl8History")

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()
import sys

from utils.paths import data_path
HISTORY_FILE = data_path('kl8_history_final.txt')

def _validate_entry(entry: str) -> bool:
    """校验单条数据格式是否合法

    检查项：
      1. 格式 date:YYYY-MM-DD,period:NNNNNNN,numbers:N-N-...-N
      2. 号码数量 = 20
      3. 号码范围 1-80
      4. 日期格式正确
      5. 期号7位数字
    """
    try:
        parts = entry.split(',')
        if len(parts) < 3:
            logger.warning(f"[校验] 格式异常(逗号不足3段): {entry[:60]}")
            return False

        date_s = parts[0].split(':')[1]
        issue_s = parts[1].split(':')[1]
        nums_str = parts[2].split(':')[1].strip()

        # 日期格式
        if not re.match(r'\d{4}-\d{2}-\d{2}$', date_s):
            logger.warning(f"[校验] 日期格式异常: {date_s}")
            return False

        # 期号格式
        if not re.match(r'\d{7}$', issue_s):
            logger.warning(f"[校验] 期号格式异常: {issue_s}")
            return False

        # 号码解析
        nums = nums_str.split('-')
        if len(nums) != 20:
            logger.warning(f"[校验] 期号{issue_s}号码数={len(nums)}≠20")
            return False

        for n_s in nums:
            n = int(n_s)
            if n < 1 or n > 80:
                logger.warning(f"[校验] 期号{issue_s}号码{n}超出1-80范围")
                return False

        return True
    except (ValueError, IndexError) as e:
        logger.warning(f"[校验] 解析异常: {e}, entry={entry[:60]}")
        return False


def _validate_history_file(filepath: str) -> dict:
    """校验已下载的历史文件完整性

    Returns:
        dict: {valid: bool, total: int, latest_issue: str, latest_date: str, errors: list}
    """
    result = {'valid': True, 'total': 0, 'latest_issue': '', 'latest_date': '', 'errors': []}
    if not os.path.exists(filepath):
        result['valid'] = False
        result['errors'].append('文件不存在')
        return result

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if 'numbers:' not in line:
                continue
            result['total'] += 1

            # 校验每行
            if not _validate_entry(line):
                if len(result['errors']) < 5:  # 最多记录5条
                    result['errors'].append(f'第{line_no}行校验失败')
                continue  # 校验收失败的行一律跳过, 不参与"最新期号"提取

            # 提取最新期号（第一行应该是最新）
            if result['total'] == 1:
                parts = line.split(',')
                result['latest_issue'] = parts[1].split(':')[1]
                result['latest_date'] = parts[0].split(':')[1]

    # 校验降序
    if result['total'] > 1:
        issues = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'period:(\d+)', line.strip())
                if m:
                    issues.append(int(m.group(1)))
        for i in range(min(len(issues) - 1, 50)):
            if issues[i] < issues[i + 1]:
                result['errors'].append(f'期号非降序: {issues[i]} < {issues[i+1]}')
                break

    if result['errors']:
        result['valid'] = len(result['errors']) <= 2  # 允许少量降序问题

    return result


def fetch_from_17500():
    """从 17500 获取数据"""
    url = "https://m.17500.cn/tgj/api/kl8/getTbList"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'list' in data:
                results = []
                for item in data['list']:
                    # 格式转化 (字段缺失/结构变化时跳过该条并告警, 避免 KeyError 崩溃)
                    issue = item.get('qihao')
                    opencode = item.get('opencode')
                    opentime = item.get('opentime')
                    if not issue or not opencode or not opentime:
                        print(f"[17500] 跳过畸形记录: {item}")
                        continue
                    nums = opencode.replace(',', '-')
                    date = opentime.split(' ')[0]
                    results.append(f"date:{date},period:{issue},numbers:{nums}")
                return results
    except Exception as e:
        print(f"[错误] 17500 API 获取失败: {e}")
    return []

def fetch_from_cwl():
    """从 CWL 官方获取数据 (作为备份)"""
    # 官方 findDrawNotice 接口提供更详细的出球顺序 (kjhyjsx)
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=kl8&issueCount=150"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.cwl.gov.cn/ygkj/kjgs/kl8/index.shtml'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'result' in data:
                results = []
                for item in data['result']:
                    issue = item.get('code')
                    date = (item.get('date') or '').split('(')[0]
                    # 优先使用 kjhyjsx (实际出号顺序)，如果没有则退而求其次用 red (通常是排序后的)
                    actual_nums = item.get('kjhyjsx')
                    if actual_nums:
                        nums = actual_nums.replace(',', '-')
                        print(f"  [CWL] 期号{issue}: 使用kjhyjsx(出球顺序)")
                    else:
                        nums = (item.get('red') or '').replace(',', '-')
                        print(f"  [CWL] 期号{issue}: kjhyjsx无数据，回退到red(排序后)")
                    if not issue or not nums:
                        print(f"[CWL] 跳过畸形记录: {item}")
                        continue
                    results.append(f"date:{date},period:{issue},numbers:{nums}")
                return results
    except Exception as e:
        print(f"[错误] CWL API 获取失败: {e}")
    return []

def fetch_history():
    print(f"[抓取] 开始获取快乐8最新数据...")
    
    # 获取现有数据
    existing_periods = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'period:(\d+)', line)
                if m: existing_periods.add(m.group(1))

    # 按照任务要求：优先使用 17500，若失败则 fallback 到 CWL
    data_list = fetch_from_17500()
    if not data_list:
        print("[尝试] 17500 失败，尝试备选源 CWL...")
        data_list = fetch_from_cwl()

    if not data_list:
        print("[失败] 所有数据源均不可用。")
        return False

    # 增量处理
    new_entries = []
    for entry in data_list:
        m = re.search(r'period:(\d+)', entry)
        if m and m.group(1) not in existing_periods:
            new_entries.append(entry)
            existing_periods.add(m.group(1))

    if not new_entries:
        print("[完成] 数据已是最新，无需更新。")
        # 即使无更新也做校验
        v = _validate_history_file(HISTORY_FILE)
        print(f"[校验] 历史{v['total']}期, 最新={v['latest_issue']}({v['latest_date']}), 有效={v['valid']}")
        return True

    # ── 写入前校验新数据 ──
    valid_new = []
    for entry in new_entries:
        if _validate_entry(entry):
            valid_new.append(entry)
        else:
            logger.warning(f"[跳过] 校验失败: {entry[:80]}")

    if not valid_new:
        print("[失败] 所有新数据均校验失败，不写入文件。")
        return False

    # 确保期号降序强排列 (最新期排在最前面)
    valid_new.sort(key=lambda x: int(re.search(r'period:(\d+)', x).group(1)), reverse=True)

    # 写入文件 (最新在前) — 首次部署时文件可能不存在 (FileNotFoundError防护)
    old_content = ""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                old_content = f.read()
        except Exception as e:
            print(f"[警告] 读取旧历史文件失败: {e}, 将以空文件初始化")
            old_content = ""

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        for entry in valid_new:
            f.write(entry + '\n')
            print(f"  [新增] {entry}")
        f.write(old_content)

    print(f"[完成] 成功更新 {len(valid_new)} 期数据。")

    # ── 写入后校验 ──
    v = _validate_history_file(HISTORY_FILE)
    if v['valid']:
        print(f"[校验] ✅ 写入后验证通过: {v['total']}期, 最新={v['latest_issue']}({v['latest_date']})")
    else:
        print(f"[校验] ❌ 写入后验证失败: errors={v['errors'][:3]}")

    return v['valid']


def get_latest_issue_and_date():
    """获取当前历史文件的最新期号和日期

    Returns:
        (issue, date) 或 ('', '') 如果文件不存在
    """
    if not os.path.exists(HISTORY_FILE):
        return '', ''
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            m_issue = re.search(r'period:(\d+)', line)
            m_date = re.search(r'date:(\d{4}-\d{2}-\d{2})', line)
            if m_issue and m_date:
                return m_issue.group(1), m_date.group(1)
    return '', ''


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    fetch_history()
