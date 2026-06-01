#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作空间项目合规性批量检查工具
检查工作空间下所有项目的规范符合性

使用方法:
    python check_all_projects.py [--fix] [--report] [--exclude pattern]

参数:
    --fix: 自动修复可修复的问题
    --report: 生成详细报告
    --exclude: 排除匹配模式的项目
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
import subprocess

class WorkspaceComplianceChecker:
    """工作空间合规性检查器"""
    
    def __init__(self, workspace_path):
        self.workspace_path = Path(workspace_path)
        self.results = {}
        self.summary = {
            'total_projects': 0,
            'compliant': 0,
            'non_compliant': 0,
            'warnings': 0,
            'fixed': 0,
            'excluded': 0
        }
    
    def find_projects(self, exclude_patterns=None):
        """查找工作空间中的所有项目"""
        print("🔍 扫描工作空间中的项目...")
        
        projects = []
        exclude_patterns = exclude_patterns or []
        
        for item in self.workspace_path.iterdir():
            if item.is_dir():
                # 检查是否在排除列表中
                should_exclude = False
                for pattern in exclude_patterns:
                    if pattern in item.name:
                        should_exclude = True
                        break
                
                if should_exclude:
                    print(f"  ⏭️  排除项目: {item.name}")
                    self.summary['excluded'] += 1
                    continue
                
                # 检查是否是项目（有src目录或README.md）
                has_src = (item / 'src').exists()
                has_readme = (item / 'README.md').exists()
                has_main = (item / 'main.py').exists()
                
                if has_src or has_readme or has_main:
                    projects.append(item)
                    print(f"  📁 发现项目: {item.name}")
        
        self.summary['total_projects'] = len(projects)
        return projects
    
    def check_project(self, project_path, fix=False):
        """检查单个项目"""
        project_name = project_path.name
        print(f"\n📋 检查项目: {project_name}")
        
        # 运行项目的合规性检查
        check_script = project_path / 'src' / 'scripts' / 'check_compliance.py'
        
        if check_script.exists():
            # 使用项目自带的检查脚本
            cmd = [sys.executable, str(check_script)]
            if fix:
                cmd.append('--fix')
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=30
                )
                
                self.results[project_name] = {
                    'path': str(project_path),
                    'exit_code': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'has_check_script': True,
                    'timestamp': datetime.now().isoformat()
                }
                
                if result.returncode == 0:
                    print(f"  ✅ {project_name}: 符合规范")
                    self.summary['compliant'] += 1
                else:
                    print(f"  ❌ {project_name}: 不符合规范")
                    print(f"     输出: {result.stdout[:200] if result.stdout else '无输出'}")
                    self.summary['non_compliant'] += 1
                
                # 统计修复数量
                if fix and '自动修复了' in result.stdout:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if '自动修复了' in line:
                            try:
                                fixed = int(line.split('自动修复了')[1].split('个')[0].strip())
                                self.summary['fixed'] += fixed
                            except:
                                pass
                
            except Exception as e:
                self.results[project_name] = {
                    'path': str(project_path),
                    'error': str(e),
                    'has_check_script': True,
                    'timestamp': datetime.now().isoformat()
                }
                print(f"  ⚠️  {project_name}: 检查脚本执行错误 - {e}")
                self.summary['non_compliant'] += 1
        else:
            # 项目没有检查脚本，进行基本检查
            self.results[project_name] = {
                'path': str(project_path),
                'warning': '项目缺少合规性检查脚本',
                'has_check_script': False,
                'timestamp': datetime.now().isoformat()
            }
            print(f"  ⚠️  {project_name}: 缺少合规性检查脚本")
            self.summary['warnings'] += 1
            self.summary['non_compliant'] += 1
    
    def generate_report(self, output_file=None):
        """生成详细报告"""
        print("\n" + "=" * 60)
        print("📊 工作空间合规性检查报告")
        print("=" * 60)
        
        # 打印摘要
        print(f"\n📈 检查摘要:")
        print(f"  总项目数: {self.summary['total_projects']}")
        print(f"  符合规范: {self.summary['compliant']}")
        print(f"  不符合规范: {self.summary['non_compliant']}")
        print(f"  警告: {self.summary['warnings']}")
        print(f"  自动修复: {self.summary['fixed']} 个问题")
        print(f"  排除项目: {self.summary['excluded']}")
        
        # 打印不符合规范的项目
        non_compliant = []
        for project_name, result in self.results.items():
            if result.get('exit_code', 1) != 0 or 'warning' in result:
                non_compliant.append(project_name)
        
        if non_compliant:
            print(f"\n❌ 不符合规范的项目 ({len(non_compliant)}个):")
            for project in non_compliant:
                print(f"  • {project}")
        
        # 打印缺少检查脚本的项目
        no_script = []
        for project_name, result in self.results.items():
            if not result.get('has_check_script', False):
                no_script.append(project_name)
        
        if no_script:
            print(f"\n⚠️  缺少检查脚本的项目 ({len(no_script)}个):")
            for project in no_script:
                print(f"  • {project}")
        
        # 生成JSON报告
        if output_file:
            report_data = {
                'summary': self.summary,
                'results': self.results,
                'workspace_path': str(self.workspace_path),
                'check_time': datetime.now().isoformat(),
                'python_version': sys.version
            }
            
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 详细报告已保存: {output_file}")
        
        print("=" * 60)
        
        # 返回状态码
        if self.summary['non_compliant'] > 0:
            return 1
        return 0
    
    def create_compliance_script_template(self, project_path):
        """为项目创建合规性检查脚本模板"""
        template = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目规范合规性检查工具
检查项目是否符合工作空间全局规范
"""

import os
import sys
from pathlib import Path

def check_compliance():
    """检查项目合规性"""
    project_path = Path.cwd()
    violations = []
    warnings = []
    
    # 检查必要目录
    required_dirs = ['src', 'docs', 'tests', 'outputs', 'configs', 'data']
    for dir_name in required_dirs:
        if not (project_path / dir_name).exists():
            violations.append(f"缺失目录: {dir_name}")
    
    # 检查根目录禁止文件
    prohibited_ext = ['.png', '.jpg', '.json', '.bat', '.log', '.csv']
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
            print(f"  - {violation}")
        return False
    else:
        print("✅ 项目符合规范")
        return True

if __name__ == "__main__":
    success = check_compliance()
    sys.exit(0 if success else 1)
'''
        
        scripts_dir = project_path / 'src' / 'scripts'
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = scripts_dir / 'check_compliance.py'
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(template)
        
        print(f"  📝 为 {project_path.name} 创建检查脚本模板")
        return script_file

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='工作空间项目合规性批量检查')
    parser.add_argument('--fix', action='store_true', help='自动修复可修复的问题')
    parser.add_argument('--report', type=str, help='生成JSON报告文件')
    parser.add_argument('--exclude', nargs='+', help='排除匹配模式的项目')
    parser.add_argument('--workspace', type=str, default='.', help='工作空间路径')
    parser.add_argument('--create-templates', action='store_true', help='为缺少检查脚本的项目创建模板')
    
    args = parser.parse_args()
    
    workspace_path = Path(args.workspace).absolute()
    if not workspace_path.exists():
        print(f"❌ 工作空间路径不存在: {workspace_path}")
        sys.exit(1)
    
    print(f"🏢 工作空间: {workspace_path}")
    
    checker = WorkspaceComplianceChecker(workspace_path)
    
    # 查找项目
    projects = checker.find_projects(args.exclude)
    
    if not projects:
        print("⚠️  未找到任何项目")
        sys.exit(0)
    
    # 检查每个项目
    for project in projects:
        checker.check_project(project, args.fix)
    
    # 为缺少检查脚本的项目创建模板
    if args.create_templates:
        print("\n🛠️  为缺少检查脚本的项目创建模板...")
        for project_name, result in checker.results.items():
            if not result.get('has_check_script', False):
                project_path = Path(result['path'])
                checker.create_compliance_script_template(project_path)
    
    # 生成报告
    exit_code = checker.generate_report(args.report)
    
    # 建议
    print("\n💡 建议:")
    if checker.summary['non_compliant'] > 0:
        print("  1. 运行 `python check_all_projects.py --fix` 自动修复问题")
        print("  2. 运行 `python check_all_projects.py --create-templates` 创建检查脚本")
        print("  3. 查看详细报告了解具体问题")
    else:
        print("  所有项目都符合规范，继续保持！")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()