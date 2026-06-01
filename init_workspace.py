#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作空间初始化脚本
为新成员或新环境快速设置工作空间规范环境

使用方法:
    python init_workspace.py [--all] [--project 项目路径]

参数:
    --all: 为工作空间所有项目初始化
    --project: 为指定项目初始化
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
import shutil

class WorkspaceInitializer:
    """工作空间初始化器"""
    
    def __init__(self, workspace_path):
        self.workspace_path = Path(workspace_path).absolute()
        self.tools_installed = False
        
    def print_banner(self):
        """打印欢迎横幅"""
        print("=" * 60)
        print("🏢 工作空间规范环境初始化")
        print("=" * 60)
        print(f"工作空间: {self.workspace_path}")
        print("")
    
    def check_prerequisites(self):
        """检查前提条件"""
        print("🔍 检查前提条件...")
        
        prerequisites = {
            'Python 3.8+': self.check_python_version(),
            'Git': self.check_git(),
            '工作空间目录': self.check_workspace_exists(),
        }
        
        all_ok = True
        for name, status in prerequisites.items():
            if status:
                print(f"  ✅ {name}")
            else:
                print(f"  ❌ {name}")
                all_ok = False
        
        return all_ok
    
    def check_python_version(self):
        """检查Python版本"""
        try:
            version = sys.version_info
            return version.major == 3 and version.minor >= 8
        except:
            return False
    
    def check_git(self):
        """检查Git"""
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def check_workspace_exists(self):
        """检查工作空间目录"""
        return self.workspace_path.exists()
    
    def install_tools(self):
        """安装规范工具"""
        if self.tools_installed:
            return
        
        print("\n🛠️  安装规范工具...")
        
        # 检查必要文件是否存在
        required_files = [
            'WORKSPACE_RULES.md',
            'check_all_projects.py',
            'setup_git_hooks.py',
            'monitor_compliance.py',
            'pre-commit-template.sh',
        ]
        
        for filename in required_files:
            filepath = self.workspace_path / filename
            if filepath.exists():
                print(f"  ✅ {filename}")
            else:
                print(f"  ❌ {filename} 不存在")
                # 在实际使用中，可以从模板创建或从仓库下载
        
        self.tools_installed = True
    
    def setup_project(self, project_path):
        """为单个项目设置规范环境"""
        project_path = Path(project_path).absolute()
        project_name = project_path.name
        
        print(f"\n📦 初始化项目: {project_name}")
        
        # 1. 创建标准目录结构
        print("  1. 创建目录结构...")
        required_dirs = ['src/scripts', 'src/frontend', 'docs', 'tests', 
                        'outputs/visualizations', 'outputs/predictions', 
                        'outputs/reports', 'outputs/logs', 'configs', 'data']
        
        for dir_path in required_dirs:
            full_path = project_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"    ✅ 创建: {dir_path}")
        
        # 2. 复制合规性检查脚本
        print("  2. 设置合规性检查...")
        check_script_src = self.workspace_path / '3d' / 'src' / 'scripts' / 'check_compliance.py'
        check_script_dst = project_path / 'src' / 'scripts' / 'check_compliance.py'
        
        if check_script_src.exists():
            shutil.copy2(check_script_src, check_script_dst)
            print(f"    ✅ 复制检查脚本")
        else:
            # 创建基本检查脚本
            self.create_basic_check_script(check_script_dst)
            print(f"    ✅ 创建基本检查脚本")
        
        # 3. 创建README.md（如果不存在）
        print("  3. 创建项目文档...")
        readme_path = project_path / 'README.md'
        if not readme_path.exists():
            self.create_readme_template(readme_path, project_name)
            print(f"    ✅ 创建README.md")
        
        # 4. 创建.gitignore（如果不存在）
        print("  4. 设置Git忽略...")
        gitignore_path = project_path / '.gitignore'
        if not gitignore_path.exists():
            self.create_gitignore_template(gitignore_path)
            print(f"    ✅ 创建.gitignore")
        
        # 5. 设置Git钩子（如果是Git仓库）
        print("  5. 设置Git钩子...")
        git_dir = project_path / '.git'
        if git_dir.exists():
            # 运行设置脚本
            setup_script = self.workspace_path / 'setup_git_hooks.py'
            if setup_script.exists():
                try:
                    subprocess.run([sys.executable, str(setup_script), str(project_path), '--force'],
                                 capture_output=True, text=True)
                    print(f"    ✅ 安装Git预提交钩子")
                except:
                    print(f"    ⚠️  Git钩子安装失败")
            else:
                print(f"    ⚠️  找不到Git钩子安装脚本")
        else:
            print(f"    ℹ️  不是Git仓库，跳过钩子安装")
        
        # 6. 运行初始合规性检查
        print("  6. 运行初始合规性检查...")
        try:
            result = subprocess.run([sys.executable, str(check_script_dst), '--fix'],
                                  cwd=project_path,
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ 项目符合规范")
            else:
                print(f"    ⚠️  项目需要手动修复一些问题")
                print(f"      输出: {result.stdout[:100]}...")
        except Exception as e:
            print(f"    ⚠️  检查脚本执行失败: {e}")
        
        print(f"\n🎉 项目 {project_name} 初始化完成!")
    
    def create_basic_check_script(self, script_path):
        """创建基本检查脚本"""
        template = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目规范合规性检查工具
检查项目是否符合工作空间全局规范
"""

import os
import sys
from pathlib import Path

def main():
    """主函数"""
    project_path = Path.cwd()
    violations = []
    warnings = []
    
    print("🔍 检查项目规范合规性...")
    
    # 检查必要目录
    required_dirs = ['src', 'docs', 'tests', 'outputs', 'configs', 'data']
    for dir_name in required_dirs:
        dir_path = project_path / dir_name
        if not dir_path.exists():
            violations.append(f"缺失必要目录: {dir_name}")
    
    # 检查根目录禁止文件
    prohibited_ext = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico']
    prohibited_ext += ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg']
    prohibited_ext += ['.bat', '.cmd', '.ps1', '.sh']
    prohibited_ext += ['.log', '.tmp', '.temp', '.cache']
    
    for item in project_path.iterdir():
        if item.is_file():
            ext = item.suffix.lower()
            if ext in prohibited_ext:
                violations.append(f"根目录禁止文件: {item.name}")
    
    # 检查脚本文件位置
    src_path = project_path / 'src'
    if src_path.exists():
        for item in src_path.iterdir():
            if item.is_file() and item.suffix == '.py':
                violations.append(f"脚本应放在src/scripts/: {item.name}")
    
    # 输出结果
    if violations:
        print("❌ 合规性检查失败:")
        for violation in violations:
            print(f"  • {violation}")
        print("\\n💡 建议:")
        print("  1. 创建缺失的目录")
        print("  2. 将禁止文件移动到正确目录")
        print("  3. 将脚本文件移动到src/scripts/")
        return 1
    else:
        print("✅ 项目符合工作空间规范")
        return 0

if __name__ == "__main__":
    sys.exit(main())
'''
        
        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(template)
    
    def create_readme_template(self, readme_path, project_name):
        """创建README模板"""
        template = f"""# {project_name}

## 📋 项目简介

简要描述项目功能和用途。

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行项目
```bash
python main.py
```

### 运行规范检查
```bash
python src/scripts/check_compliance.py
```

## 📁 项目结构

```
{project_name}/
├── src/                    # 源代码
│   ├── scripts/           # 可执行脚本
│   ├── frontend/          # 前端代码
│   ├── core/              # 核心功能
│   ├── models/            # 预测模型
│   └── utils/             # 工具函数
├── docs/                  # 文档
├── tests/                 # 测试
├── outputs/               # 输出结果
├── configs/               # 配置文件
├── data/                  # 数据文件
├── main.py               # 主入口
├── requirements.txt      # 依赖文件
└── README.md            # 本文件
```

## 📚 相关文档

- [工作空间规范]({self.workspace_path}/WORKSPACE_RULES.md)
- [编码规范]({self.workspace_path}/3d/docs/specifications/CODING_STANDARDS.md)

## ⚠️ 重要规范

### 文件生成禁令
1. **严禁**在根目录生成图片文件（`.png`, `.jpg`, `.gif`等）
2. **严禁**在根目录生成JSON配置文件
3. **严禁**在根目录生成BAT批处理脚本
4. **严禁**在根目录生成临时日志文件

### 目录结构规范
- 所有脚本文件必须放入 `src/scripts/` 目录
- 所有前端代码必须放入 `src/frontend/` 目录
- 所有输出文件必须放入 `outputs/` 目录

## 🛠️ 开发指南

### 新增功能
1. 检查现有模块，避免重复创建
2. 在已有模块上扩展功能
3. 遵循编码规范要求
4. 及时清理临时文件

### 代码提交
1. 确保代码符合规范
2. 删除所有临时文件
3. 更新相关文档
4. 添加有意义的提交信息

---

**注意**：本项目遵循工作空间全局开发规范，请确保所有开发活动符合规范要求。
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(template)
    
    def create_gitignore_template(self, gitignore_path):
        """创建.gitignore模板"""
        template = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/
.env
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Outputs
outputs/
!outputs/.gitkeep

# Data files
*.csv
*.xlsx
*.xls
*.parquet
*.feather

# Logs
*.log
*.tmp
*.temp

# 工作空间规范：禁止在根目录生成的文件
# 图片文件应放在 outputs/visualizations/
*.png
*.jpg
*.jpeg
*.gif
*.bmp

# 配置文件应放在 configs/
*.json
*.yaml
*.yml
*.toml
*.ini
*.cfg

# 批处理脚本应放在 configs/
*.bat
*.cmd
*.ps1
"""
        
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(template)
    
    def find_all_projects(self):
        """查找所有项目"""
        projects = []
        exclude_patterns = ['.git', '__pycache__', 'venv', 'env', 'node_modules']
        
        for item in self.workspace_path.iterdir():
            if item.is_dir():
                # 检查是否在排除列表中
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern in item.name:
                        should_exclude = True
                        break
                
                if should_exclude:
                    continue
                
                # 检查是否是项目
                has_src = (item / 'src').exists()
                has_readme = (item / 'README.md').exists()
                has_main = (item / 'main.py').exists()
                
                if has_src or has_readme or has_main:
                    projects.append(item)
        
        return projects

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='工作空间初始化脚本')
    parser.add_argument('--all', action='store_true', help='为所有项目初始化')
    parser.add_argument('--project', type=str, help='为指定项目初始化')
    parser.add_argument('--workspace', type=str, default='.', help='工作空间路径')
    
    args = parser.parse_args()
    
    initializer = WorkspaceInitializer(args.workspace)
    initializer.print_banner()
    
    # 检查前提条件
    if not initializer.check_prerequisites():
        print("\n❌ 前提条件检查失败，请先解决问题")
        sys.exit(1)
    
    # 安装工具
    initializer.install_tools()
    
    if args.all:
        # 为所有项目初始化
        projects = initializer.find_all_projects()
        
        if not projects:
            print("\n⚠️  未找到任何项目")
            sys.exit(0)
        
        print(f"\n🔍 找到 {len(projects)} 个项目:")
        for project in projects:
            print(f"  • {project.name}")
        
        print("\n开始初始化所有项目...")
        for project in projects:
            initializer.setup_project(project)
        
        print("\n🎉 所有项目初始化完成!")
        
    elif args.project:
        # 为指定项目初始化
        project_path = Path(args.project).absolute()
        if not project_path.exists():
            print(f"\n❌ 项目路径不存在: {project_path}")
            sys.exit(1)
        
        initializer.setup_project(project_path)
        
    else:
        # 交互式选择
        print("\n请选择初始化模式:")
        print("  1. 为当前目录项目初始化")
        print("  2. 为工作空间所有项目初始化")
        print("  3. 指定项目路径初始化")
        
        choice = input("\n请选择 (1/2/3): ").strip()
        
        if choice == '1':
            initializer.setup_project(Path.cwd())
        elif choice == '2':
            projects = initializer.find_all_projects()
            if projects:
                for project in projects:
                    initializer.setup_project(project)
                print("\n🎉 所有项目初始化完成!")
            else:
                print("\n⚠️  未找到任何项目")
        elif choice == '3':
            project_path = input("请输入项目路径: ").strip()
            if project_path:
                initializer.setup_project(project_path)
            else:
                print("❌ 未提供项目路径")
        else:
            print("❌ 无效选择")
    
    print("\n📚 后续步骤:")
    print("  1. 阅读工作空间规范: WORKSPACE_RULES.md")
    print("  2. 运行合规性检查: python check_all_projects.py")
    print("  3. 设置Git钩子: python setup_git_hooks.py --all")
    print("  4. 设置监控: python monitor_compliance.py --daily")

if __name__ == "__main__":
    main()