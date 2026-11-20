# -*- coding: utf-8 -*-
"""
快乐8 每日点位与三高特征 Excel 自动解析与落库 Python 终端
==============================================================================
支持:
  1. 扫描 validation/file (或自定义目录) 下的最新 Excel 表格 (*快乐8点位图* Sheet);
  2. 提取期号、K 列 20 码点位、以及三高特征池（重复高、左右边高、冷号高）;
  3. 原子落盘更新 daily_points.txt 与 storage/points/tri_high_points.json;
  4. 无新文件时自动平稳降级 (Graceful Degradation)，绝不抛异常阻断日常预测流水线。
"""
import os
import sys
import subprocess
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_HERE) if os.path.basename(_HERE) == "scripts" else _HERE
PS_SCRIPT = os.path.join(_HERE, "import_daily_excel.ps1")

def run_excel_import(file_path: str = None, file_dir: str = None, check_only: bool = False, quiet: bool = False) -> int:
    """调用系统 PowerShell + COM 高性能双轨引擎执行解析"""
    if not os.path.exists(PS_SCRIPT):
        print(f"[ERROR] 找不到底层解析引擎: {PS_SCRIPT}")
        return 1
        
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", PS_SCRIPT]
    if file_path:
        cmd.extend(["-FilePath", file_path])
    if file_dir:
        cmd.extend(["-FileDir", file_dir])
    if check_only:
        cmd.append("-CheckOnly")
    if quiet:
        cmd.append("-Quiet")
        
    res = subprocess.run(cmd)
    return res.returncode

def main():
    parser = argparse.ArgumentParser(description="快乐8 最新点位与三高特征 Excel 自动解析终端")
    parser.add_argument("--file", "-f", type=str, default="", help="指定待解析的 Excel 文件路径")
    parser.add_argument("--dir", "-d", type=str, default="", help="指定扫描目录（默认 validation/file）")
    parser.add_argument("--check-only", "-c", action="store_true", help="仅预览解析结果，不写入落盘")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    
    args = parser.parse_args()
    code = run_excel_import(
        file_path=args.file,
        file_dir=args.dir,
        check_only=args.check_only,
        quiet=args.quiet
    )
    sys.exit(code)

if __name__ == "__main__":
    main()
