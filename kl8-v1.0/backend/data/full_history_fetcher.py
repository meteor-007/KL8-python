#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8全量历史数据获取脚本
获取有序（出球顺序）和无序（排序号码）的数据
基于 fetch_kl8_history.py 和 data_fetcher_and_converter.py
"""

import requests
import pandas as pd
import time
import re
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('full_history_fetcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# API配置 for ordered data
BASE_URL = "https://m.17500.cn/tgj/api/kl8/getTbList"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://m.17500.cn/tgj/kl8/cqzs.html'
}

# URL for unordered data
UNORDERED_URL = "http://data.17500.cn/kl8_desc.txt"

class FullHistoryFetcher:
    def __init__(self, data_dir=None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_ordered_data(self, page=1, limit=100):
        """获取有序出球顺序数据"""
        params = {
            'action': 'cqzs',
            'page': page,
            'limit': limit,
            'orderby': 'asc',
            'start_issue': 0,
            'end_issue': 0,
            'week': 'all'
        }

        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"请求失败: {e}")
            return None

    def parse_ordered_data(self, data):
        """解析有序出球顺序数据"""
        if not data or data.get('code') != 0:
            logger.warning("数据获取失败")
            return []

        parsed_data = []
        records = data.get('data', {}).get('data', [])

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
                    logger.warning(f"无效的号码格式: {num_str}")

            if len(numbers) == 20:
                row_data = {
                    '开奖期号': issue,
                    '开奖日期': kjdate
                }

                positions = ['一位', '二位', '三位', '四位', '五位', '六位', '七位', '八位', '九位', '十位',
                           '十一位', '十二位', '十三位', '十四位', '十五位', '十六位', '十七位', '十八位', '十九位', '二十位']
                for i, num in enumerate(numbers):
                    row_data[positions[i]] = num

                parsed_data.append(row_data)
            else:
                logger.warning(f"期号 {issue} 的号码数量不正确: {len(numbers)} 个")

        return parsed_data

    def fetch_unordered_data(self):
        """获取无序开奖号码数据"""
        try:
            logger.info(f"开始从数据源获取无序数据: {UNORDERED_URL}")
            response = requests.get(UNORDERED_URL, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }, timeout=30)
            response.encoding = 'gb2312'

            if response.status_code == 200 and response.text:
                text_content = response.text
                logger.info(f"成功获取无序数据，长度: {len(text_content)} 字符")
            else:
                logger.error(f"响应状态码异常: {response.status_code}")
                return []

            lines = text_content.strip().split('\n')
            data = []
            valid_count = 0
            invalid_count = 0

            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 22:
                    issue = parts[0]
                    date = parts[1]
                    numbers = parts[2:22]

                    if len(date) == 10 and date[4] == '-' and date[7] == '-':
                        # Sort numbers for unordered
                        sorted_numbers = sorted([int(num) for num in numbers])
                        formatted_numbers = [f"{num:02d}" for num in sorted_numbers]
                        numbers_str = '-'.join(formatted_numbers)

                        data.append({
                            'date': date,
                            'issue': issue,
                            'numbers': numbers_str
                        })
                        valid_count += 1
                    else:
                        invalid_count += 1
                        logger.warning(f"日期格式不正确，跳过: {line}")
                else:
                    invalid_count += 1
                    logger.warning(f"数据格式不正确，跳过: {line}")

            logger.info(f"成功解析 {valid_count} 条有效无序数据")
            if invalid_count > 0:
                logger.warning(f"跳过 {invalid_count} 条格式不正确的数据")

            # Sort by date descending
            data.sort(key=lambda x: x['date'], reverse=True)
            return data

        except Exception as e:
            logger.error(f"获取无序数据时出错: {e}")
            return []

    def save_ordered_to_excel(self, data, filename):
        """保存有序数据到Excel"""
        try:
            import openpyxl
            from openpyxl.utils.dataframe import dataframe_to_rows
        except ImportError:
            logger.error("openpyxl库不可用，无法生成Excel文件")
            return

        import numpy as np

        def convert_numpy_types(data):
            converted_data = []
            for row in data:
                converted_row = {}
                for key, value in row.items():
                    if isinstance(value, (np.int64, np.int32, np.int16, np.int8)):
                        converted_row[key] = int(value)
                    elif isinstance(value, (np.float64, np.float32, np.float16)):
                        float_val = float(value)
                        converted_row[key] = int(float_val) if float_val.is_integer() else float_val
                    else:
                        converted_row[key] = value
                converted_data.append(converted_row)
            return converted_data

        converted_data = convert_numpy_types(data)
        df = pd.DataFrame(converted_data)

        columns_order = ['开奖期号', '开奖日期'] + ['一位', '二位', '三位', '四位', '五位', '六位', '七位', '八位', '九位', '十位',
                           '十一位', '十二位', '十三位', '十四位', '十五位', '十六位', '十七位', '十八位', '十九位', '二十位']
        df = df[columns_order]

        df['开奖日期'] = pd.to_datetime(df['开奖日期'])
        df = df.sort_values(by='开奖日期', ascending=True)
        df['开奖日期'] = df['开奖日期'].dt.strftime('%Y-%m-%d')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '快8历史出球顺序'

        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws.cell(row=r_idx, column=c_idx, value=value)

        wb.save(filename)
        logger.info(f"有序数据已保存到 {filename}")

    def save_unordered_to_txt(self, data, filename):
        """保存无序数据到TXT"""
        with open(filename, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(f"{item['date']} {item['issue']} {item['numbers']}\n")
        logger.info(f"无序数据已保存到 {filename}")

    def fetch_full_history(self):
        """获取全量历史数据"""
        logger.info("开始获取全量有序历史数据...")

        # Fetch ordered data
        all_ordered_data = []
        page = 1
        limit = 100

        while True:
            logger.info(f"正在获取有序数据第 {page} 页...")
            data = self.fetch_ordered_data(page, limit)

            if not data:
                logger.error("获取有序数据失败")
                break

            parsed_data = self.parse_ordered_data(data)

            if not parsed_data:
                logger.warning("解析有序数据失败")
                break

            all_ordered_data.extend(parsed_data)
            logger.info(f"第 {page} 页获取到 {len(parsed_data)} 条有序数据")

            total = data.get('data', {}).get('total', 0)
            current_count = page * limit

            if current_count >= total:
                logger.info("已获取所有有序数据")
                break

            page += 1
            time.sleep(1)

        logger.info(f"总共获取到 {len(all_ordered_data)} 条有序数据")

        # Fetch unordered data
        logger.info("开始获取全量无序历史数据...")
        unordered_data = self.fetch_unordered_data()
        logger.info(f"获取到 {len(unordered_data)} 条无序数据")

        # Save ordered data
        if all_ordered_data:
            ordered_filename = self.data_dir / '快8历史出球顺序.xlsx'
            self.save_ordered_to_excel(all_ordered_data, ordered_filename)

        # Save unordered data
        if unordered_data:
            unordered_filename = self.data_dir / 'kl8_history_final.txt'
            self.save_unordered_to_txt(unordered_data, unordered_filename)

        logger.info("全量历史数据获取完成")

def main():
    fetcher = FullHistoryFetcher()
    fetcher.fetch_full_history()

if __name__ == "__main__":
    main()
