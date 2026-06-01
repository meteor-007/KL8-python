# 工作空间全局开发规范

## 📋 适用范围

本规范适用于 `D:\Dpanqianyi\Python-Project\` 工作空间下的所有项目，包括但不限于：
- `3d/` - 3D彩票分析系统
- `KL8-V1.0/` - KL8彩票分析系统V1.0
- `KL8-V1.1/` - KL8彩票分析系统V1.1
- `KL8-围码+点位+重号/` - KL8综合预测系统
- `logparse/` - 日志分析系统
- 以及其他所有子项目

## 🎯 核心原则

### 1. **统一架构标准**
- 所有项目必须遵循模块化设计
- 禁止在根目录直接存放代码文件
- 必须使用标准化的目录结构

### 2. **代码质量保障**
- 所有代码必须包含中文注释
- 禁止生成临时测试文件
- 必须及时清理无用代码

### 3. **文件管理禁令**
- **严禁**在项目根目录生成图片文件（`.png`, `.jpg`, `.gif`, `.bmp`等）
- **严禁**在项目根目录生成JSON配置文件（`.json`）
- **严禁**在项目根目录生成BAT批处理文件（`.bat`）
- **严禁**在项目根目录生成临时日志文件（`.log`, `.txt`等）

## 📁 标准项目结构模板

所有新项目必须遵循以下结构，现有项目应逐步迁移：

```
项目名称/
├── src/                    # 源代码目录（必须）
│   ├── core/              # 核心功能模块
│   ├── models/            # 预测/分析模型
│   ├── services/          # 服务层
│   ├── utils/             # 工具函数
│   ├── scripts/           # 可执行脚本（必须）
│   └── frontend/          # 前端代码（如有）
├── docs/                  # 文档目录（必须）
│   ├── guides/           # 使用指南
│   ├── api/              # API文档
│   ├── specifications/   # 规范文档
│   └── design/           # 设计文档
├── configs/              # 配置文件目录
├── tests/                # 测试目录（必须）
├── data/                 # 数据目录
├── outputs/              # 输出目录（必须）
│   ├── visualizations/   # 可视化结果
│   ├── predictions/      # 预测结果
│   ├── reports/          # 分析报告
│   └── logs/             # 运行日志
├── requirements.txt      # Python依赖（Python项目必须）
├── package.json         # Node.js依赖（前端项目必须）
├── README.md            # 项目说明（必须）
└── .gitignore           # Git忽略文件（必须）
```

## 🔧 具体实施规则

### 1. **脚本文件管理**
- 所有可执行脚本必须放入 `src/scripts/` 目录
- 禁止在根目录或任意子目录直接存放 `.py` 执行文件
- 每个项目必须有统一的入口脚本（如 `main.py`）

### 2. **前端代码管理**
- 所有HTML、CSS、JavaScript文件必须放入 `src/frontend/` 目录
- 禁止在前端目录外存放前端资源文件
- 前端资源必须按类型分类存放

### 3. **文档管理**
- 所有文档必须放入 `docs/` 目录
- 禁止在项目根目录直接存放 `.md` 文件（README.md除外）
- 文档必须按类型分类存放

### 4. **输出文件管理**
- 所有生成的文件必须放入 `outputs/` 目录
- 禁止在项目任意位置生成临时输出文件
- 输出文件必须按类型分类存放

### 5. **配置文件管理**
- 所有配置文件必须放入 `configs/` 目录
- 禁止在项目根目录存放配置文件
- 配置文件必须使用合适的格式和命名

## 🚫 严格禁止行为

### 1. **文件生成禁令**
```bash
# 禁止生成的文件类型（在根目录）
*.png, *.jpg, *.jpeg, *.gif, *.bmp      # 图片文件
*.json                                   # JSON配置文件
*.bat, *.cmd, *.ps1                      # 批处理脚本
*.log, *.tmp, *.temp                     # 临时日志文件
*.csv, *.xlsx, *.xls                     # 数据文件（应放data/）
```

### 2. **目录结构禁令**
- ❌ 禁止在根目录创建 `script/`, `utils/`, `lib/` 等目录
- ❌ 禁止在根目录创建 `test/`, `test_cases/` 等目录
- ❌ 禁止在根目录创建 `doc/`, `document/` 等目录
- ❌ 禁止在根目录创建 `frontend/`, `web/` 等目录

### 3. **代码质量禁令**
- ❌ 禁止无注释的复杂逻辑代码
- ❌ 禁止生成一次性测试脚本
- ❌ 禁止保留已废弃的代码文件
- ❌ 禁止使用拼音或随意命名的变量

## 🛠️ 合规检查工具

### 1. **目录结构检查脚本**
每个项目应包含 `src/scripts/check_compliance.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目规范合规性检查工具
检查项目是否符合工作空间全局规范
"""

import os
import sys
from pathlib import Path

def check_project_structure(project_path):
    """检查项目结构合规性"""
    required_dirs = ['src', 'docs', 'tests', 'outputs', 'configs']
    violations = []
    
    for dir_name in required_dirs:
        dir_path = project_path / dir_name
        if not dir_path.exists():
            violations.append(f"缺失必要目录: {dir_name}")
    
    # 检查根目录违规文件
    prohibited_extensions = ['.png', '.jpg', '.gif', '.json', '.bat', '.log']
    for file_path in project_path.iterdir():
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in prohibited_extensions:
                violations.append(f"根目录禁止文件: {file_path.name}")
    
    return violations

if __name__ == "__main__":
    project_path = Path.cwd()
    violations = check_project_structure(project_path)
    
    if violations:
        print("❌ 项目结构违规:")
        for violation in violations:
            print(f"  - {violation}")
        sys.exit(1)
    else:
        print("✅ 项目结构符合规范")
```

### 2. **预提交钩子配置**
每个项目应在 `.git/hooks/pre-commit` 中添加：

```bash
#!/bin/bash
# 预提交合规性检查

echo "🔍 检查项目规范合规性..."

# 运行合规性检查
python src/scripts/check_compliance.py

if [ $? -ne 0 ]; then
    echo "❌ 提交被拒绝：项目不符合规范"
    exit 1
fi

echo "✅ 项目符合规范，允许提交"
```

## 📊 规范执行监控

### 1. **定期审计**
- 每周对工作空间所有项目进行合规性检查
- 生成合规性报告
- 标记不合规项目并限期整改

### 2. **新项目审核**
- 所有新项目创建前必须通过架构审核
- 审核通过后方可开始开发
- 审核内容包括目录结构、命名规范等

### 3. **代码审查标准**
- 代码审查必须包含规范符合性检查
- 不合规的代码不得合并
- 审查人员有责任确保代码符合规范

## 🔄 迁移与整改指南

### 1. **现有项目迁移步骤**
1. 创建标准目录结构
2. 移动文件到相应目录
3. 更新导入路径和配置文件
4. 运行合规性检查
5. 修复发现的问题

### 2. **常见问题整改**
- **问题**：根目录有 `.py` 脚本文件
  **整改**：移动到 `src/scripts/`，更新入口脚本

- **问题**：根目录有 `.md` 文档文件
  **整改**：移动到 `docs/` 相应子目录

- **问题**：根目录有图片文件
  **整改**：移动到 `outputs/visualizations/`

- **问题**：缺少必要目录
  **整改**：创建缺失的目录结构

## 📈 规范演进机制

### 1. **规范更新流程**
1. 提出规范修改建议
2. 工作空间成员讨论
3. 更新本规范文档
4. 通知所有项目负责人
5. 设定整改期限

### 2. **例外申请流程**
1. 提交例外申请说明
2. 说明技术原因和替代方案
3. 获得架构委员会批准
4. 记录例外情况

## 📞 支持与反馈

### 1. **规范咨询**
- 如有疑问，请参考本规范文档
- 可咨询架构委员会成员
- 查看现有合规项目示例

### 2. **问题反馈**
- 发现规范问题请及时反馈
- 提出改进建议
- 报告不合规项目

### 3. **培训资源**
- 新成员必须阅读本规范
- 定期组织规范培训
- 提供规范检查工具使用指导

---

## 📌 生效与执行

**生效日期**：2026年1月30日  
**适用范围**：工作空间所有项目  
**执行责任**：所有项目负责人和开发人员  
**审查周期**：每周一次  

**注意**：本规范是工作空间开发质量的基础保障，所有成员必须严格遵守。违反规范将影响项目质量和团队协作效率。