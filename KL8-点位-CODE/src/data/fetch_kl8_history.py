#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8历史出球顺序数据获取脚本
从17500.cn网站获取快乐8历史开奖数据并保存到Excel文件
"""

import requests
import pandas as pd
import time
import re
from datetime import datetime
import os

# API配置
BASE_URL = "https://m.17500.cn/tgj/api/kl8/getTbList"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://m.17500.cn/tgj/kl8/cqzs.html'
}



def fetch_kl8_data(page=1, limit=100):
    """获取快乐8数据"""
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
        print(f"请求失败: {e}")
        return None

def parse_kl8_data(data):
    """解析快乐8数据"""
    if not data or data.get('code') != 0:
        print("数据获取失败")
        return []
    
    parsed_data = []
    records = data.get('data', {}).get('data', [])
    
    for record in records:
        # 提取期号
        issue = record.get('issue')
        # 提取开奖日期
        kjdate = record.get('kjdate')
        # 从cqzs.winnum获取原始出球顺序号码
        cqzs_data = record.get('cqzs', {})
        winnum_list = cqzs_data.get('winnum', [])
        
        # 清理号码数据，移除特殊字符(*)并转换为整数
        numbers = []
        for num_str in winnum_list:
            # 移除可能的特殊字符(*)
            clean_num = num_str.replace('*', '')
            try:
                numbers.append(int(clean_num))
            except ValueError:
                print(f"无效的号码格式: {num_str}")
        
        # 确保有20个号码
        if len(numbers) == 20:
            # 创建一行数据
            row_data = {
                '开奖期号': issue,
                '开奖日期': kjdate
            }
            
            # 添加20个号码列，保持原始出球顺序
            for i, num in enumerate(numbers):
                position = ['一位', '二位', '三位', '四位', '五位', '六位', '七位', '八位', '九位', '十位',
                           '十一位', '十二位', '十三位', '十四位', '十五位', '十六位', '十七位', '十八位', '十九位', '二十位'][i]
                row_data[position] = num
                
            parsed_data.append(row_data)
        else:
            print(f"期号 {issue} 的号码数量不正确: {len(numbers)} 个")
    
    return parsed_data

def save_to_excel(data, filename):
    """保存数据到Excel文件（使用openpyxl）"""
    import openpyxl
    from openpyxl.utils.dataframe import dataframe_to_rows
    import numpy as np
    
    # 转换numpy数值类型为Python原生类型
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
    
    # 先转换数据类型再创建DataFrame
    converted_data = convert_numpy_types(data)
    df = pd.DataFrame(converted_data)
    
    # 确保列的顺序正确
    columns_order = ['开奖期号', '开奖日期'] + ['一位', '二位', '三位', '四位', '五位', '六位', '七位', '八位', '九位', '十位',
                           '十一位', '十二位', '十三位', '十四位', '十五位', '十六位', '十七位', '十八位', '十九位', '二十位']
    df = df[columns_order]
    
    # 转换开奖日期为datetime格式
    df['开奖日期'] = pd.to_datetime(df['开奖日期'])
    
    # 按开奖日期升序排列
    df = df.sort_values(by='开奖日期', ascending=True)
    
    # 只保留日期部分，去除时分秒，并转换为字符串格式
    df['开奖日期'] = df['开奖日期'].dt.strftime('%Y-%m-%d')
    
    # 使用openpyxl创建工作簿
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '快8历史出球顺序'
    
    # 使用dataframe_to_rows高效写入数据
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx, value=value)
    
    # 保存文件
    wb.save(filename)
    print(f"数据已保存到 {filename}")

def main():
    """主函数"""
    print("开始获取快乐8历史出球顺序数据...")
    
    # 获取所有数据
    all_data = []
    page = 1
    limit = 100  # 增加每页获取的数据量以提高效率
    
    while True:
        print(f"正在获取第 {page} 页数据...")
        data = fetch_kl8_data(page, limit)
        
        if not data:
            print("获取数据失败，停止获取")
            break
            
        parsed_data = parse_kl8_data(data)
        
        if not parsed_data:
            print("解析数据失败，停止获取")
            break
            
        all_data.extend(parsed_data)
        print(f"第 {page} 页获取到 {len(parsed_data)} 条数据")
        
        # 检查是否还有更多数据
        total = data.get('data', {}).get('total', 0)
        current_count = page * limit
        
        if current_count >= total:
            print("已获取所有数据")
            break
            
        # 增加页码
        page += 1
        
        # 添加延时，避免请求过于频繁
        time.sleep(1)
    
    print(f"总共获取到 {len(all_data)} 条数据")
    
    # 保存到Excel文件
    if all_data:
        # 使用xlsx格式保存
        filename = os.path.join(os.path.dirname(__file__), '快8历史出球顺序_new.xlsx')
        save_to_excel(all_data, filename)
        print("数据获取完成! 文件保存为: 快8历史出球顺序_new.xlsx")
        
        # 重命名为最终文件名
        final_filename = os.path.join(os.path.dirname(__file__), '快8历史出球顺序.xlsx')
        if os.path.exists(final_filename):
            os.remove(final_filename)
        os.rename(filename, final_filename)
        print(f"文件已重命名为: {final_filename}")
    else:
        print("未获取到任何数据")

if __name__ == "__main__":
    main()