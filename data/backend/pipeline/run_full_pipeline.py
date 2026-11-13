#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 每日全流程一键执行器 v4.3
=================================
用法：在项目 data 目录下执行 python -m backend.pipeline.run_full_pipeline
功能：完整执行分析脚本中的所有任务，输出美观详细的控制台报告
"""
from backend.utils.paths import (
    get_cache_dir, get_outputs_dir, get_reports_dir, find_module_script,
)
import os, sys, json, re, datetime, collections, math, traceback, time, subprocess, shutil

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── 双根引导 (Dual-Root Bootstrap) ──
_PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
# 如果在 backend/pipeline 下运行，PROJ 指向根目录
if os.path.basename(_PROJ_DIR) == "pipeline" and os.path.basename(os.path.dirname(_PROJ_DIR)) == "backend":
    PROJ = os.path.dirname(os.path.dirname(_PROJ_DIR))
elif os.path.basename(_PROJ_DIR) == "backend":
    PROJ = os.path.dirname(_PROJ_DIR)
else:
    PROJ = _PROJ_DIR

_BACKEND_DIR = os.path.join(PROJ, "backend")
for _p in [_BACKEND_DIR, PROJ]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.paths import data_path, get_python_runner


def module_active(mid: str) -> bool:
    """模块是否仍在册 —— 判决源唯一：backend/core/module_gate.py 的 MODULE_SEED。

    流水线不用「注释掉任务」的方式退役模块：那样复启就得改代码，
    任务列表会变成与注册表并行的第二份真相源，两边迟早打架。
    导入失败时按活跃处理，绝不因为读不到判决就静默停掉任务。
    """
    try:
        from core.module_gate import is_module_active
        return is_module_active(mid)
    except Exception:
        return True

# ── ANSI 颜色代码 (Windows 10+ 支持) ──
C = {
    'reset':  '\033[0m',
    'bold':   '\033[1m',
    'cyan':   '\033[96m',
    'green':  '\033[92m',
    'yellow': '\033[93m',
    'red':    '\033[91m',
    'blue':   '\033[94m',
    'magenta':'\033[95m',
    'white':  '\033[97m',
    'gray':   '\033[90m',
    'bg_blue':'\033[44m',
}

def c(text, *colors):
    return ''.join(C.get(col,'') for col in colors) + str(text) + C['reset']

def banner(text, color='cyan'):
    width = 75
    line = '═' * width
    print(c(line, color))
    print(c(f'  {text}', color, 'bold'))
    print(c(line, color))

def step(num, title, color='yellow'):
    print()
    print(c(f'┌─── [{num}] {title}', color, 'bold'))
    print(c('└' + '─' * 60, color))

def ok(msg):   print(c('  ✅ ' + msg, 'green'))
def warn(msg): print(c('  ⚠️  ' + msg, 'yellow'))
def err(msg):  print(c('  ❌ ' + msg, 'red'))
def info(msg): print(c('  ℹ  ' + msg, 'blue'))
def sub(msg):  print(c('     ' + msg, 'gray'))

def _resolve_backend_script(*subpath_parts):
    """优先在 backend/ 下寻找脚本，兼容根目录"""
    cand1 = os.path.join(PROJ, 'backend', *subpath_parts)
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.join(PROJ, *subpath_parts)
    if os.path.exists(cand2):
        return cand2
    return cand1

def run_py(script, *args, cwd=None):
    """运行 Python 子脚本，实时打印输出 (带 -u 无缓冲标志)"""
    python_runner = get_python_runner()
    cmd = [python_runner, "-u", script] + list(args)
    cwd = cwd or PROJ
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJ};{_BACKEND_DIR}" + (";" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    print(c(f'  ▶ python {os.path.basename(script)} {" ".join(args)}', 'gray'))
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace'
        )
        for line in proc.stdout:
            print(c('  │ ', 'gray') + line.rstrip())
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        err(f'执行异常: {e}')
        return False

# ══════════════════════════════════════════════════════════
# SECTION 0: 环境预检
# ══════════════════════════════════════════════════════════
def task0_env_check():
    banner('任务0：环境预检与清理')
    
    # 清理锁文件
    locks = [f for f in os.listdir(PROJ) if f.endswith('.excel_lock')]
    if locks:
        for lf in locks:
            try:
                os.remove(os.path.join(PROJ, lf))
                ok(f'已清理锁文件: {lf}')
            except Exception as e:
                warn(f'清理锁文件失败: {lf} - {e}')
    else:
        ok('无残留锁文件')
    
    # 检查关键文件
    key_files = [
        data_path('kl8_history_final.txt'),
        data_path('daily_points.txt'),
        _resolve_backend_script('core', 'pair_selector.py'),
        _resolve_backend_script('pipeline', 'auto_generate_daily_report.py'),
        _resolve_backend_script('data_acquisition', 'generate_hot_excel.py'),
    ]
    all_ok = True
    for f in key_files:
        f_path = f if os.path.isabs(f) else os.path.join(PROJ, f)
        rel_f = os.path.relpath(f_path, PROJ)
        if os.path.exists(f_path):
            ok(f'文件存在: {rel_f}')
        else:
            err(f'文件缺失: {rel_f}')
            all_ok = False
    return all_ok

# ══════════════════════════════════════════════════════════
# SECTION 0.0: 数据校验
# ══════════════════════════════════════════════════════════
def task00_validate():
    banner('任务0.0：数据一致性强制校验与自动修复')
    validator = _resolve_backend_script('utils', 'data_validator.py')
    if os.path.exists(validator):
        run_py(validator, '--auto-fix')
    else:
        warn('data_validator.py 未找到，跳过校验')

# ══════════════════════════════════════════════════════════
# SECTION 1.1: 抓取开奖历史
# ══════════════════════════════════════════════════════════
def task11_fetch():
    banner('任务1.1：双源抓取最新开奖历史')
    script = _resolve_backend_script('data_acquisition', 'fetch_kl8_history.py')
    if os.path.exists(script):
        run_py(script)
    else:
        warn('fetch_kl8_history.py 未找到，跳过')
    
    # 读取最新期号 (活数据在 storage/raw/, 之前指向项目根目录会永远读不到)
    hist_file = data_path('kl8_history_final.txt')
    try:
        with open(hist_file, 'r', encoding='utf-8') as f:
            first = f.readline().strip()
        m = re.search(r'period:(\d+)', first)
        if m:
            ok(f'历史数据最新期号: {m.group(1)}')
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# SECTION 1.2: 热码统计生成
# ══════════════════════════════════════════════════════════
def task12_hot_numbers():
    banner('任务1.2：热码统计生成与同步')
    
    gen_script = _resolve_backend_script('data_acquisition', 'generate_hot_excel.py')
    proc_script = _resolve_backend_script('data_acquisition', 'process_hot_numbers.py')
    
    if os.path.exists(gen_script):
        step('1.2-A', '缺期补偿 (--fill-missing)')
        run_py(gen_script, '--fill-missing')
        
        step('1.2-B', '生成最新期热码统计')
        run_py(gen_script)
    
    if os.path.exists(proc_script):
        step('1.2-C', '批量同步热码到Excel (--sync-all-missing)')
        run_py(proc_script, '--sync-all-missing')
    
    # 验证热码统计目录
    hot_dir = data_path('热码统计')
    if os.path.exists(hot_dir):
        files = sorted([f for f in os.listdir(hot_dir) if f.endswith('.xlsx')], reverse=True)
        if files:
            ok(f'热码统计目录最新文件: {files[0]}')
            info(f'共 {len(files)} 个热码统计文件')
        else:
            err('热码统计目录无xlsx文件！')

# ══════════════════════════════════════════════════════════
# SECTION 1.3-1.5: 历史同步与格式化
# ══════════════════════════════════════════════════════════
def task13_15_sync():
    banner('任务1.3-1.5：历史同步 + 格式化')
    
    sync = _resolve_backend_script('data_acquisition', 'sync_history_to_excel.py')
    fmt  = _resolve_backend_script('format', 'apply_formats.py')
    
    if os.path.exists(sync):
        step('1.3', '历史数据同步到Excel')
        run_py(sync)
    
    roads_prime_sync = _resolve_backend_script('data_acquisition', 'generate_roads_and_prime_stats.py')
    if os.path.exists(roads_prime_sync):
        step('1.4', '012路与质合汇总表同步 (kl8_012_roads_summary.csv & kl8_prime_composite_summary.csv)')
        run_py(roads_prime_sync)

    if os.path.exists(fmt):
        step('1.5', 'Excel增量格式化')
        run_py(fmt)
    
    ok('数据同步与格式化完成')

# ══════════════════════════════════════════════════════════
# SECTION 2: 复盘分析（从缓存读取）
# ══════════════════════════════════════════════════════════
def task2_review():
    banner('任务2：深度复盘 + 命中率统计 (近10期)')
    
    # 读取历史数据
    hist_file = data_path('kl8_history_final.txt')
    history = []
    try:
        with open(hist_file, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'period:(\d+),numbers:([\d\-]+)', line.strip())
                if m:
                    history.append({
                        'period': m.group(1),
                        'numbers': set(int(n) for n in m.group(2).split('-'))
                    })
    except Exception as e:
        err(f'读取历史数据失败: {e}')
        return
    
    # 读取自学习记忆
    mem_file = os.path.join(get_cache_dir(), 'self_learning_state.json')
    records = []
    try:
        with open(mem_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        records = state.get('history', [])
    except Exception:
        warn('读取自学习状态失败')
    
    if not records:
        warn('无历史预测记录可供复盘')
        return
    
    # 构建期号→开奖号码的映射
    hist_map = {h['period']: h['numbers'] for h in history}
    
    print()
    print(c('  ╔══════════════════════════════════════════════════════════╗', 'cyan'))
    print(c('  ║          📊 最近10期实战命中率复盘对账表                ║', 'cyan', 'bold'))
    print(c('  ╚══════════════════════════════════════════════════════════╝', 'cyan'))
    print()
    
    header = f"  {'期号':^8} │ {'目标期':^8} │ {'选2命中':^6} │ {'T5命中':^6} │ {'T12命中':^7} │ {'HE5命中':^7} │ {'方案2爆发':^9}"
    sep    = '  ' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*7 + '┼' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*10
    
    print(c(header, 'white', 'bold'))
    print(c(sep, 'gray'))
    
    trinity_hits5, trinity_hits12, he5_hits, deep_hits = [], [], [], []
    row_count = 0
    seen_targets = set()

    for rec in records[:10]:
        target = str(rec.get('target_issue', ''))
        actual = hist_map.get(target, None)
        if actual is None:
            continue
        # 2026-10-21 统计诚信修复 (Bug#4)：自学习记忆存在同一目标期的重复记录
        # (同一天跑两次全流程即追加两条)，重复行会把同一期命中数算两遍、扭曲均值。
        # 目标期为主键，重复期只保留首次(最新)一条。
        if target in seen_targets:
            warn(f'跳过重复记录: 目标期 {target} 已在表中')
            continue
        seen_targets.add(target)
        
        row_count += 1
        p2  = rec.get('optimal_pick2', [])
        t5  = sorted(rec.get('top5', []))
        t12 = sorted(rec.get('top12', []))
        he5 = sorted(rec.get('b3_final5', []))
        dpicks = sorted(rec.get('deep_picks', []))
        
        hp2 = len(set(p2) & actual) if (p2 and len(p2)==2) else 0
        h5  = len(set(t5)  & actual)
        h12 = len(set(t12) & actual)
        hhe5 = len(set(he5) & actual)
        hdp  = len(set(dpicks) & actual)

        # 2026-10-21 统计诚信修复 (Bug#2 的连带口径问题)：
        # 熔断曾把 top5/top12 抹成空表，空表既不是「推荐了 5 码全没中」也不是有效样本。
        # 空列表一律记 N/A 不入均值，避免把 Lift 假压成 0.00x 触发莫须有的防守模式。
        if t5:   trinity_hits5.append(h5)
        if t12:  trinity_hits12.append(h12)
        if he5:  he5_hits.append(hhe5)
        if dpicks: deep_hits.append(hdp)
        
        def fmt_hit(h, total, threshold=1):
            if h >= threshold:
                return c(f'{h}/{total}', 'green', 'bold')
            else:
                return c(f'{h}/{total}', 'red')
        
        latest = str(rec.get('latest_issue', ''))
        dp_str = fmt_hit(hdp, len(dpicks)) if dpicks else c('N/A', 'gray')

        # 空推荐 = 无有效样本，显示 N/A 而非假的 0/5 红字
        t5_str   = fmt_hit(h5, 5)          if t5   else c(' N/A ', 'gray')
        t12_str  = fmt_hit(h12, 12, 2)     if t12  else c(' N/A  ', 'gray')
        he5_str  = fmt_hit(hhe5, 5)        if he5  else c(' N/A  ', 'gray')

        p2_str = fmt_hit(hp2, 2, threshold=1) if (p2 and len(p2)==2) else c('N/A', 'gray')
        row = (f"  {latest:^8} │ {target:^8} │ "
               f" {p2_str:^6} │  {t5_str}   │  {t12_str}   │"
               f"  {he5_str}   │  {dp_str}")
        print(row)
    
    print(c(sep, 'gray'))
    
    if trinity_hits5:
        avg5  = sum(trinity_hits5) / len(trinity_hits5)
        avg12 = sum(trinity_hits12) / len(trinity_hits12)
        avghh = sum(he5_hits) / len(he5_hits) if he5_hits else 0
        avgd  = sum(deep_hits) / len(deep_hits) if deep_hits else 0
        
        lift5  = avg5  / (5  * 20/80)
        lift12 = avg12 / (12 * 20/80)
        liftHE = avghh / (5  * 20/80)
        
        print()
        print(c('  📈 统计汇总 (近10期均值)', 'cyan', 'bold'))
        print(c('  ────────────────────────────────────', 'gray'))
        
        def lift_color(l):
            if l >= 1.5: return 'green'
            if l >= 1.0: return 'yellow'
            return 'red'
        
        print(f"  三维融合 Top5  : 均命中 {avg5:.2f}/5  | Lift={c(f'{lift5:.2f}x', lift_color(lift5), 'bold')}")
        print(f"  三维融合 Top12 : 均命中 {avg12:.2f}/12 | Lift={c(f'{lift12:.2f}x', lift_color(lift12), 'bold')}")
        print(f"  Hidden Energy 5: 均命中 {avghh:.2f}/5  | Lift={c(f'{liftHE:.2f}x', lift_color(liftHE), 'bold')}")
        if deep_hits:
            print(f"  方案2爆发码    : 均命中 {avgd:.2f}      |")
        
        print()
        # 诊断结论
        if lift5 >= 1.2:
            ok(f'近期命中率良好 (Lift={lift5:.2f}x)，当前模型表现稳定')
        elif lift5 >= 0.9:
            warn(f'近期命中率接近随机基线 (Lift={lift5:.2f}x)，大盘震荡期，守号为主')
        else:
            warn(f'近期命中率低于随机基线 (Lift={lift5:.2f}x)，系统已触发防守模式')
        
        # 优化建议
        print()
        print(c('  🔍 深度优化方案评估', 'yellow', 'bold'))
        print(c('  ────────────────────────────────────', 'gray'))
        if lift12 < 1.0:
            print(c('  当前架构已精简到 EF/RW/FO 三维，处于大盘混沌期。', 'white'))
            print(c('  经统计检验，当前命中率未显著优于随机基线，不建议增加新优化方案。', 'white'))
            print(c('  当前架构已科学合理，继续增加复杂度可能引入过拟合。维持现状，持续监控。', 'white'))
        else:
            print(c('  系统运行良好，当前三维架构已是最优精简版，无需调整。', 'green'))
    else:
        warn('近 10 期自学习记忆中 Trinity top5/top12 均为空表，无可信样本 —— '
             '不据此判定防守模式 (旧版曾因熔断抹零而误报 Lift=0.00x)。')

# ══════════════════════════════════════════════════════════
# SECTION 3.6: 顺口溜口诀规律与组合带出分析
# ══════════════════════════════════════════════════════════
def task36_formula_jingle():
    banner('任务3.6：📜 顺口溜口诀规律与组合带出分析 (90条精英规则)', 'cyan')
    jingle_script = find_module_script('run_jingle_daily.py')
    if os.path.exists(jingle_script):
        run_py(jingle_script, '20')
    else:
        warn('run_jingle_daily.py 未找到，尝试内置引擎推演')
        try:
            from core.formula_jingle.jingle_engine import load_jingle_rules, predict_jingle, save_jingle_prediction
            from utils.history_loader import load_history
            hist = load_history()
            draws = []
            for h in reversed(hist):
                nums = sorted(list(h['numbers']))
                if len(nums) == 20:
                    draws.append((int(h['issue']), h.get('date', ''), nums))
            rules, _ = load_jingle_rules()
            res = predict_jingle(draws, rules)
            save_jingle_prediction(res)
            ok(f"顺口溜推演完成 | 目标期 {res.get('target_issue')} | 推荐 {res.get('k_count')} 码")
        except Exception as je:
            warn(f"顺口溜推演异常: {je}")

# ══════════════════════════════════════════════════════════
# SECTION 3.8: 未开点位高压反弹与空间关联追踪
# ══════════════════════════════════════════════════════════
def task38_point_suppression():
    banner('任务3.8：🪞 未开点位高压反弹与空间关联追踪 (弹簧压制 + 影子替身)', 'magenta')
    supp_script = find_module_script('run_suppression_daily.py')
    if os.path.exists(supp_script):
        run_py(supp_script, '30')
    else:
        warn('run_suppression_daily.py 未找到，尝试内置算法引擎推演')
        try:
            from backend.modules.point_suppression.run_daily import run_suppression_pipeline
            res = run_suppression_pipeline(n_review=30, verbose=False)
            top1 = res.get('top1', {})
            ok(f"未开点位反弹推演完成 | 目标期 {res.get('target_period')} | 首重反弹胆: {top1.get('num', 0):02d}")
        except Exception as se:
            warn(f"未开反弹推演异常: {se}")

# ══════════════════════════════════════════════════════════
# SECTION 3.9: 定金选2决策推演 (双重金胆法 + 7维评分)
# ══════════════════════════════════════════════════════════
def task39_gold_pick2():
    banner('任务3.9：💎 定金选2决策推演 (双重金胆法 + 7维特征加权 + 条件共现)', 'cyan')
    pick2_script = find_module_script('run_pick2_daily.py')
    if os.path.exists(pick2_script):
        run_py(pick2_script, '30')
    else:
        warn('run_pick2_daily.py 未找到，尝试内置算法引擎推演')
        try:
            from backend.modules.legacy.gold_pick2.run_daily import run_pick2_pipeline
            res = run_pick2_pipeline(n_review=30, verbose=False)
            ok(f"定金选2分析完成 | 目标期 {res.get('target_period')} | 核心金胆: {res.get('golden'):02d} | 热胆: {res.get('hot'):02d}")
        except Exception as pe:
            warn(f"定金选2推演异常: {pe}")

# ══════════════════════════════════════════════════════════
# SECTION 3.94: 16期中热号频次动态推演与组合决策
# ══════════════════════════════════════════════════════════
def task394_sixteen_period():
    banner('任务3.94: 16期中热号频次动态推演与组合决策 (大盘光谱 + 出窗进窗推演 + 选2/3)', 'yellow')
    sixteen_script = find_module_script('run_sixteen_daily.py')
    if os.path.exists(sixteen_script):
        run_py(sixteen_script, '30')
    else:
        warn('run_sixteen_daily.py 未找到，跳过16期中热推演')

    # 16 窗工作簿生成后, 合并为「全合一终极量化驾驶舱」(含跟随看板/死党榜/全历史矩阵)
    cockpit = _resolve_backend_script('modules', 'build_unified_master_excel.py')
    if os.path.exists(cockpit):
        run_py(cockpit)
    else:
        warn('build_unified_master_excel.py 未找到，跳过全合一驾驶舱合并')

# ══════════════════════════════════════════════════════════
# SECTION 3.95: 终审共识与数据汇总复盘 (多路子系统多维共振 + 8区空间平衡)
# ══════════════════════════════════════════════════════════
def task395_aggregation():
    banner('任务3.95：🧬 终审共识与数据汇总复盘 (多路子系统多维共振 + 8区空间平衡 + 稳健号)', 'magenta')
    agg_script = find_module_script('run_aggregation_daily.py')
    if os.path.exists(agg_script):
        run_py(agg_script, '--force')
    else:
        warn('run_aggregation_daily.py 未找到，跳过终审汇总')

# ══════════════════════════════════════════════════════════
# SECTION 3.955: 模块前瞻账对账与门禁刷新 (C5/C6/D4)
# ══════════════════════════════════════════════════════════
def task3955_module_reconcile():
    banner('任务3.955：📊 模块前瞻账对账 + 门禁权重 live 刷新 (C5/C6/D4)', 'blue')
    try:
        from core.module_gate import (
            reconcile_module_ledger, module_ledger_report, ModuleGate,
        )
    except Exception as e:
        warn(f'module_gate 导入失败，跳过对账: {e}')
        return

    # 1) 开奖后: 把已开奖期补上 actual/hits (C5 前瞻账)
    try:
        filled = reconcile_module_ledger(limit_periods=400)
        info(f'前瞻账新对账 {filled} 条')
    except Exception as e:
        err(f'前瞻账对账失败: {e}')
        return

    # 2) 门禁注册表权重 live 重算 (shrink_lift + BH-FDR, 读 master_review_ledger)
    try:
        gate = ModuleGate()
        reg, changes = gate.refresh_from_master_ledger()
        if changes:
            ok(f'门禁权重已刷新 ({len(changes)} 项变更):')
            for ch in changes:
                sub(ch)
        else:
            info('门禁权重无变更 (各模块水位稳定)')
    except Exception as e:
        warn(f'门禁刷新失败: {e}')

    # 3) 落盘每模块前瞻账报告 (走 wf_hit_engine 同口径: lift/CI/p/BH-FDR)
    try:
        report = module_ledger_report(min_n=30)
        out_dir = os.path.join(get_outputs_dir(), 'reports')
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, 'module_ledger_report_latest.json')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        ok(f'模块前瞻账报告已落盘: outputs/reports/module_ledger_report_latest.json')
        # 2026-10-22 修复 (Bug#8)：入账但尚未开奖 / 样本为 0 的模块，其 lift、CI、p、bh_q 均为 None，
        # 直接 f"{None:.3f}" 抛 "unsupported format string passed to NoneType.__format__"。
        # 且异常发生在 json.dump 之后的打印循环里 —— 报告其实已落盘却被误报「前瞻账报告生成失败」。
        # 现统一走安全格式化，并对退役模块给出如实标注。
        def _fmt3(v):
            return f'{v:.3f}' if isinstance(v, (int, float)) else ' —  '
        for mid, m in report.get('modules', {}).items():
            # 2026-10-21 统计诚信修复 (Bug#7)：这里原先读 `significant`
            # (单模块未校正判据: n≥min_n 且 CI下界>1 且 p≤α) 却打成「✓FDR显著」。
            # 跨 37 个模块做 BH 校正后 trinity_top5 的 q=0.713 根本不过门槛，
            # 展示层却宣称 FDR 显著 —— 属于「拿未校正当 FDR 结论」的假显著。
            # 现改为读真正的 BH-FDR 位 (bh_significant / winner)。
            bh_ok = bool(m.get('bh_significant'))
            if m.get('retired'):
                sig = '已退役(不参校正)'
            elif bh_ok:
                sig = '✓BH-FDR显著'
            else:
                sig = '样本不足' if m.get('insufficient') else '未过BH-FDR(原始p可能<0.05)'
            sub(f"{m.get('name', mid):16s} n={m['n_periods']:>3} Lift={_fmt3(m.get('lift'))} "
                f"CI_lo={_fmt3(m.get('lift_ci_lo'))} p={_fmt3(m.get('p_value'))} q={_fmt3(m.get('bh_q'))} {sig} [{m.get('gate_progress', '?')}]")
    except Exception as e:
        warn(f'前瞻账报告生成失败: {e}')

    # 3.5) 一致性体检：legacy/ 下的模块目录是否都能映射到判决层。
    #      改名 legacy 后，「活跃模块住在 legacy/」是正常状态，不报警；
    #      真正要拦的是「查无此模块」—— 那说明它既没登记、也没人知道还在不在跑。
    try:
        from core.module_gate import check_registry_consistency
        _c = check_registry_consistency()
        if _c['ungoverned_dirs']:
            warn(f"注册表一致性: 以下目录未纳入判决层（谁也不知道还在不在跑）—— {_c['ungoverned_dirs']}")
        else:
            ok('注册表一致性体检通过（legacy/ 下全部目录均有判决）')
    except Exception as e:
        warn(f'注册表一致性体检跳过: {e}')

    # 4) 统一对账：开奖后 settle + 刷新 Markdown 日报
    # 2026-11-09 修复：过去只 settle 从不 snapshot，settle 便永远"无预测快照"而 skip，
    # 且只打 INFO 不告警 —— unified_daily_audit 自 2026281 起已静默断档 18 期。
    # 现改为：先结算上一期，再立刻为本期建立快照，次日即可正常结算。
    try:
        from backend.modules.unified_audit.run_daily import run_settle, run_snapshot
        ua = run_settle()
        if ua.get("status") == "ok":
            ok(f"统一对账已结算: 目标期 {ua.get('target_period')} → {ua.get('report')}")
        else:
            warn(f"统一对账 settle 未结算: {ua.get('status')} {ua.get('message')}")
        try:
            _snap = run_snapshot()
            if _snap.get("status") == "ok":
                ok(f"统一对账快照已建立: 目标期 {_snap.get('target_period')}")
            else:
                warn(f"统一对账 snapshot 未建立: {_snap.get('message')}")
        except Exception as _e:
            warn(f'统一对账 snapshot 失败: {_e}')
    except Exception as e:
        warn(f'统一对账 settle 失败: {e}')

# ══════════════════════════════════════════════════════════
# SECTION 3.951: 跟随统计推演 (1码×70期窗口, 精确检验版)
# ══════════════════════════════════════════════════════════
def task3951_follow_rank():
    banner('任务3.951：🔗 跟随统计推演 (上期号码下期跟随 + 精确加权伯努利检验)', 'blue')
    script = _resolve_backend_script('modules', 'calc_follow_stats.py')
    if not os.path.exists(script):
        warn('calc_follow_stats.py 未找到, 跳过跟随统计推演')
        return
    run_py(script, '--window', '70')


# ══════════════════════════════════════════════════════════
# SECTION 3.952: 逐模块预测收割 (C5 前瞻账: 各模块当期推荐入库)
# ══════════════════════════════════════════════════════════
def task3952_harvest():
    banner('任务3.952：📥 逐模块预测收割 (各模块当期推荐 → 追加式前瞻账)', 'blue')
    try:
        from backend.modules.daily_review.harvester import harvest
        res = harvest(verbose=True)
        ok(f"收割完成 | 目标期 {res.get('target_period')} | 收到 {res.get('recorded_count')} 个模块 "
           f"(新入账 {res.get('newly_added')} 条, 重收 {res.get('refreshed')} 条, 未收割 {res.get('skipped_count')} 个)")
        if res.get('skipped_count'):
            info('未收割模块详见 storage/reviews/harvest/ 明细 (产物缺失/目标期未刷新/抽不到号码)')
    except Exception as e:
        warn(f'逐模块预测收割失败: {e}')


def task3952b_research_sync():
    """把已立预注册的研究实验与前瞻账同步（只同步，不判定）。

    研究结论必须来自「先立规矩、再收数据、到期按规矩判」，
    所以这一步只负责喂数据；判定由 research_harness.evaluate() 按预注册规则做，
    任何地方都不许在这里改规则或提前下结论。
    """
    try:
        from backend.utils.research_harness import sync_all_from_forward_ledger, list_experiments
        synced = sync_all_from_forward_ledger()
        if not synced:
            info('无进行中的预注册实验')
            return
        for s in synced:
            if s.get('added'):
                ok(f"实验 {s['exp_id']} 新增观察 {s['added']} 期"
                   f"（累计 {s.get('total_periods')} 期）")
        for r in list_experiments():
            if r.get('verdict') not in (None, 'collecting', 'error'):
                info(f"实验 {r['exp_id']} 判定: {r['verdict']} —— {r.get('reason')}")
    except Exception as e:
        warn(f'研究实验同步失败: {e}')


# ══════════════════════════════════════════════════════════
# SECTION 3.953: 30码大底方案滚动回测 (研报动态证据源, OOF + BH-FDR)
# ══════════════════════════════════════════════════════════
def task3953_thirty_ball_benchmark():
    banner('任务3.953：🎲 30码大底多方案滚动回测 (证据 JSON 供研报动态引用)', 'blue')
    try:
        script = _resolve_backend_script('modules', 'spear_shield_portfolio', 'thirty_ball_benchmark.py')
        if not os.path.exists(script):
            warn('thirty_ball_benchmark.py 未找到, 跳过 30码大底回测')
            return
        run_py(script, '--periods', '1000')
    except Exception as e:
        warn(f'30码大底回测失败: {e}')


# ══════════════════════════════════════════════════════════
# SECTION 3.956: 逐模块逐期复盘 (每模块这一期中了几码)
# ══════════════════════════════════════════════════════════
def task3956_period_review():
    banner('任务3.956：🔍 逐模块逐期复盘 (上期各模块命中明细)', 'green')
    try:
        from backend.modules.daily_review.reviewer import review_period
        res = review_period(verbose=True)
        ok(f"复盘完成 | 期号 {res.get('period')} | 有前瞻账模块 {res.get('modules_reviewed')} 个, "
           f"命中 {res.get('total_hits')}/{res.get('total_picks')} 票, "
           f"池化命中率 {(res.get('pooled_rate') or 0) * 100:.1f}% | 无法复盘 {res.get('modules_unreviewed')} 个")
        sub(f"报告: {res.get('report_file')}")
    except Exception as e:
        warn(f'逐模块逐期复盘失败: {e}')


# ══════════════════════════════════════════════════════════
# SECTION 3.96: 质数合数与尾数香农熵三大协同推演
# ══════════════════════════════════════════════════════════
def task396_prime_tail():
    banner('任务3.96：🔢 质合数与尾数香农熵三大协同推演 (方案二/三/四)', 'blue')
    try:
        from backend.core.prime_composite_engine import run_prime_tail_analysis_pipeline
        res = run_prime_tail_analysis_pipeline()
        ok(f"质合与尾数协同推演完成 | 目标期 {res.get('target_period')}")
    except Exception as e:
        warn(f"质合与尾数推演异常: {e}")

# ══════════════════════════════════════════════════════════
# SECTION 3.97: 心理博弈论与逆向均值回归量化推演
# ══════════════════════════════════════════════════════════
def task397_psychological_game():
    banner('任务3.97：🧠 心理博弈论与逆向均值回归量化推演 (四大心理支柱)', 'cyan')
    try:
        from backend.core.psychological_game_engine import run_psychological_game_pipeline
        res = run_psychological_game_pipeline()
        ok(f"心理博弈推演完成 | 目标期 {res.get('target_period')}")
        from backend.audit.backtest_psychological_game_theory import PsychologicalGameTheoryAuditor
        auditor = PsychologicalGameTheoryAuditor()
        auditor.generate_full_audit_ledger_and_report()
        ok("心理博弈滚动回测对账账本已同步刷新")
    except Exception as e:
        warn(f"心理博弈推演/回测异常: {e}")

# ══════════════════════════════════════════════════════════
# SECTION 3.98: 三高特征 (重复高/边高/冷高) × 每日点位深度共振推演
# ══════════════════════════════════════════════════════════
def task398_tri_high():
    banner('任务3.98：🧬 三高特征 (重复高/边高/冷高) × 每日点位深度共振推演', 'yellow')
    try:
        from backend.core.tri_high_engine import run_tri_high_pipeline
        res = run_tri_high_pipeline()
        ok(f"三高×点位深度共振推演完成 | 目标期 {res.get('target_period')}")
    except Exception as e:
        warn(f"三高×点位推演异常: {e}")

# ══════════════════════════════════════════════════════════
# SECTION 3.991: 三维交集共识 / 一胆拖三盾 (此前无人调用, 产物长期缺当期)
# ══════════════════════════════════════════════════════════
def task3991_straddle_spear():
    banner('任务3.991：🧬 三维交集共识定胆 + 一胆拖三盾选2组合拳', 'magenta')
    for label, mid, sub in [
        ('三维交集共识 (consensus_straddle)', 'consensus_straddle',
         ('modules', 'legacy', 'consensus_straddle', 'run_daily.py')),
        ('一胆拖三盾 (spear_shield)', 'spear_shield',
         ('modules', 'spear_shield_portfolio', 'run_daily.py')),
    ]:
        # 退役与否由注册表判决，不在这里写死 —— 复启只需改 MODULE_SEED 一处
        if not module_active(mid):
            info(f'{label} 已退役，跳过推演')
            continue
        script = _resolve_backend_script(*sub)
        if os.path.exists(script):
            ok_flag = run_py(script)
            ok(f'{label} 推演{"完成" if ok_flag else "退出码非0，请查上方输出"}')
        else:
            warn(f'{label} 入口脚本未找到: {script}')


# ══════════════════════════════════════════════════════════
# SECTION 3.992: 点位正负2引力展开 × 012路偏态剪枝压缩
# ══════════════════════════════════════════════════════════
def task3992_point_road_compressor():
    banner('任务3.992：🧬 点位012偏态压缩器 (点位锚定重心 + 正负2半径展开 + 012路偏态剪枝)', 'yellow')
    script = _resolve_backend_script('modules', 'point_road_compressor', 'run_daily.py')
    if os.path.exists(script):
        run_py(script)
    else:
        warn(f'point_road_compressor 入口未找到: {script}')


# ══════════════════════════════════════════════════════════
# SECTION 3.993: 数据源1×2 / 点位与遗漏 / 多维共振 —— 日常舱补挂
# ══════════════════════════════════════════════════════════
# 2026-10-21 Bug#3 修复：这三个模块在 docs/MODULE_INDEX.md 里登记为 **daily（日常舱）**，
# 收割器也按 daily 口径向它们索取当期产物，但 run_full_pipeline 从未调用过它们，
# 导致前瞻账每天如实报「当期产物不存在 / 产物目标期不符(未刷新)」而永久漏账。
# 现按同一 run_py 模式补挂，与其余日常模块同源同口径。
def task3993_daily_gap_modules():
    banner('任务3.993：🧩 日常舱漏挂模块补齐 (数据源1×2 / 点位+遗漏 / 多维共振)', 'cyan')
    for label, logical, argv in [
        # 注意各入口的参数契约不同：datasource 位置参 = n_review(期数),
        # point_omission 位置参 = period(期号!)，误传 '30' 会把目标期当成 30 期，
        # 因此 point_omission / multi_resonance 一律留空由模块自行推断目标期。
        ('数据源1×2 深层关联', 'run_datasource_daily.py', ['30']),
        ('点位+遗漏', 'run_omission_daily.py', ['--no-fetch']),
        ('多维共振', 'run_multi_resonance_daily.py', []),
    ]:
        script = find_module_script(logical)
        if os.path.exists(script):
            if run_py(script, *argv):
                ok(f'{label} 推演完成')
            else:
                warn(f'{label} 退出码非 0，请查上方输出')
        else:
            warn(f'{label} 入口未找到: {logical} -> {script}')


# ══════════════════════════════════════════════════════════
# SECTION 3.994: 决策树 012路 × 质合多梯度缩水 (TPRD v2.0)
# ══════════════════════════════════════════════════════════
def task3994_road_prime_shrink():
    banner('任务3.994：🌲 决策树 012路 × 质合多梯度智能缩水 (AI海选团 + 20/25/30码实战矩阵)', 'cyan')
    script = _resolve_backend_script('modules', 'road_prime_shrink', 'run_daily.py')
    if os.path.exists(script):
        run_py(script)
    else:
        warn(f'road_prime_shrink 入口未找到: {script}')


# ══════════════════════════════════════════════════════════
# SECTION 3.99: 残差改错预测与错题纠偏推演 (LightGBM 错题本纠偏)
# ══════════════════════════════════════════════════════════
def task399_error_correction():
    banner('任务3.99：🧬 残差改错预测与错题纠偏推演 (专攻错题本的 AI 改错裁判)', 'green')
    ec_script = find_module_script('run_error_correction_daily.py')
    if os.path.exists(ec_script):
        run_py(ec_script)
    else:
        warn('run_error_correction_daily.py 未找到，跳过残差改错推演')

# ══════════════════════════════════════════════════════════
# SECTION 4: 生成今日完整分析报告
# ══════════════════════════════════════════════════════════
def task4a_daily_report():
    """工业级日报先行: Trinity / HiddenEnergy5 / 传统AI 等模块只在日报里留档,
    必须先产出, 收割器才能按同一口径记账 (否则台账与最终报告会各说各话)。"""
    banner('任务4-A：🏭 生成工业级日报 (供收割器按同一口径记账)', 'green')
    report_script = _resolve_backend_script('pipeline', 'auto_generate_daily_report.py')
    if not os.path.exists(report_script):
        err('auto_generate_daily_report.py 未找到！')
        return None
    _ok = run_py(report_script)
    today = datetime.datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(get_reports_dir(), f'daily_analysis_report_{today}.md')
    # 2026-11-10 修复：原实现只看"文件是否存在"，而生成器是边算边写的 ——
    # 中途抛异常会留下一个**截断的文件**，于是崩溃被当成成功（实测 NameError
    # 让日报停在第 6 节，管线仍打印 ✅）。现改为以子进程退出码为准，并提示截断风险。
    if not _ok:
        err('auto_generate_daily_report.py 执行失败 —— 日报可能不完整，请查看上方日志')
        return None
    return report_path if os.path.exists(report_path) else None


def task4_generate_report():
    banner('任务4：🚀 生成今日完整分析报告', 'green')

    print()
    print(c('  ████████████████████████████████████████', 'magenta'))
    print(c('  ██   正在启动核心量化推演引擎...       ██', 'magenta', 'bold'))
    print(c('  ██████████████████████══════════════════', 'magenta'))
    print()

    # 4.B: 生成全模块标准终极研报 (涵盖三维交集共识、顺口溜双轨、全模块明细与可复制微信格式)
    std_report_script = _resolve_backend_script('pipeline', 'generate_standard_full_report.py')
    if os.path.exists(std_report_script):
        run_py(std_report_script)

    today = datetime.datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(get_reports_dir(), f'daily_analysis_report_{today}.md')

    if os.path.exists(report_path):
        size = os.path.getsize(report_path)
        ok(f'报告已生成: reports/daily_analysis_report_{today}.md ({size:,} bytes)')
        return report_path
    else:
        err(f'未找到今日报告: {report_path}')
        return None

def print_report_summary(report_path):
    """打印报告关键内容的美观摘要"""
    if not report_path or not os.path.exists(report_path):
        return
    
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
    
    print()
    banner('📋 今日分析报告核心摘要', 'cyan')
    print()
    
    # 提取关键块
    def extract_section(text, marker, lines=8):
        idx = text.find(marker)
        if idx == -1: return None
        snippet = text[idx:idx+1500]
        result_lines = snippet.split('\n')[:lines]
        return '\n'.join(result_lines)
    
    sections = [
        ('## 一、', '📅 复盘追溯', 'yellow'),
        ('### 0.', '🎯 今日极简选2 · 黄金搭档', 'green'),
        ('### 1.', '🛡️ 三维融合 极秘推荐', 'cyan'),
        ('### 4.6.', '📜 顺口溜口诀研判', 'cyan'),
        ('### 5.', '⭐ Hidden Energy 5', 'magenta'),
        ('### 10.', '🔗 方案2 深层关联分析', 'yellow'),
        ('### 10.5.', '⚡ 全链路三级漏斗流水线', 'green'),
        ('### 11.', '⚖️  风险审计', 'red'),
    ]
    
    for marker, label, color in sections:
        snippet = extract_section(content, marker)
        if snippet:
            print(c(f'  ┌─ {label} ──────────────────────────────', color, 'bold'))
            for line in snippet.split('\n')[:10]:
                if line.strip():
                    print(c('  │ ', color) + line)
            print(c('  └──────────────────────────────────────────', color))
            print()

# ══════════════════════════════════════════════════════════
# SECTION 5: 验证与清理
# ══════════════════════════════════════════════════════════
def task5_verify(report_path):
    banner('任务5：验证报告完整性')
    
    if not report_path or not os.path.exists(report_path):
        err('报告文件未找到，生成失败！')
        return False
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('极简选2', '选2黄金搭档', '最优1组推荐'),
        ('Hidden Energy 5', '首席战略官特供', '5码精选'),
        ('Trinity', '三维融合', 'Top5/Top12'),
        ('顺口溜', '顺口溜口诀', '组合带出推演'),
        ('方案2', '深层关联分析', '爆发码精选'),
        ('KL', '物理熔断', '安全监控'),
    ]
    
    all_pass = True
    for key, name, desc in checks:
        if key in content:
            ok(f'{name}: {desc} ✓')
        else:
            warn(f'{name}: 未找到相关内容 ✗')
            all_pass = False
    
    return all_pass

def print_module_board(target_period=None):
    """收尾总览: 把当期各模块真实推荐与前瞻账水位打成一张看板。

    数据源: 前瞻账 storage/cache/paper_trading_modules.jsonl (与复盘同源, 不再是各处自说自话)。
    """
    ledger = os.path.join(get_cache_dir(), 'paper_trading_modules.jsonl')
    if not os.path.exists(ledger):
        warn('前瞻账不存在，跳过全模块总览')
        return

    if not target_period:
        latest = None
        for line in open(data_path('kl8_history_final.txt'), 'r', encoding='utf-8'):
            m = re.search(r'period:(\d+)', line)
            if m:
                latest = m.group(1)
                break
        target_period = str(int(latest) + 1) if latest else None
    if not target_period:
        return

    rows, hist = [], {}
    try:
        with open(ledger, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                mid = r.get('module')
                if r.get('hits') is not None and r.get('picks'):
                    acc = hist.setdefault(mid, [0, 0])
                    acc[0] += len(r['picks'])
                    acc[1] += r['hits']
                if str(r.get('period')) == str(target_period):
                    rows.append(r)
    except Exception as e:
        warn(f'前瞻账读取失败: {e}')
        return

    if not rows:
        warn(f'前瞻账无 {target_period} 期记录，跳过全模块总览')
        return

    rows.sort(key=lambda r: str(r.get('module')))

    print()
    banner(f'🎯 第 {target_period} 期 · 全模块推荐总览 ({len(rows)} 个模块)', 'cyan')
    print(c('  模块                        推荐号码                                          前瞻水位', 'gray'))
    print(c('  ' + '─' * 98, 'gray'))
    for r in rows:
        picks = ' '.join(f'{int(x):02d}' for x in r.get('picks', []))
        acc = hist.get(r.get('module'))
        if acc and acc[0]:
            rate = acc[1] / acc[0]
            lift = rate / 0.25
            color = 'green' if lift >= 1.05 else ('red' if lift < 1.0 else 'yellow')
            stat = c(f'{rate * 100:5.1f}%  {lift:5.2f}x', color)
        else:
            stat = c('   — 无前瞻账', 'gray')
        print(f"  {r.get('module','')[:24]:<26}{picks:<48}{stat}")
    print(c('  ' + '─' * 98, 'gray'))
    total_picks = sum(len(r.get('picks', [])) for r in rows)
    print(c(f'  合计 {total_picks} 票 ｜ 水位 = 该模块历史前瞻账命中率 ÷ 25% 随机基线（<1.00x 即跑输大盘）', 'gray'))
    print(c('  ℹ  各模块口径不同，票数≠概率；未过统计显著门槛者仅作研究参考。', 'yellow'))


def task6_cleanup():
    banner('任务6：清理 __pycache__ 防污染')
    count = 0
    for root, dirs, files in os.walk(PROJ):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                try:
                    shutil.rmtree(path)
                    count += 1
                except Exception:
                    pass
    ok(f'已清理 {count} 个 __pycache__ 目录')


def task7_auto_git_sync():
    """收尾：把当日代码与数据变更自动提交并推送。

    2026-11-11 新增。失败只告警，绝不影响流水线结果 —— 同步是运维动作，
    不该拖垮业务计算。可用环境变量关闭：
        AUTO_GIT_SYNC=0  完全跳过
        AUTO_GIT_PUSH=0  只提交不推送
    """
    banner('任务7：📤 自动提交并推送当日变更', 'cyan')
    try:
        from backend.utils.auto_git_sync import auto_sync
    except Exception as e:
        warn(f'自动同步模块不可用: {e}')
        return

    note = ''
    try:
        hist = data_path('kl8_history_final.txt')
        with open(hist, 'r', encoding='utf-8') as f:
            m = re.search(r'period:(\d+)', f.readline())
        if m:
            note = f'目标期 {int(m.group(1)) + 1}'
    except Exception:
        pass

    try:
        res = auto_sync(note=note)
        st = res.get('status')
        sha = res.get('sha') or ''
        if st == 'pushed':
            ok(f"已推送 · {res.get('branch')} {sha} {res.get('shortstat', '')}".rstrip())
        elif st == 'committed':
            warn(f"已提交但未推送: {res.get('message')}")
        elif st == 'pending':
            warn(f"仍有提交未推送: {res.get('message')}")
        elif st == 'no_changes':
            info(f"无需提交: {res.get('message') or '工作区干净'}")
        elif st == 'skipped':
            info(f"跳过: {res.get('message')}")
        else:
            warn(f"自动同步失败（不影响本次推演）: {res.get('message')}")
    except Exception as e:
        warn(f'自动同步异常（不影响本次推演）: {e}')

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    # 开启 ANSI 颜色支持 (Windows)
    os.system('color')
    
    start_time = time.time()
    
    banner(f'快乐8预测系统 — 每日全流程推演引擎 v4.3 (精锐纯净版) [{datetime.datetime.now():%Y-%m-%d %H:%M}]', 'cyan')
    
    try:
        task0_env_check()
        task00_validate()
        task11_fetch()
        task12_hot_numbers()
        task13_15_sync()
        task2_review()
        if module_active('formula_jingle'):
            task36_formula_jingle()
        task38_point_suppression()
        task39_gold_pick2()
        task394_sixteen_period()
        # 全部分预测模块先跑完, 再收割 —— 否则收割时下游模块产物还停留在上一期,
        # 会被判"目标期不符"整批漏账 (2026-10-09 顺序整改)。
        task396_prime_tail()
        task397_psychological_game()
        task398_tri_high()
        if module_active('error_correction'):
            task399_error_correction()
        task3991_straddle_spear()
        task3992_point_road_compressor()
        task3993_daily_gap_modules()
        task3994_road_prime_shrink()
        task4a_daily_report()
        task395_aggregation()
        task3951_follow_rank()
        task3952_harvest()
        task3952b_research_sync()
        task3953_thirty_ball_benchmark()
        task3955_module_reconcile()
        task3956_period_review()
        report_path = task4_generate_report()
        print_report_summary(report_path)
        ok_report = task5_verify(report_path)
        print_module_board()
        task6_cleanup()
        task7_auto_git_sync()
    except KeyboardInterrupt:
        print()
        warn('用户中断执行')
        sys.exit(1)
    except Exception as e:
        err(f'执行过程发生异常: {e}')
        traceback.print_exc()
    
    elapsed = time.time() - start_time
    
    print()
    banner(f'✅ 全域推演完成！耗时 {elapsed:.1f}s — 请查阅 reports/ 目录中的今日报告', 'green')
    print()
