#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Incremental Data Service
Automatically fetch latest KL8 lottery data when service starts
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# API config for ordered data
BASE_URL = "https://m.17500.cn/tgj/api/kl8/getTbList"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://m.17500.cn/tgj/kl8/cqzs.html'
}

UNORDERED_URL = "http://data.17500.cn/kl8_desc.txt"


class IncrementalDataService:
    """Incremental data synchronization service"""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            current_file = Path(__file__).resolve()
            backend_root = current_file.parent.parent.parent
            self.data_dir = backend_root / "data"
        else:
            self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.ordered_xlsx = self.data_dir / "快8历史出球顺序.xlsx"
        self.unordered_txt = self.data_dir / "kl8_history_final.txt"
        self.incremental_log = self.data_dir / "incremental_update.log"

    def _log(self, message: str, level: str = "INFO"):
        """Log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"

        if level == "INFO":
            logger.info(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.debug(message)

        try:
            with open(self.incremental_log, 'a', encoding='utf-8') as f:
                f.write(log_message + "\n")
        except Exception as e:
            logger.warning(f"Failed to write log: {e}")

    def get_latest_local_date_from_txt(self) -> Optional[str]:
        """Get latest date from local TXT file"""
        if not self.unordered_txt.exists():
            self._log("Local unordered data file not found", "WARNING")
            return None

        try:
            with open(self.unordered_txt, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                return None

            last_line = lines[-1].strip()
            if not last_line and len(lines) > 1:
                last_line = lines[-2].strip()
            else:
                return None

            parts = last_line.split()
            if len(parts) >= 2:
                date = parts[0]
                self._log(f"Local latest date: {date}")
                return date
        except Exception as e:
            self._log(f"Error reading TXT file: {e}", "ERROR")

        return None

    def fetch_incremental_unordered_data(self) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch incremental unordered data"""
        try:
            self._log("Starting to fetch unordered data...")
            response = requests.get(UNORDERED_URL, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }, timeout=30)
            response.encoding = 'gb2312'

            if response.status_code != 200:
                self._log(f"Data source request failed: status {response.status_code}", "ERROR")
                return [], 0

            text_content = response.text
            self._log(f"Successfully fetched unordered data, size: {len(text_content)} chars")

            lines = text_content.strip().split('\n')
            all_data = []

            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 22:
                    issue = parts[0]
                    date = parts[1]
                    numbers = parts[2:22]

                    if len(date) == 10 and date[4] == '-' and date[7] == '-':
                        sorted_numbers = sorted([int(num) for num in numbers])
                        formatted_numbers = [f"{num:02d}" for num in sorted_numbers]
                        numbers_str = '-'.join(formatted_numbers)

                        all_data.append({
                            'date': date,
                            'issue': issue,
                            'numbers': numbers_str
                        })

            local_latest_date = self.get_latest_local_date_from_txt()

            if local_latest_date:
                new_data = [d for d in all_data if d['date'] > local_latest_date]
                self._log(f"Found {len(new_data)} new unordered records after {local_latest_date}")
            else:
                new_data = all_data
                self._log(f"Local data empty, will use all {len(new_data)} records")

            return new_data, len(new_data)

        except Exception as e:
            self._log(f"Error fetching unordered data: {e}", "ERROR")
            return [], 0

    def append_unordered_data(self, new_data: List[Dict[str, Any]]) -> bool:
        """Append new unordered data to TXT file"""
        if not new_data:
            self._log("No new unordered data to append")
            return True

        try:
            with open(self.unordered_txt, 'a', encoding='utf-8') as f:
                for item in new_data:
                    line = f"{item['date']} {item['issue']} {item['numbers']}\n"
                    f.write(line)

            self._log(f"Successfully appended {len(new_data)} unordered records")
            return True

        except Exception as e:
            self._log(f"Error appending unordered data: {e}", "ERROR")
            return False

    def fetch_incremental_ordered_data(self) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch incremental ordered data (ball sequence)"""
        try:
            self._log("Starting to fetch ordered data...")
            local_latest_date = self.get_latest_local_date_from_txt()

            all_ordered_data = []
            page = 1
            limit = 100

            while True:
                try:
                    params = {
                        'action': 'cqzs',
                        'page': page,
                        'limit': limit,
                        'orderby': 'asc',
                        'start_issue': 0,
                        'end_issue': 0,
                        'week': 'all'
                    }

                    response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                except requests.RequestException as e:
                    self._log(f"Request failed (page {page}): {e}", "ERROR")
                    break

                if not data or data.get('code') != 0:
                    self._log(f"API error (page {page})", "WARNING")
                    break

                records = data.get('data', {}).get('data', [])
                if not records:
                    self._log(f"All ordered data fetched ({page-1} pages)")
                    break

                for record in records:
                    issue = record.get('issue')
                    kjdate = record.get('kjdate')
                    cqzs_data = record.get('cqzs', {})
                    winnum_list = cqzs_data.get('winnum', [])

                    numbers = []
                    for num_str in winnum_list:
                        clean_num = num_str.replace('*', '')
                        try:
                            numbers.append(int(clean_num))
                        except ValueError:
                            pass

                    if len(numbers) == 20:
                        row_data = {
                            '开奖期号': issue,
                            '开奖日期': kjdate,
                            'numbers': numbers
                        }
                        all_ordered_data.append(row_data)

                self._log(f"Page {page}: fetched {len(records)} records")

                total = data.get('data', {}).get('total', 0)
                if page * limit >= total:
                    break

                page += 1
                time.sleep(0.5)

            if local_latest_date:
                new_ordered_data = [d for d in all_ordered_data if d['开奖日期'] > local_latest_date]
                self._log(f"Found {len(new_ordered_data)} new ordered records after {local_latest_date}")
            else:
                new_ordered_data = all_ordered_data
                self._log(f"Local ordered data empty, will use all {len(new_ordered_data)} records")

            return new_ordered_data, len(new_ordered_data)

        except Exception as e:
            self._log(f"Error fetching ordered data: {e}", "ERROR")
            return [], 0

    def append_ordered_data_to_excel(self, new_data: List[Dict[str, Any]]) -> bool:
        """Append new ordered data to Excel file"""
        if not new_data:
            self._log("No new ordered data to append")
            return True

        try:
            import openpyxl
            import pandas as pd
        except ImportError:
            self._log("Missing openpyxl or pandas library", "ERROR")
            return False

        try:
            if self.ordered_xlsx.exists():
                df_existing = pd.read_excel(self.ordered_xlsx)
                self._log(f"Read existing Excel file: {len(df_existing)} rows")
            else:
                df_existing = pd.DataFrame()
                self._log("Ordered data file not found, will create new file")

            positions = ['一位', '二位', '三位', '四位', '五位', '六位', '七位', '八位', '九位', '十位',
                       '十一位', '十二位', '十三位', '十四位', '十五位', '十六位', '十七位', '十八位', '十九位', '二十位']

            new_rows = []
            for item in new_data:
                row = {
                    '开奖期号': item['开奖期号'],
                    '开奖日期': item['开奖日期']
                }
                for i, num in enumerate(item['numbers']):
                    row[positions[i]] = num
                new_rows.append(row)

            df_new = pd.DataFrame(new_rows)

            if not df_existing.empty:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['开奖期号'], keep='first')
                df_combined = df_combined.sort_values(by='开奖日期', ascending=True)
            else:
                df_combined = df_new

            columns_order = ['开奖期号', '开奖日期'] + positions
            df_combined = df_combined[columns_order]

            df_combined.to_excel(self.ordered_xlsx, index=False, sheet_name='快8历史出球顺序')
            self._log(f"Successfully updated ordered data: {len(df_combined)} rows")

            return True

        except Exception as e:
            self._log(f"Error updating ordered data: {e}", "ERROR")
            return False

    def sync_incremental_data(self) -> Dict[str, Any]:
        """Synchronize incremental data (both ordered and unordered)"""
        self._log("=" * 60)
        self._log("Starting incremental data synchronization...")
        self._log("=" * 60)

        start_time = time.time()
        result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'unordered_added': 0,
            'ordered_added': 0,
            'duration_seconds': 0
        }

        try:
            unordered_data, unordered_count = self.fetch_incremental_unordered_data()
            result['unordered_added'] = unordered_count

            if unordered_count > 0:
                if self.append_unordered_data(unordered_data):
                    self._log(f"OK: Added {unordered_count} unordered records")
                else:
                    self._log(f"FAIL: Failed to append unordered data", "ERROR")
            else:
                self._log("INFO: No unordered data updates")

            ordered_data, ordered_count = self.fetch_incremental_ordered_data()
            result['ordered_added'] = ordered_count

            if ordered_count > 0:
                if self.append_ordered_data_to_excel(ordered_data):
                    self._log(f"OK: Added {ordered_count} ordered records")
                else:
                    self._log(f"FAIL: Failed to append ordered data", "ERROR")
            else:
                self._log("INFO: No ordered data updates")

            result['success'] = True
            result['duration_seconds'] = time.time() - start_time

            self._log("=" * 60)
            self._log(f"Sync completed in {result['duration_seconds']:.2f}s")
            self._log(f"  - Unordered: +{result['unordered_added']}")
            self._log(f"  - Ordered: +{result['ordered_added']}")
            self._log("=" * 60)

        except Exception as e:
            self._log(f"Sync error: {e}", "ERROR")
            import traceback
            self._log(traceback.format_exc(), "ERROR")

        return result


def auto_sync_on_startup(timeout_seconds: int = 60) -> Dict[str, Any]:
    """Automatically sync incremental data on service startup"""
    import threading

    service = IncrementalDataService()
    result = {'success': False, 'reason': ''}

    def sync_task():
        nonlocal result
        try:
            result = service.sync_incremental_data()
        except Exception as e:
            result = {
                'success': False,
                'reason': str(e),
                'timestamp': datetime.now().isoformat()
            }

    sync_thread = threading.Thread(target=sync_task, daemon=True)
    sync_thread.start()
    sync_thread.join(timeout=timeout_seconds)

    if sync_thread.is_alive():
        logger.warning(f"Data sync timeout ({timeout_seconds}s)")
        result = {
            'success': False,
            'reason': f'Timeout after {timeout_seconds}s',
            'timestamp': datetime.now().isoformat()
        }

    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    service = IncrementalDataService()
    result = service.sync_incremental_data()
    print("\nSync Result:")
    print(f"  Success: {result['success']}")
    print(f"  Unordered: +{result.get('unordered_added', 0)}")
    print(f"  Ordered: +{result.get('ordered_added', 0)}")
    print(f"  Duration: {result.get('duration_seconds', 0):.2f}s")

