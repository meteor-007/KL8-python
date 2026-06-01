#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git钩子安装脚本
为工作空间中的项目安装预提交规范检查钩子

使用方法:
    python setup_git_hooks.py [项目路径] [--all] [--force]

参数:
    项目路径: 指定要安装钩子的项目路径
    --all: 为工作空间所有项目安装钩子
    --force: 强制覆盖现有钩子
"""

import os
import sys
import argparse
import shutil
from pathlib import Path

def install_pre_commit_hook(project_path, force=False):
    """为项目安装预提交钩子"""
    project_path = Path(project_path).absolute()
    project_name = project_path.name
    
    print(f"📦 为项目安装Git钩子: {project_name}")
    
    # 检查是否是Git仓库
    git_dir = project_path / '.git'
    if not git_dir.exists():
        print(f"  ⚠️  {project_name} 不是Git仓库，跳过")
        return False
    
    # 检查hooks目录
    hooks_dir = git_dir / 'hooks'
    hooks_dir.mkdir(exist_ok=True)
    
    # 预提交钩子路径
    pre_commit_hook = hooks_dir / 'pre-commit'
    
    # 检查是否已存在钩子
    if pre_commit_hook.exists() and not force:
        print(f"  ⚠️  {project_name} 已存在预提交钩子，使用 --force 覆盖")
        return False
    
    # 读取模板
    template_path = Path(__file__).parent / 'pre-commit-template.sh'
    if not template_path.exists():
        print(f"  ❌ 找不到钩子模板: {template_path}")
        return False
    
    # 复制模板
    try:
        shutil.copy2(template_path, pre_commit_hook)
        
        # 设置执行权限（在Windows上可能需要其他方式）
        if sys.platform != 'win32':
            os.chmod(pre_commit_hook, 0o755)
        
        print(f"  ✅ 成功安装预提交钩子到 {project_name}")
        return True
    except Exception as e:
        print(f"  ❌ 安装失败: {e}")
        return False

def find_projects(workspace_path, exclude_patterns=None):
    """查找工作空间中的所有项目"""
    workspace_path = Path(workspace_path).absolute()
    projects = []
    exclude_patterns = exclude_patterns or ['.git', '__pycache__', 'venv', 'env']
    
    for item in workspace_path.iterdir():
        if item.is_dir():
            # 检查是否在排除列表中
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in item.name:
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
            
            # 检查是否是项目（有.git目录或src目录）
            has_git = (item / '.git').exists()
            has_src = (item / 'src').exists()
            has_readme = (item / 'README.md').exists()
            
            if has_git or has_src or has_readme:
                projects.append(item)
    
    return projects

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Git钩子安装脚本')
    parser.add_argument('path', nargs='?', default='.', help='项目路径或工作空间路径')
    parser.add_argument('--all', action='store_true', help='为工作空间所有项目安装钩子')
    parser.add_argument('--force', action='store_true', help='强制覆盖现有钩子')
    parser.add_argument('--exclude', nargs='+', help='排除的项目模式')
    
    args = parser.parse_args()
    
    target_path = Path(args.path).absolute()
    
    if not target_path.exists():
        print(f"❌ 路径不存在: {target_path}")
        sys.exit(1)
    
    print(f"🏢 工作空间: {target_path}")
    
    if args.all:
        # 为所有项目安装钩子
        print("🔍 查找工作空间中的所有项目...")
        projects = find_projects(target_path, args.exclude)
        
        if not projects:
            print("⚠️  未找到任何项目")
            sys.exit(0)
        
        print(f"找到 {len(projects)} 个项目:")
        for project in projects:
            print(f"  • {project.name}")
        
        print("\n开始安装Git钩子...")
        installed = 0
        failed = 0
        
        for project in projects:
            if install_pre_commit_hook(project, args.force):
                installed += 1
            else:
                failed += 1
        
        print(f"\n📊 安装完成:")
        print(f"  成功: {installed}")
        print(f"  失败: {failed}")
        
        if installed > 0:
            print("\n💡 钩子使用说明:")
            print("  1. 钩子会在每次git commit前自动运行")
            print("  2. 如果项目不符合规范，提交将被拒绝")
            print("  3. 运行项目检查脚本查看具体问题: python src/scripts/check_compliance.py")
        
    else:
        # 为单个项目安装钩子
        if not (target_path / '.git').exists():
            print(f"❌ {target_path.name} 不是Git仓库")
            print("💡 请先初始化Git仓库: git init")
            sys.exit(1)
        
        install_pre_commit_hook(target_path, args.force)
    
    print("\n📚 工作空间规范文档:")
    print("  查看 WORKSPACE_RULES.md 了解完整规范")
    print("  运行 check_all_projects.py 检查所有项目")

if __name__ == "__main__":
    main()