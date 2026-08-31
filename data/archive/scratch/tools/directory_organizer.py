import os
import sys
import shutil
import json
import re
import py_compile
from datetime import datetime
import argparse

def create_backup(target_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{target_dir}_backup_{timestamp}"
    print(f"[*] 创建防御性备份: {backup_dir}")
    shutil.copytree(target_dir, backup_dir)
    return backup_dir

def get_category_path(filename):
    ext = os.path.splitext(filename)[1].lower()
    
    # 核心忽略名单，遵循 GEMINI.md 神父法统，保持在根目录
    core_files = ['k8qe_main.py', 'pipeline_runner.py', 'main_predictor.py', 'model_engine.py', 'feature_engineering.py', 'run_today.py', 'requirements.txt']
    if filename in core_files:
        return None
        
    if ext in ['.py', '.sh', '.bat', '.js']:
        return 'tools' # 默认测试或辅助脚本归入 tools
    elif ext in ['.json', '.yaml', '.yml', '.ini', '.cfg']:
        return 'config'
    elif ext in ['.txt', '.md', '.csv']:
        return 'logs'
    
    return None

def main():
    parser = argparse.ArgumentParser(description="量化系统自动化目录整理工具")
    parser.add_argument("--target", required=True, help="目标系统目录绝对路径")
    parser.add_argument("--backup", action="store_true", help="是否创建防御性备份")
    parser.add_argument("--dry-run", action="store_true", help="仅打印执行计划，不实际修改")
    args = parser.parse_args()

    target_dir = args.target
    if not os.path.isdir(target_dir):
        print(f"[-] 错误: 目标目录 {target_dir} 不存在。")
        sys.exit(1)
        
    print(f"========== 启动量化系统结构自愈引警 ==========")
    print(f"目标目录: {target_dir}")
    
    if args.backup and not args.dry_run:
        create_backup(target_dir)

    # 1. 分类映射计算
    mapping = {} # old_name -> new_relative_path
    
    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)
        if not os.path.isfile(item_path):
            continue
            
        cat = get_category_path(item)
        if cat:
            mapping[item] = f"{cat}/{item}"
            
    if not mapping:
        print("[+] 根目录已高度秩序化，无游离文件需整理。")
        sys.exit(0)
        
    print("\n[*] 拟移动的文件映射路线:")
    for old, new in mapping.items():
        print(f"    - {old}  =>  {new}")

    if not args.dry_run:
        # 实际移动文件
        for old, new in mapping.items():
            old_path = os.path.join(target_dir, old)
            new_path = os.path.join(target_dir, os.path.normpath(new))
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            
    # 2. 启发式路径修正
    print("\n[*] 开始深度扫描与路径依赖修正...")
    script_extensions = ['.py', '.sh', '.js', '.bat']
    modified_files = []
    failed_compilations = []
    
    for root, dirs, files in os.walk(target_dir):
        # 忽略环境与备份目录
        if '.git' in root or '.venv' in root or '__pycache__' in root:
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in script_extensions:
                continue
                
            script_path = os.path.join(root, file)
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"    [!] 无法读取文件 {script_path}: {e}")
                continue
                
            is_modified = False
            for old_name, new_rel_path in mapping.items():
                pattern = r'(["\']){}(["\'])'.format(re.escape(old_name))
                def replacer(match):
                    nonlocal is_modified
                    is_modified = True
                    quote = match.group(1)
                    return f"{quote}{new_rel_path}{quote}"
                
                content = re.sub(pattern, replacer, content)
                
            if is_modified:
                modified_files.append(script_path)
                if not args.dry_run:
                    with open(script_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                    # 对Python文件执行AST语法防线检测
                    if ext == '.py':
                        try:
                            py_compile.compile(script_path, doraise=True)
                        except py_compile.PyCompileError as e:
                            failed_compilations.append((script_path, str(e)))

    print("\n========== 报告总结 ==========")
    print(f"被移动的文件数量: {len(mapping)}")
    print(f"被修复引用的脚本数量: {len(modified_files)}")
    for sf in modified_files:
        print(f"    [已修正] {sf}")
        
    if failed_compilations:
        print("\n[!!!] 严重警告: 发现语法编译被破坏的文件 (需人工干预):")
        for f, err in failed_compilations:
            print(f"    {f}")
            print(f"    原因: {err}")
    else:
        print("\n[+] 语法防线校验通过。所有自动修复逻辑均保持编译正确。")
        
    # 生成报告文档
    if not args.dry_run:
        report_path = os.path.join(target_dir, "logs", f"organization_report_{datetime.now().strftime('%Y%m%d')}.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("# 系统目录整理与自愈报告\n\n")
            rf.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            rf.write("## 物理空间位移记录\n")
            for old, new in mapping.items():
                rf.write(f"- `{old}` => `{new}`\n")
            rf.write("\n## 路径依赖修复记录\n")
            for sf in modified_files:
                rf.write(f"- [已修正] {sf}\n")
            if failed_compilations:
                rf.write("\n## ⚠️ 语法损坏告警\n")
                for f, err in failed_compilations:
                    rf.write(f"- `{f}`: {err}\n")
            else:
                rf.write("\n## ✅ 验证状态\n语法防线校验通过，未发现损坏。\n")
        print(f"\n[+] 详细结构化报告已生成至: {report_path}")

if __name__ == "__main__":
    main()
