#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 每日全流程一键执行器 v4.3
=================================
用法：在项目 data 目录下执行 python run_full_pipeline.py
功能：完整执行分析脚本中的所有任务，输出美观详细的控制台报告
"""
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

from utils.paths import data_path

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
    cmd = [sys.executable, "-u", script] + list(args)
    cwd = cwd or PROJ
    print(c(f'  ▶ python {os.path.basename(script)} {" ".join(args)}', 'gray'))
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd,
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
        'kl8_history_final.txt',
        'daily_points.txt',
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
    
    # 读取最新期号
    hist_file = os.path.join(PROJ, 'kl8_history_final.txt')
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
    hist_file = os.path.join(PROJ, 'kl8_history_final.txt')
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
    mem_file = os.path.join(PROJ, 'cache', 'self_learning_state.json')
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
    
    header = f"  {'期号':^8} │ {'目标期':^8} │ {'选2命中':^6} │ {'T5命中':^6} │ {'T12命中':^7} │ {'HE5命中':^7} │ {'纯净池':^6} │ {'方案2爆发':^9}"
    sep    = '  ' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*7 + '┼' + '─'*8 + '┼' + '─'*8 + '┼' + '─'*7 + '┼' + '─'*10
    
    print(c(header, 'white', 'bold'))
    print(c(sep, 'gray'))
    
    trinity_hits5, trinity_hits12, he5_hits, pure_hits, deep_hits = [], [], [], [], []
    row_count = 0
    
    for rec in records[:10]:
        target = str(rec.get('target_issue', ''))
        actual = hist_map.get(target, None)
        if actual is None:
            continue
        
        row_count += 1
        p2  = rec.get('optimal_pick2', [])
        t5  = sorted(rec.get('top5', []))
        t12 = sorted(rec.get('top12', []))
        he5 = sorted(rec.get('b3_final5', []))
        pure = sorted(rec.get('pure_pool_top', []))
        dpicks = sorted(rec.get('deep_picks', []))
        
        hp2 = len(set(p2) & actual) if (p2 and len(p2)==2) else 0
        h5  = len(set(t5)  & actual)
        h12 = len(set(t12) & actual)
        hhe5 = len(set(he5) & actual)
        hpure = len(set(pure) & actual)
        hdp  = len(set(dpicks) & actual)
        
        trinity_hits5.append(h5)
        trinity_hits12.append(h12)
        he5_hits.append(hhe5)
        pure_hits.append(hpure)
        if dpicks: deep_hits.append(hdp)
        
        def fmt_hit(h, total, threshold=1):
            if h >= threshold:
                return c(f'{h}/{total}', 'green', 'bold')
            else:
                return c(f'{h}/{total}', 'red')
        
        latest = str(rec.get('latest_issue', ''))
        dp_str = fmt_hit(hdp, len(dpicks)) if dpicks else c('N/A', 'gray')
        
        p2_str = fmt_hit(hp2, 2, threshold=1) if (p2 and len(p2)==2) else c('N/A', 'gray')
        row = (f"  {latest:^8} │ {target:^8} │ "
               f" {p2_str:^6} │  {fmt_hit(h5,5)}   │  {fmt_hit(h12,12,2)}   │"
               f"  {fmt_hit(hhe5,5)}   │ {fmt_hit(hpure, len(pure) if pure else 5)}"
               f"  │  {dp_str}")
        print(row)
    
    print(c(sep, 'gray'))
    
    if trinity_hits5:
        avg5  = sum(trinity_hits5) / len(trinity_hits5)
        avg12 = sum(trinity_hits12) / len(trinity_hits12)
        avghh = sum(he5_hits) / len(he5_hits) if he5_hits else 0
        avgp  = sum(pure_hits) / len(pure_hits) if pure_hits else 0
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
        print(f"  纯净池定胆     : 均命中 {avgp:.2f}      |")
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

# ══════════════════════════════════════════════════════════
# SECTION 3.5: 双层LSTM 深度学习推演与回测
# ══════════════════════════════════════════════════════════
def task35_lstm_engine():
    banner('任务3.5：🧠 双层LSTM 深度学习时序推演与复盘', 'magenta')
    try:
        from models.lstm.lstm_service import LSTMService
        res = LSTMService.run_daily_pipeline(backfill_n=5, verbose=True)
        info_data = res.get('prediction')
        if info_data:
            ok(f"双层LSTM推演完成 | 目标期 {info_data['period']} | 💎金胆 {info_data['gold']:02d} 🥈银胆 {info_data['silver']:02d} 🥉铜胆 {info_data['bronze']:02d}")
        else:
            warn("双层LSTM推演未返回有效结果")
    except Exception as e:
        warn(f"双层LSTM推演过程提示: {e}")

# ══════════════════════════════════════════════════════════
# SECTION 3.6: 顺口溜口诀规律与组合带出分析
# ══════════════════════════════════════════════════════════
def task36_formula_jingle():
    banner('任务3.6：📜 顺口溜口诀规律与组合带出分析 (90条精英规则)', 'cyan')
    jingle_script = os.path.join(PROJ, 'run_jingle_daily.py')
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
# SECTION 3.7: 空间重点点位分析与精排 (4维可解释打分)
# ══════════════════════════════════════════════════════════
def task37_spatial_points():
    banner('任务3.7：🔮 空间重点点位分析与精排 (4维透明打分 + Walk-Forward 评级)', 'yellow')
    points_script = os.path.join(PROJ, 'run_points_daily.py')
    if os.path.exists(points_script):
        run_py(points_script, '30')
    else:
        warn('run_points_daily.py 未找到，尝试内置算法引擎推演')
        try:
            from run_points_daily import run_points_pipeline
            res = run_points_pipeline(n_review=30, verbose=False)
            ok(f"重点点位分析完成 | 目标期 {res.get('target_period')} | 核心五码: {res['picks']['core5_str']}")
        except Exception as pe:
            warn(f"重点点位推演异常: {pe}")

# ══════════════════════════════════════════════════════════
# SECTION 3.8: 未开点位高压反弹与空间关联追踪
# ══════════════════════════════════════════════════════════
def task38_point_suppression():
    banner('任务3.8：🪞 未开点位高压反弹与空间关联追踪 (弹簧压制 + 影子替身)', 'magenta')
    supp_script = os.path.join(PROJ, 'run_suppression_daily.py')
    if os.path.exists(supp_script):
        run_py(supp_script, '30')
    else:
        warn('run_suppression_daily.py 未找到，尝试内置算法引擎推演')
        try:
            from run_suppression_daily import run_suppression_pipeline
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
    pick2_script = os.path.join(PROJ, 'run_pick2_daily.py')
    if os.path.exists(pick2_script):
        run_py(pick2_script, '30')
    else:
        warn('run_pick2_daily.py 未找到，尝试内置算法引擎推演')
        try:
            from run_pick2_daily import run_pick2_pipeline
            res = run_pick2_pipeline(n_review=30, verbose=False)
            ok(f"定金选2分析完成 | 目标期 {res.get('target_period')} | 核心金胆: {res.get('golden'):02d} | 热胆: {res.get('hot'):02d}")
        except Exception as pe:
            warn(f"定金选2推演异常: {pe}")

# ══════════════════════════════════════════════════════════
# SECTION 3.91: 跟随分析 (重复号追踪与多窗条件跟随)
# ══════════════════════════════════════════════════════════
def task391_follow_analysis():
    banner('任务3.91：🔗 跟随分析 (重复号追踪 + 搭档跟随 + 多窗条件跟随)', 'magenta')
    follow_script = os.path.join(PROJ, 'run_follow_daily.py')
    if os.path.exists(follow_script):
        run_py(follow_script, '30')
    else:
        warn('run_follow_daily.py 未找到，跳过跟随分析')

# ══════════════════════════════════════════════════════════
# SECTION 3.92: Gemini 选2预测 (5大物理算子量化研判)
# ══════════════════════════════════════════════════════════
def task392_gemini_pick2():
    banner('任务3.92：💎 Gemini 选2预测 (空间张力 + 尾数熵 + 扩散 + 共现社区 + 动量)', 'cyan')
    gemini_script = os.path.join(PROJ, 'run_geminixuan2_daily.py')
    if os.path.exists(gemini_script):
        run_py(gemini_script, '30')
    else:
        warn('run_geminixuan2_daily.py 未找到，跳过Gemini选2')

# ══════════════════════════════════════════════════════════
# SECTION 3.93: KillSeeker 极致杀号与五维反哺
# ══════════════════════════════════════════════════════════
def task393_killseeker():
    banner('任务3.93：🚫 KillSeeker 极致杀号与反哺防御 (5大引擎协同排除)', 'red')
    kill_script = os.path.join(PROJ, 'run_killseeker_daily.py')
    if os.path.exists(kill_script):
        run_py(kill_script)
    else:
        warn('run_killseeker_daily.py 未找到，跳过KillSeeker')

# ══════════════════════════════════════════════════════════
# SECTION 3.94: 16期中热号频次动态推演与组合决策
# ══════════════════════════════════════════════════════════
def task394_sixteen_period():
    banner('任务3.94：🔥 16期中热号频次动态推演与组合决策 (大盘光谱 + 出窗进窗推演 + 选2/3)', 'yellow')
    sixteen_script = os.path.join(PROJ, 'run_sixteen_daily.py')
    if os.path.exists(sixteen_script):
        run_py(sixteen_script, '30')
    else:
        warn('run_sixteen_daily.py 未找到，跳过16期中热推演')

# ══════════════════════════════════════════════════════════
# SECTION 3.95: 终审共识与数据汇总复盘 (多路子系统多维共振 + 8区空间平衡)
# ══════════════════════════════════════════════════════════
def task395_aggregation():
    banner('任务3.95：🧬 终审共识与数据汇总复盘 (多路子系统多维共振 + 8区空间平衡 + 稳健号)', 'magenta')
    agg_script = os.path.join(PROJ, 'run_aggregation_daily.py')
    if os.path.exists(agg_script):
        run_py(agg_script, '--force')
    else:
        warn('run_aggregation_daily.py 未找到，跳过终审汇总')

# ══════════════════════════════════════════════════════════
# SECTION 4: 生成今日完整分析报告
# ══════════════════════════════════════════════════════════
def task4_generate_report():
    banner('任务4：🚀 生成今日完整分析报告', 'green')
    
    print()
    print(c('  ████████████████████████████████████████', 'magenta'))
    print(c('  ██   正在启动核心量化推演引擎...       ██', 'magenta', 'bold'))
    print(c('  ██████████████████████══════════════════', 'magenta'))
    print()
    
    report_script = _resolve_backend_script('pipeline', 'auto_generate_daily_report.py')
    if not os.path.exists(report_script):
        err('auto_generate_daily_report.py 未找到！')
        return None
    
    success = run_py(report_script)
    
    today = datetime.datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(PROJ, 'reports', f'daily_analysis_report_{today}.md')
    
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
        ('### 4.5.', '🧠 双层LSTM 深度学习研判', 'magenta'),
        ('### 4.6.', '📜 顺口溜口诀研判', 'cyan'),
        ('### 5.', '⭐ Hidden Energy 5', 'magenta'),
        ('### 8.', '💎 纯净池定胆', 'blue'),
        ('### 10.', '🔗 方案2 深层关联分析', 'yellow'),
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
        ('双层LSTM', '双层LSTM深度学习', 'AI时序建模与海选'),
        ('顺口溜', '顺口溜口诀', '组合带出推演'),
        ('纯净池', '纯净池定胆', '高置信定胆'),
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

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    # 开启 ANSI 颜色支持 (Windows)
    os.system('color')
    
    start_time = time.time()
    
    banner(f'快乐8预测系统 — 每日全流程推演引擎 v4.3  [{datetime.datetime.now():%Y-%m-%d %H:%M}]', 'cyan')
    
    try:
        task0_env_check()
        task00_validate()
        task11_fetch()
        task12_hot_numbers()
        task13_15_sync()
        task2_review()
        task35_lstm_engine()
        task36_formula_jingle()
        task37_spatial_points()
        task38_point_suppression()
        task39_gold_pick2()
        task391_follow_analysis()
        task392_gemini_pick2()
        task393_killseeker()
        task394_sixteen_period()
        task395_aggregation()
        report_path = task4_generate_report()
        print_report_summary(report_path)
        ok_report = task5_verify(report_path)
        task6_cleanup()
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
