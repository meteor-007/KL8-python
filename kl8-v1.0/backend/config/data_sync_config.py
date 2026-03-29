#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据同步配置文件
控制服务启动时的增量数据获取行为
"""

# 是否在服务启动时自动同步增量数据
ENABLE_INCREMENTAL_SYNC = True

# 增量同步的超时时间（秒）
# 如果同步时间超过此值，将跳过此次同步，继续启动服务
SYNC_TIMEOUT_SECONDS = 60

# 是否在同步时跳过失败任务
# True: 如果无序或有序数据获取失败，继续启动服务
# False: 任何失败都会导致启动阶段显示错误提示
SKIP_ON_FAILURE = True

# 增量同步任务是否在后台进行（不阻塞启动）
RUN_IN_BACKGROUND = True

# 数据更新后是否自动触发模型训练
AUTO_TRIGGER_TRAINING = False

# 自动触发的训练命令
TRAINING_COMMAND = "python train_advanced_models.py"

# 同步日志级别
# 可选: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = "INFO"

# 是否启用详细日志输出
VERBOSE = False

# 重试策略
MAX_RETRIES = 3
RETRY_INTERVAL_SECONDS = 5

# 数据源配置
ORDERED_DATA_SOURCE = "https://m.17500.cn/tgj/api/kl8/getTbList"
UNORDERED_DATA_SOURCE = "http://data.17500.cn/kl8_desc.txt"

# 请求超时
REQUEST_TIMEOUT_SECONDS = 30

# 单次获取的记录数限制
RECORDS_PER_PAGE = 100

# 最多获取的页数（-1 表示无限制）
MAX_PAGES = -1

