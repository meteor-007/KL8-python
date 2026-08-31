import subprocess
import sys
import os

# 确保在 UTF-8 编码下执行
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════
# V15.0 七大子系统调度
#   - '点位+跟随+遗漏系统合并' + '全新-20260430-分析' → '全新+点位'
#   - '微积分' + '随机森林算法' 已被取代，当前统一平台为 'kl8_math_system' (极简主脑)
#   - 极简主脑入口: run_daily.py
#   - 重点点位分析 & K8-Ultimate-Sniper 已因过度拟合被废弃
# ═══════════════════════════════════════════════════════════════════
BATCHES = [
    {
        "name": "首发列阵 (轻量/短周期模型)",
        "jobs": [
            {"dir": r"全新+点位", "cmd": ["python", "main.py"]},
            {"dir": r"定金选2-分析", "cmd": ["python", "main_predictor.py"]},
        ]
    },
    {
        "name": "中枢列阵 (拓扑/空间模型)",
        "jobs": [
            {"dir": r"开号位置+形态+曲线图", "cmd": ["python", "main.py"]},
            {"dir": r"kl8_math_system", "cmd": ["python", "run_daily.py"]},
        ]
    },
    {
        "name": "重载列阵 (重型算力/高维复盘)",
        "jobs": [
            {"dir": r"archive\统计次数-复盘\ensemble", "cmd": ["python", "main.py", "--run"]},
        ]
    }
]

BASE_DIR = r"D:\Dpanqianyi\Python-Project"

def run_batch(batch_info):
    print(f"\n{'='*60}")
    print(f"🚀 正在启动: {batch_info['name']}")
    print(f"{'='*60}")
    
    processes = []
    
    for job in batch_info['jobs']:
        job_dir = os.path.join(BASE_DIR, job['dir'])
        if not os.path.isdir(job_dir):
            print(f"  [⚠️] 子系统目录不存在，跳过: {job['dir']}")
            continue
        print(f"  [+] 启动子系统: {job['dir']} -> {' '.join(job['cmd'])}")
        
        try:
            p = subprocess.Popen(
                job['cmd'],
                cwd=job_dir,
                env=os.environ,
                shell=False
            )
            processes.append({"name": job['dir'], "process": p})
        except Exception as e:
            print(f"  [!] 启动 {job['dir']} 失败: {str(e)}")

    # 等待当前批次所有进程结束
    for p_info in processes:
        p_info['process'].wait()
        if p_info['process'].returncode != 0:
            print(f"  [❌] 子系统 {p_info['name']} 异常退出，返回码: {p_info['process'].returncode}")
        else:
            print(f"  [✅] 子系统 {p_info['name']} 执行成功。")
            
    print(f"\n🎯 {batch_info['name']} 全部收网完毕。")

if __name__ == "__main__":
    print("🧬 快乐8预测系统 — 七大子系统全局调度器 V15.0")
    print("特性：三批次隔离、进程级防爆、强制 UTF-8 编码、7系统精简架构、UPP统一平台")
    
    for batch in BATCHES:
        run_batch(batch)
        
    print("\n✅ 所有阶段执行完毕。请前往执行阶段三（跨域深度聚合）。")
