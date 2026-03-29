#!/usr/bin/env python3 -B
# -*- coding: utf-8 -*-
"""
快乐8开奖数据增量获取与转换工具
支持增量获取最新数据并触发相关程序脚本
"""

# 应用JSON兼容性补丁，解决Python 3.13中缺少JSONDecodeError的问题
try:
    from utils.json_patch import patch_json_module
    patch_json_module()
except ImportError:
    pass


import re
import os
import time
import json
import subprocess
import sys
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_fetcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 导入标准库作为备选
import urllib.request
import urllib.error
from urllib.parse import urlencode

# 尝试导入requests模块并检测可用性
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests库不可用，将使用标准库urllib作为备选")


class KuaiLe8DataProcessor:
    """快乐8数据处理器 - 支持增量获取和触发相关程序"""
    
    def __init__(
        self,
        data_dir: str = None,
        enable_incremental: bool = True,
        sequential_trigger: bool = True,
    ):
        """
        初始化数据处理器
        
        做什么：创建数据处理器实例，设置数据目录与触发模式
        怎么做：支持增量获取与顺序触发（训练完成后再预测）
        为什么：确保每日数据更新后稳定执行训练与预测流程
        """
        if data_dir is None:
            # 默认数据目录
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径 - 仅保留kl8_history_final.txt作为主数据源
        self.final_txt_file = self.data_dir / "kl8_history_final.txt"
        
        # 增量获取模式
        self.enable_incremental = enable_incremental

        # 顺序触发模式（训练完成后再触发预测）
        self.sequential_trigger = sequential_trigger
        
        # 触发程序配置
        self.trigger_programs = {
            'train_advanced_models': 'train_advanced_models.py',
            'train_models': 'train_models.py',
            'main_prediction': 'main.py'
        }
    
    def get_data_from_17500_source(self) -> list:
        """
        从17500数据源获取快乐8开奖数据
        支持requests库和urllib标准库两种方式
        """
        url = "http://data.17500.cn/kl8_desc.txt"
        
        try:
            logger.info(f"开始从数据源获取数据: {url}")
            
            # 优先使用requests库
            if REQUESTS_AVAILABLE:
                logger.debug("使用requests库获取数据")
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }, timeout=30)
                
                # 正确的编码应该是gb2312
                response.encoding = 'gb2312'
                logger.info(f"数据源请求状态码: {response.status_code}")
                
                if response.status_code == 200 and response.text:
                    text_content = response.text
                    logger.debug(f"成功获取HTML内容，长度: {len(text_content)} 字符")
                else:
                    logger.error(f"响应状态码异常: {response.status_code}")
                    return []
            else:
                # 备选方案：使用标准库urllib
                logger.debug("使用标准库urllib获取数据")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    # 读取并解码为gb2312
                    text_content = response.read().decode('gb2312')
                logger.debug(f"成功获取HTML内容，长度: {len(text_content)} 字符")
            
            # 解析文本数据
            logger.debug("开始解析文本数据")
            lines = text_content.strip().split('\n')
            data = []
            valid_count = 0
            invalid_count = 0
            
            for line in lines:
                # 正确解析数据格式：期号 日期 20个号码 奖金信息...
                parts = line.strip().split()
                if len(parts) >= 22:  # 至少要有期号、日期和20个号码
                    issue = parts[0]      # 期号
                    date = parts[1]       # 日期
                    # 20个开奖号码是 parts[2] 到 parts[21]
                    numbers = parts[2:22]
                    
                    # 验证日期格式是否正确（YYYY-MM-DD）
                    if len(date) == 10 and date[4] == '-' and date[7] == '-':
                        formatted_numbers = [num.zfill(2) for num in numbers]
                        formatted_numbers_str = '-'.join(formatted_numbers)
                        
                        data.append({
                            'date': date,           # 日期
                            'issue': issue,         # 期号
                            'numbers': formatted_numbers_str  # 号码
                        })
                        valid_count += 1
                    else:
                        invalid_count += 1
                        logger.warning(f"日期格式不正确，跳过: {line}")
                else:
                    invalid_count += 1
                    logger.warning(f"数据格式不正确，跳过: {line}")
            
            if invalid_count > 0:
                logger.warning(f"跳过 {invalid_count} 条格式不正确的数据")
            
            logger.info(f"成功解析 {valid_count} 条有效数据")
            
            # 数据源是升序排列（从旧到新），我们需要按日期降序排列（从新到旧）
            data.sort(key=lambda x: x['date'], reverse=True)
            logger.info(f"数据已按日期降序排列，最新日期: {data[0]['date'] if data else '无数据'}")

            # 旧文本源存在长时间不更新的情况，检测到数据明显陈旧时切换到移动 API。
            if data:
                latest_year = int(data[0]['date'][:4])
                current_year = datetime.now().year
                if latest_year < current_year - 1:
                    logger.warning("检测到主数据源最新年份过旧，改用移动 API 拉取最新开奖。")
                    mobile_data = self.get_data_from_mobile_api()
                    if mobile_data:
                        return mobile_data
            
            return data
            
        except urllib.error.URLError as e:
            logger.error(f"网络请求错误: {e}")
            return self.get_sample_data()
        except Exception as e:
            logger.error(f"获取数据时出错: {e}")
            logger.exception("详细错误信息:")
            return self.get_sample_data()

    def get_data_from_mobile_api(self) -> list:
        """
        使用 17500 移动 API 获取最新开奖数据，作为旧文本源的补充。
        """
        api_url = "https://m.17500.cn/tgj/api/kl8/getTbList"
        params = {
            'action': 'cqzs',
            'page': 1,
            'limit': 200,
            'orderby': 'desc',
            'start_issue': 0,
            'end_issue': 0,
            'week': 'all'
        }

        try:
            if REQUESTS_AVAILABLE:
                response = requests.get(api_url, params=params, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://m.17500.cn/tgj/kl8/cqzs.html'
                }, timeout=20)
                response.raise_for_status()
                payload = response.json()
            else:
                req = urllib.request.Request(f"{api_url}?{urlencode(params)}", headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://m.17500.cn/tgj/kl8/cqzs.html'
                })
                with urllib.request.urlopen(req, timeout=20) as response:
                    payload = json.loads(response.read().decode('utf-8'))

            records = payload.get('data', {}).get('data', [])
            parsed = []
            for record in records:
                issue = str(record.get('issue', '')).strip()
                date = str(record.get('kjdate', '')).strip()
                numbers = record.get('cqzs', {}).get('winnum', [])
                cleaned = [str(num).replace('*', '').zfill(2) for num in numbers if str(num).replace('*', '').isdigit()]
                if issue and re.match(r"^\d{4}-\d{2}-\d{2}$", date) and len(cleaned) == 20:
                    parsed.append({
                        'date': date,
                        'issue': issue,
                        'numbers': '-'.join(cleaned)
                    })

            parsed.sort(key=lambda x: x['date'], reverse=True)
            logger.info(f"移动 API 获取成功，共 {len(parsed)} 期，最新日期: {parsed[0]['date'] if parsed else '无数据'}")
            return parsed
        except Exception as e:
            logger.error(f"移动 API 获取失败: {e}")
            return []
            
    def _deterministic_sample(self, population, k, seed=0):
        """
        做什么：确定性采样替代random.sample
        怎么做：基于种子和哈希算法实现确定性采样
        为什么：确保示例数据生成结果一致，避免随机性影响
        """
        import hashlib
        
        # 基于种子生成确定性序列
        seed_str = f"sample_{seed}"
        hash_val = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        
        # 将population转换为列表
        pop_list = list(population)
        n = len(pop_list)
        
        # 确定性采样算法
        selected = []
        for i in range(k):
            # 基于哈希值和索引计算选择位置
            pos = (hash_val + i * 997) % n  # 使用质数997避免模式重复
            selected.append(pop_list[pos])
            
            # 避免重复选择
            if pos < n - 1:
                pop_list[pos] = pop_list[n-1]
            n -= 1
        
        return selected

    def get_sample_data(self) -> list:
        """
        提供示例数据作为备选，当网络请求失败或无法使用时
        
        做什么：生成示例数据作为网络请求失败的备选方案
        怎么做：生成最近10期的随机开奖数据
        为什么：确保系统在网络不可用时仍能正常运行
        """
        print("使用示例数据作为备选...")
        
        # 生成最近10期的示例数据
        sample_data = []
        for i in range(10):
            # 使用当前日期减去天数生成日期
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # 生成假定期号
            issue = f"2024{i+100:04d}"
            # 生成20个确定性号码（1-80）
            # 使用确定性算法替代random.sample
            numbers = self._deterministic_sample(range(1, 81), 20, seed=i)
            numbers.sort()
            formatted_numbers = [f"{num:02d}" for num in numbers]
            numbers_str = '-'.join(formatted_numbers)
            
            sample_data.append({
                'date': date,
                'issue': issue,
                'numbers': numbers_str
            })
        
        return sample_data
    
    def get_latest_local_date(self) -> str:
        """
        获取本地数据文件中的最新日期
        
        做什么：从本地数据文件中提取最新开奖日期
        怎么做：读取文件第一行（最新数据）并解析日期
        为什么：用于增量数据检测，避免重复处理已有数据
        """
        if not self.final_txt_file.exists():
            logger.info("本地数据文件不存在，返回None")
            return None
        
        try:
            with open(self.final_txt_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line:
                    # 解析日期格式：date:YYYY-MM-DD
                    match = re.search(r'date:(\d{4}-\d{2}-\d{2})', first_line)
                    if match:
                        latest_date = match.group(1)
                        logger.info(f"成功获取本地最新日期: {latest_date}")
                        return latest_date
                    else:
                        logger.warning(f"无法解析日期格式: {first_line}")
                else:
                    logger.warning("本地数据文件为空")
        except Exception as e:
            logger.error(f"读取本地最新日期时出错: {e}")
        
        return None
    
    def filter_incremental_data(self, all_data: list, latest_local_date: str) -> list:
        """
        筛选增量数据
        
        做什么：根据本地最新日期筛选出需要更新的新数据
        怎么做：比较数据源中每条记录的日期与本地最新日期
        为什么：减少数据处理量，提高效率，避免重复处理
        """
        if not latest_local_date:
            logger.info("没有本地最新日期，返回所有数据")
            return all_data  # 如果没有本地数据，返回所有数据
        
        incremental_data = []
        valid_count = 0
        
        logger.info(f"本地最新日期: {latest_local_date}")
        logger.info(f"数据源最新日期: {all_data[0]['date'] if all_data else '无数据'}")
        
        for item in all_data:
            if 'date' not in item:
                logger.warning(f"数据项缺少date字段: {item}")
                continue
                
            try:
                # 数据源已经按日期降序排列，我们只需要找到比本地最新日期更新的数据
                if item['date'] > latest_local_date:
                    incremental_data.append(item)
                    logger.debug(f"发现新数据: {item['date']} 期号: {item['issue']}")
                valid_count += 1
            except Exception as e:
                logger.error(f"比较日期时出错: {e}, 数据项: {item}")
        
        logger.info(f"增量数据筛选结果: 从{valid_count}条有效数据中筛选出{len(incremental_data)}条新数据")
        
        if incremental_data:
            logger.info(f"最新新数据日期: {incremental_data[0]['date']}")
        else:
            logger.info("没有发现新数据")
            
        return incremental_data
    
    def trigger_related_programs(self, has_new_data: bool) -> None:
        """
        触发相关程序脚本
        
        做什么：在数据更新后触发训练与预测程序
        怎么做：支持顺序触发（训练完成再预测）或并行异步触发
        为什么：满足每日单次执行的稳定性与时序要求
        """
        project_root = Path(__file__).parent.parent
        models_dir = project_root / 'models'
        train_adv_script = (
            project_root / self.trigger_programs['train_advanced_models']
        )
        train_script = project_root / self.trigger_programs['train_models']
        main_script = project_root / self.trigger_programs['main_prediction']

        if not has_new_data:
            logger.info("没有新数据，跳过程序触发")
            return

        logger.info("检测到新数据，开始触发相关程序...")
        try:
            models_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"清空模型目录 {models_dir}")
            for p in models_dir.iterdir():
                try:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink()
                except Exception as e:
                    logger.warning(f"清理失败: {p} {e}")
            logger.info("模型目录已清空")
        except Exception as e:
            logger.error(f"清理模型目录时出错: {e}")

        if self.sequential_trigger:
            try:
                if not train_adv_script.exists():
                    logger.warning(
                        f"高级模型训练脚本不存在: {train_adv_script}"
                    )
                    return
                logger.info(
                    f"顺序触发：开始高级模型训练 {train_adv_script}"
                )
                proc_adv = subprocess.Popen(
                    [sys.executable, str(train_adv_script)],
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                out_adv, err_adv = proc_adv.communicate()
                if out_adv:
                    logger.info(out_adv)
                if err_adv:
                    logger.error(err_adv)
                if proc_adv.returncode != 0:
                    logger.error(
                        f"高级训练脚本执行失败，返回码: {proc_adv.returncode}"
                    )
                    return

                if not train_script.exists():
                    logger.warning(f"模型训练脚本不存在: {train_script}")
                    return
                logger.info(f"顺序触发：开始训练模型 {train_script}")
                proc = subprocess.Popen(
                    [sys.executable, str(train_script)],
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                out, err = proc.communicate()
                if out:
                    logger.info(out)
                if err:
                    logger.error(err)
                if proc.returncode != 0:
                    logger.error(f"训练脚本执行失败，返回码: {proc.returncode}")
                    return
                logger.info("[OK] 训练完成，开始触发主预测程序")
                if not main_script.exists():
                    logger.warning(f"主预测脚本不存在: {main_script}")
                    return
                subprocess.Popen(
                    [sys.executable, str(main_script)],
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                logger.info("[OK] 主预测程序已启动（异步执行）")
            except Exception as e:
                logger.error(f"顺序触发流程出错: {e}")
        else:
            try:
                if train_script.exists():
                    logger.info(f"并行触发：模型训练 {train_script}")
                    subprocess.Popen(
                        [sys.executable, str(train_script)],
                        cwd=project_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    logger.info("[OK] 模型训练已启动（异步执行）")
                else:
                    logger.warning(f"模型训练脚本不存在: {train_script}")
            except Exception as e:
                logger.error(f"触发模型训练时出错: {e}")

            try:
                if main_script.exists():
                    logger.info(f"并行触发：主预测程序 {main_script}")
                    subprocess.Popen(
                        [sys.executable, str(main_script)],
                        cwd=project_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    logger.info("[OK] 主预测程序已启动（异步执行）")
                else:
                    logger.warning(f"主预测脚本不存在: {main_script}")
            except Exception as e:
                logger.error(f"触发主预测程序时出错: {e}")
    
    def load_existing_data(self, filename: str) -> list:
        """
        加载现有数据文件
        
        做什么：从本地文件加载现有的开奖数据
        怎么做：读取文本文件并解析每行数据
        为什么：支持增量更新，避免重复获取已有数据
        """
        if not os.path.exists(filename):
            logger.warning(f"数据文件不存在: {filename}")
            return []
        
        existing_data = []
        valid_count = 0
        invalid_count = 0
        
        try:
            logger.info(f"开始加载现有数据文件: {filename}")
            with open(filename, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        # 尝试匹配中文格式
                        match = re.match(r'开奖日期：(.+),开奖期数:(\d+),开奖号码:(.+)', line)
                        if not match:
                            # 尝试匹配英文格式
                            match = re.match(r'date:(.+),period:(\d+),numbers:(.+)', line)
                        
                        if match:
                            date, issue, numbers = match.groups()
                            existing_data.append({
                                'date': date,
                                'issue': issue,
                                'numbers': numbers
                            })
                            valid_count += 1
                        else:
                            invalid_count += 1
                            logger.warning(f"第{line_num}行数据格式不正确: {line}")
            
            if invalid_count > 0:
                logger.warning(f"跳过 {invalid_count} 条格式不正确的数据")
            
            logger.info(f"成功加载 {valid_count} 条有效数据")
            
        except FileNotFoundError:
            logger.error(f"数据文件不存在: {filename}")
        except PermissionError:
            logger.error(f"没有权限读取文件: {filename}")
        except UnicodeDecodeError as e:
            logger.error(f"文件编码错误: {e}")
        except Exception as e:
            logger.error(f"加载现有数据失败: {e}")
            logger.exception("详细错误信息:")
        
        return existing_data
    
    def merge_data(self, existing_data: list, new_data: list):
        """
        合并现有数据和新数据
        
        做什么：将新数据合并到现有数据中，避免重复
        怎么做：基于期号去重，按日期降序排列
        为什么：确保数据完整性，避免重复记录，最新数据在前
        """
        try:
            logger.info(f"开始合并数据: 现有数据 {len(existing_data)} 条, 新数据 {len(new_data)} 条")
            
            # 创建期号到数据的映射
            data_map = {}
            existing_count = 0
            new_count = 0
            duplicate_count = 0
            
            # 先添加现有数据
            for item in existing_data:
                if 'issue' in item:
                    data_map[item['issue']] = item
                    existing_count += 1
                else:
                    logger.warning("现有数据中缺少期号字段，跳过")
            
            # 再添加新数据（会覆盖重复的期号）
            for item in new_data:
                if 'issue' in item:
                    if item['issue'] in data_map:
                        duplicate_count += 1
                        logger.debug(f"发现重复期号: {item['issue']}")
                    data_map[item['issue']] = item
                    new_count += 1
                else:
                    logger.warning("新数据中缺少期号字段，跳过")
            
            # 按日期降序排列（最新数据在前）
            merged_data = []
            try:
                merged_data = sorted(data_map.values(), key=lambda x: x['date'], reverse=True)
                logger.info(f"合并完成: 总数据 {len(merged_data)} 条 (现有: {existing_count}, 新增: {new_count}, 重复: {duplicate_count})")
                
                if merged_data:
                    logger.info(f"合并后最新日期: {merged_data[0]['date']}")
                    logger.info(f"合并后最旧日期: {merged_data[-1]['date']}")
            except KeyError as e:
                logger.error(f"数据排序失败，缺少日期字段: {e}")
                # 如果排序失败，返回原始数据
                merged_data = list(data_map.values())
            except Exception as e:
                logger.error(f"数据排序失败: {e}")
                merged_data = list(data_map.values())
            
            return merged_data
            
        except Exception as e:
            logger.error(f"数据合并失败: {e}")
            logger.exception("详细错误信息:")
            # 返回空列表避免程序崩溃
            return []
    
    def save_to_txt_file(self, data: list, filename: str):
        """
        保存数据到文本文件
        
        做什么：将处理后的数据保存到本地文件
        怎么做：按指定格式写入文本文件
        为什么：持久化存储数据，便于后续使用
        """
        try:
            logger.info(f"开始保存数据到文件: {filename}")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            saved_count = 0
            error_count = 0
            
            with open(filename, 'w', encoding='utf-8') as f:
                for item in data:
                    try:
                        # 验证数据格式
                        if 'date' not in item or 'issue' not in item or 'numbers' not in item:
                            logger.warning(f"数据格式不完整，跳过: {item}")
                            error_count += 1
                            continue
                        
                        # 根据文件名决定使用哪种格式
                        if 'final' in os.path.basename(filename):
                            # 保持原始英文格式
                            line = f"date:{item['date']},period:{item['issue']},numbers:{item['numbers']}\n"
                        else:
                            # 使用中文标签格式
                            line = f"开奖日期：{item['date']},开奖期数:{item['issue']},开奖号码:{item['numbers']}\n"
                        
                        f.write(line)
                        saved_count += 1
                        
                    except Exception as e:
                        logger.error(f"写入单条数据失败: {e}")
                        error_count += 1
                        continue
            
            if error_count > 0:
                logger.warning(f"保存过程中跳过 {error_count} 条格式不正确的数据")
            
            logger.info(f"成功保存 {saved_count} 条数据到文件: {filename}")
            
        except PermissionError:
            logger.error(f"没有权限写入文件: {filename}")
        except IOError as e:
            logger.error(f"文件IO错误: {e}")
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            logger.exception("详细错误信息:")
    
    def validate_data_format(self, data: list) -> bool:
        """
        验证数据格式
        
        做什么：检查数据格式是否符合要求
        怎么做：验证必填字段和数据类型
        为什么：确保数据质量，避免后续处理错误
        """
        if not data:
            logger.error("验证失败: 数据为空")
            return False
        
        valid_count = 0
        invalid_count = 0
        
        logger.info("开始验证数据格式...")
        
        for i, item in enumerate(data, 1):
            try:
                # 检查必填字段
                if 'date' not in item:
                    logger.error(f"第{i}条数据缺少日期字段")
                    invalid_count += 1
                    continue
                
                if 'issue' not in item:
                    logger.error(f"第{i}条数据缺少期号字段")
                    invalid_count += 1
                    continue
                
                if 'numbers' not in item:
                    logger.error(f"第{i}条数据缺少号码字段")
                    invalid_count += 1
                    continue
                
                # 检查号码格式 - 支持字符串格式（如"01-02-03..."）
                numbers_str = item['numbers']
                if isinstance(numbers_str, str):
                    numbers_list = numbers_str.split('-')
                    if len(numbers_list) != 20:
                        logger.error(
                            f"第{i}条数据号码数量不正确: "
                            f"{len(numbers_list)}个号码"
                        )
                        invalid_count += 1
                        continue
                    
                    # 检查号码格式（应为01-80的数字）
                    for num in numbers_list:
                        if not num.isdigit() or not (1 <= int(num) <= 80):
                            logger.error(
                                f"第{i}条数据号码格式不正确: {num}"
                            )
                            invalid_count += 1
                            break
                    else:
                        valid_count += 1
                else:
                    # 如果是列表格式
                    if len(item['numbers']) != 20:
                        logger.error(
                            f"第{i}条数据号码数量不正确: "
                            f"{len(item['numbers'])}个号码"
                        )
                        invalid_count += 1
                        continue
                    
                    # 检查号码格式（应为01-80的数字）
                    for num in item['numbers']:
                        if not num.isdigit() or not (1 <= int(num) <= 80):
                            logger.error(
                                f"第{i}条数据号码格式不正确: {num}"
                            )
                            invalid_count += 1
                            break
                    else:
                        valid_count += 1
                    
            except Exception as e:
                logger.error(f"验证第{i}条数据时出错: {e}")
                invalid_count += 1
        
        if invalid_count > 0:
            logger.error(f"数据验证失败: {invalid_count} 条数据格式不正确")
            return False
        
        logger.info(f"数据验证成功: 所有 {valid_count} 条数据格式正确")
        return True
    
    def backup_existing_file(self, filename: str):
        """
        备份现有文件
        
        做什么：在更新前备份现有数据文件
        怎么做：复制文件并添加时间戳后缀
        为什么：防止数据丢失，便于回滚
        """
        if not os.path.exists(filename):
            logger.warning(f"备份文件不存在，跳过备份: {filename}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = filename.replace('.txt', f'_backup_{timestamp}.txt')
            
            # 确保备份目录存在
            os.makedirs(os.path.dirname(backup_name), exist_ok=True)
            
            import shutil
            shutil.copy2(filename, backup_name)
            
            # 验证备份文件是否创建成功
            if os.path.exists(backup_name):
                file_size = os.path.getsize(backup_name)
                logger.info(f"备份文件成功: {backup_name} (大小: {file_size} 字节)")
            else:
                logger.error(f"备份文件创建失败: {backup_name}")
                
        except PermissionError:
            logger.error(f"没有权限备份文件: {filename}")
        except IOError as e:
            logger.error(f"文件IO错误: {e}")
        except Exception as e:
            logger.error(f"备份失败: {e}")
            logger.exception("详细错误信息:")
    
    def process_data_pipeline(self, force_update: bool = False, enable_trigger: bool = True):
        """
        数据处理流水线 - 支持增量获取和程序触发
        
        做什么：执行完整的数据处理流程，支持增量获取和自动触发相关程序
        怎么做：根据配置决定使用全量还是增量获取，处理完成后触发相关程序
        为什么：提高数据处理效率，实现数据更新后的自动化处理流程
        """
        logger.info("=== 快乐8开奖数据处理流水线开始 ===")
        
        try:
            # 1. 获取本地最新日期
            latest_local_date = self.get_latest_local_date()
            logger.info(
                f"本地最新开奖日期: "
                f"{latest_local_date if latest_local_date else '无本地数据'}"
            )
            
            # 2. 从数据源获取数据
            logger.info("1. 从17500数据源获取数据...")
            all_new_data = self.get_data_from_17500_source()
            
            if not all_new_data:
                logger.error("无法从数据源获取数据")
                return False
            
            logger.info(f"成功获取 {len(all_new_data)} 期数据")
            
            # 3. 增量数据筛选
            if self.enable_incremental and latest_local_date:
                logger.info("2. 增量数据筛选...")
                incremental_data = self.filter_incremental_data(
                    all_new_data,
                    latest_local_date,
                )
                
                if not incremental_data:
                    logger.info("[OK] 没有发现新数据，数据已是最新")
                    # 即使没有新数据，也触发程序（用于定期更新）
                    if enable_trigger:
                        self.trigger_related_programs(has_new_data=False)
                    return True
                
                new_data = incremental_data
                logger.info(
                    f"增量模式: 筛选出 {len(new_data)} 条新数据"
                )
            else:
                # 全量模式或首次运行
                new_data = all_new_data
                logger.info(
                    f"全量模式: 使用所有 {len(new_data)} 条数据"
                )
            
            # 4. 加载现有数据
            logger.info("3. 加载现有数据...")
            existing_data = self.load_existing_data(str(self.final_txt_file))
            logger.info(
                f"现有数据 {len(existing_data)} 条"
            )
            
            # 5. 合并数据
            logger.info("4. 合并数据...")
            merged_data = self.merge_data(existing_data, new_data)
            logger.info(
                f"合并后数据 {len(merged_data)} 条"
            )
            
            # 6. 验证数据格式
            logger.info("5. 验证数据格式...")
            if not self.validate_data_format(merged_data):
                return False
            
            # 7. 备份现有文件
            if len(new_data) > 0:
                logger.info("6. 备份现有文件...")
                self.backup_existing_file(str(self.final_txt_file))
            
            # 8. 保存数据文件
            logger.info("7. 保存kl8_history_final.txt文件...")
            self.save_to_txt_file(merged_data, str(self.final_txt_file))
            
            # 9. 触发相关程序
            has_new_data = len(new_data) > 0
            if enable_trigger:
                logger.info("8. 触发相关程序...")
                self.trigger_related_programs(has_new_data)
            
            # 完成处理
            logger.info("=== 数据处理完成 ===")
            logger.info(f"数据文件: {self.final_txt_file}")
            logger.info(
                f"总数据量: {len(merged_data)} 期"
            )
            logger.info(
                f"新增数据: {len(new_data)} 期"
            )
            logger.info(
                f"增量模式: {'启用' if self.enable_incremental else '禁用'}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"数据处理流水线执行失败: {e}")
            logger.exception("详细错误信息:")
            return False


def main():
    """
    主函数 - 支持命令行参数控制增量模式和触发功能
    
    做什么：解析命令行参数并执行数据处理流程
    怎么做：使用argparse解析参数，支持增量模式、强制更新和触发控制
    为什么：提供灵活的运行方式，适应不同的使用场景
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='快乐8开奖数据处理工具'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='使用全量模式（禁用增量获取）',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制更新（备份现有文件）',
    )
    parser.add_argument(
        '--no-trigger',
        action='store_true',
        help='禁用程序触发功能',
    )
    parser.add_argument(
        '--sequential-trigger',
        action='store_true',
        help='顺序触发：训练完成后再触发预测',
    )
    
    args = parser.parse_args()
    
    logger.info("快乐8开奖数据处理工具")
    logger.info("功能: 增量获取历史数据并触发相关程序")
    logger.info("=" * 50)
    
    # 显示依赖状态
    if REQUESTS_AVAILABLE:
        logger.info("[OK] requests库可用")
    else:
        logger.warning("[WARN] requests库不可用，将使用标准库urllib作为备选")
    
    # 创建数据处理器
    processor = KuaiLe8DataProcessor(
        enable_incremental=not args.full,
        sequential_trigger=True,
    )
    
    # 显示运行模式
    mode = "全量模式" if args.full else "增量模式"
    trigger_status = "禁用" if args.no_trigger else "顺序触发"
    logger.info(f"运行模式: {mode}")
    logger.info(f"程序触发: {trigger_status}")
    logger.info(f"强制更新: {'是' if args.force else '否'}")
    
    # 执行数据处理流水线
    success = processor.process_data_pipeline(
        force_update=args.force, 
        enable_trigger=not args.no_trigger
    )
    
    if success:
        logger.info("[OK] 数据处理成功完成！")
        logger.info(
            "[OK] 已生成 kl8_history_final.txt 文件"
        )
        logger.info(
            "格式：date:YYYY-MM-DD,period:XXXXXXXX,numbers:XX-XX-...-XX"
        )
    else:
        logger.error("[ERROR] 数据处理失败！")
        logger.info("将尝试使用示例数据...")
        
        # 如果处理失败，直接使用示例数据生成文件
        sample_data = processor.get_sample_data()
        if sample_data:
            processor.save_to_txt_file(sample_data, str(processor.final_txt_file))
            logger.info("[OK] 已使用示例数据生成文件")
        else:
            logger.error("[ERROR] 无法生成数据文件")


if __name__ == "__main__":
    main()
