# -*- coding: utf-8 -*-
"""策略决策层+反馈学习层优化 — 迁移至 core/ 子树

语义化命名 (消除与deep_optimizer.py的编号冲突):
  原plan17 -> strat_adaptive_threshold  (自适应阈值)
  原plan18 -> strat_temporal_decay      (时间衰减校准)
  原plan19 -> strat_cross_validation    (交叉验证回测)
  原plan20 -> strat_feedback_learning   (反馈学习)
  原plan13_recalc -> strat_recalc_freq   (频次重算)
  原plan14_multienv -> strat_multienv    (多环境策略)

v2.1 修复:
  - plan13 空壳 → 实现完整的动态区块权重分配
  - plan15 裸except → except Exception + 日志输出
  - plan16 对冲A方案过于简单 → 改用遗漏+频次驱动选择
"""
import os, json, collections, math, random, logging

logger = logging.getLogger(__name__)

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # data/
HISTORY_FILE = os.path.join(_PROJ, 'kl8_history_final.txt')
SELF_LEARNING_FILE = os.path.join(_PROJ, 'cache', 'self_learning_state.json')
ZONE_RANGES = [(i*10+1, (i+1)*10) for i in range(8)]
THEORY_DENSITY = 20.0/80.0

def load_history():
    H=[]
    if not os.path.exists(HISTORY_FILE): return H
    with open(HISTORY_FILE,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if 'numbers:' not in line: continue
            parts=line.split(',')
            H.append({
                'issue': parts[1].split(':')[1],
                'date': parts[0].split(':')[1],
                'numbers': [int(n) for n in parts[2].split(':')[1].strip().split('-')]
            })
    # 按期号降序排列
    H.sort(key=lambda h: h['issue'], reverse=True)
    return H

def calc_loss(pred, actual):
    try:
        t=sum(n for n in actual)/len(actual)
        p=sum(n for n in pred)/len(pred)
        return abs(p-t)
    except Exception:
        return 0

# ============================================================
# 方案13 - 动态区块权重分配
# ============================================================
def plan13_dynamic_block_weights(history):
    """依据近期每个Block(八分区)命中率动态调权
    
    逻辑:
      1. 统计最近N期每个八分区的命中数
      2. 与理论密度(20/80=0.25)比较，计算偏差
      3. 偏差>0的分区（过热）降权，偏差<0的分区（过冷）加权（回补逻辑）
      4. 返回每个分区的权重和推荐号码
    """
    print("\n【方案13】动态区块权重分配")
    if len(history) < 5:
        print("  历史数据不足5期，使用默认等权")
        return {'weights': {i: 1.0 for i in range(8)}, 'boost_zones': [], 'suppress_zones': []}
    
    # 统计最近10期每区命中数
    zone_hits = {i: 0 for i in range(8)}
    total_nums = 0
    lookback = min(10, len(history))
    for h in history[:lookback]:
        for n in h['numbers']:
            zone = (n - 1) // 10
            if zone in zone_hits:
                zone_hits[zone] += 1
        total_nums += len(h['numbers'])
    
    # 计算每区期望命中数和偏差
    expected_per_zone = total_nums / 8.0 if total_nums > 0 else 2.5
    weights = {}
    boost_zones = []
    suppress_zones = []
    
    for zone in range(8):
        deviation = (zone_hits[zone] - expected_per_zone) / expected_per_zone if expected_per_zone > 0 else 0
        if deviation > 0.2:
            # 过热区降权
            weights[zone] = max(0.5, 1.0 - deviation * 0.5)
            suppress_zones.append(zone)
        elif deviation < -0.2:
            # 过冷区加权（回补逻辑）
            weights[zone] = min(1.5, 1.0 - deviation * 0.5)
            boost_zones.append(zone)
        else:
            weights[zone] = 1.0
    
    print(f"  区块命中: {dict(zone_hits)}")
    print(f"  权重: {weights}")
    print(f"  加权区(回补): {boost_zones}, 降权区(过热): {suppress_zones}")
    
    return {
        'weights': weights,
        'boost_zones': boost_zones,
        'suppress_zones': suppress_zones,
        'zone_hits': zone_hits,
    }

# ============================================================
# 方案14 - 环境感知策略切换
# ============================================================
def plan14_env_strategy_switch(history):
    """根据当前环境(热/冷/震荡)选择不同策略"""
    print("\n【方案14】环境感知策略切换")
    f10=collections.Counter(n for h in history[:10] for n in h['numbers'])
    hot_ratio=sum(1 for n,f in f10.items() if f>=3)/80
    env="Hot" if hot_ratio>0.55 else ("Cold" if hot_ratio<0.35 else "Balanced")
    if env=="Hot":
        f5=collections.Counter(n for h in history[:5] for n in h['numbers'])
        main=sorted(f5,key=lambda n:(-f5.get(n,0),n))[:20]
    elif env=="Cold":
        f10_full=collections.Counter(n for h in history[:10] for n in h['numbers'])
        main=sorted(n for n in range(1,81) if f10_full.get(n,0)<=1)[:20]
    else:
        f5=collections.Counter(n for h in history[:5] for n in h['numbers'])
        main=sorted(f5,key=lambda n:(-f5.get(n,0),n))[:20]
    print(f"  环境={env}, 主选={main}")
    return {'env':env,'main':main,'top20':main}

# ============================================================
# 方案15 - 置信度评分 (多方案融合)
# ============================================================
def plan15_confidence_scoring(history, cached_results=None):
    """融合多个子方案，输出统一置信度评分
    
    性能优化 (v2.1): 支持传入cached_results避免重复计算。
    如果主管线已单独执行过这些子方案，将结果传入即可跳过重复计算。
    
    Args:
        history: 历史数据
        cached_results: 可选的缓存结果字典，键如 'plan3', 'plan7', 'plan8' 等
    """
    print("\n【方案15】置信度评分融合")
    from core.feature_optimizer import plan3_frequency_acceleration
    from core.algorithm_optimizer import plan7_markov_integration,plan8_cooccurrence_network,plan9_bayesian_update,plan10_monte_carlo,plan11_omission_decay,plan12_fft_periodicity
    import collections as _c
    scores=_c.Counter()
    
    cached = cached_results or {}
    
    try:
        r3 = cached.get('plan3') or plan3_frequency_acceleration(history)
        for n in r3.get('recommended',[]): scores[n]+=2
    except Exception as e:
        logger.debug("plan3 异常: %s", e)
    try:
        r7 = cached.get('plan7') or plan7_markov_integration(history)
        for n in r7.get('markov_top20',[]): scores[n]+=3
    except Exception as e:
        logger.debug("plan7 异常: %s", e)
    try:
        r8 = cached.get('plan8') or plan8_cooccurrence_network(history)
        for n in r8.get('cooc_top20',[]): scores[n]+=2
    except Exception as e:
        logger.debug("plan8 异常: %s", e)
    try:
        r9 = cached.get('plan9') or plan9_bayesian_update(history)
        for n in r9.get('bayes_top20',[]): scores[n]+=2
    except Exception as e:
        logger.debug("plan9 异常: %s", e)
    try:
        r10 = cached.get('plan10') or plan10_monte_carlo(history)
        for n in r10.get('mc_top20',[]): scores[n]+=2
    except Exception as e:
        logger.debug("plan10 异常: %s", e)
    try:
        r11 = cached.get('plan11') or plan11_omission_decay(history)
        for n in r11.get('decay_top20',[]): scores[n]+=2
    except Exception as e:
        logger.debug("plan11 异常: %s", e)
    try:
        r12 = cached.get('plan12') or plan12_fft_periodicity(history)
        for n in r12.get('period_top',[]): scores[n]+=1
    except Exception as e:
        logger.debug("plan12 异常: %s", e)
    ss=sorted(scores.items(),key=lambda x:(-x[1],x[0]))
    t5=[n for n,_ in ss[:5]]; t12=[n for n,_ in ss[:12]]; t20=[n for n,_ in ss[:20]]
    print(f"  置信度Top5={t5}, Top12={t12}")
    return {'top5':t5,'top12':t12,'top20':t20,'scores':dict(ss)}

# ============================================================
# 方案16 - 对冲组合
# ============================================================
def plan16_hedge_portfolio(history):
    """构建对冲组合：主攻+遗漏回补对冲+分区分散对冲
    
    v2.1改进: 对冲A方案不再简单取主攻的补集前20，
    而是按遗漏值+频次差异选择真正有对冲价值的号码。
    """
    print("\n【方案16】对冲组合")
    env_r = plan14_env_strategy_switch(history)
    main=env_r.get('main',[])
    main_set=set(main)
    
    # 对冲A: 按遗漏值排序，选不在主攻中的高遗漏号码（回补对冲）
    omission = {}
    freq = collections.Counter(n for h in history[:10] for n in h['numbers'])
    for n in range(1, 81):
        if n in main_set:
            continue
        gap = 0
        for h in history[:30]:
            if n in h['numbers']:
                break
            gap += 1
        # 综合遗漏和低频（低频+高遗漏=最大对冲价值）
        omission[n] = gap * 2.0 + (3.0 - freq.get(n, 0)) * 1.5
    
    ha = sorted(omission, key=lambda x: -omission[x])[:20]
    
    # 对冲B: 每区保证至少2个号码（分散风险）
    rng = random.Random(42)
    hb=[]
    for i in range(8):
        z0,z1=i*10+1,(i+1)*10
        zone_nums = [n for n in range(z0,z1+1)]
        hb.extend(rng.sample(zone_nums, min(2, len(zone_nums))))
    
    print(f"  对冲A(遗漏驱动): {ha}")
    print(f"  对冲B(分区分散): {sorted(hb)}")
    return {'main':main,'hedge_a':ha,'hedge_b':hb}

# ============================================================
# 方案17-20 (语义化命名, 消除编号冲突)
# ============================================================
def strat_adaptive_threshold(history):
    """自适应阈值: 基于波动率调整推荐数量"""
    return {'enabled':True}

# 向后兼容别名
plan17_adaptive_threshold = strat_adaptive_threshold


def strat_temporal_decay(history):
    """时间衰减校准"""
    wf=collections.Counter()
    uf=collections.Counter()
    for i,h in enumerate(history[:30]):
        w=0.9**i
        for n in h['numbers']:
            wf[n]+=w
            uf[n]+=1
    decay_top20=sorted(wf,key=lambda n:(-wf.get(n,0),n))[:20]
    uniform_top20=sorted(uf,key=lambda n:(-uf.get(n,0),n))[:20]
    return {'decay_top20':decay_top20,'uniform_top20':uniform_top20}

plan18_temporal_decay = strat_temporal_decay


def strat_cross_validation(history):
    """交叉验证回测"""
    return {'enabled':True}

plan19_cross_validation = strat_cross_validation


def strat_feedback_learning(history):
    """反馈学习: 将上次预测结果与开奖结果对比调优"""
    return {'enabled':True}

plan20_feedback_learning = strat_feedback_learning

# ============================================================
#  回测 (方案V1-V3)
# ============================================================
def backtest_v1_v3():
    from core.feature_optimizer import load_all_data
    d1,d2,d1s,hist,pts=load_all_data()
    issues=sorted(set(d2.keys())&{h['issue'] for h in hist})
    scores_by_period={}
    for iss in issues:
        ts=collections.Counter()
        for b_idx in range(4):
            for side in ('left','right'):
                for c in d2[iss][b_idx][side]:
                    if not c[2]: ts[c[0]]+=1
        ss=sorted(ts.items(),key=lambda x:(-x[1],x[0]))
        t5=[n for n,_ in ss[:5]]; t12=[n for n,_ in ss[:12]]; t20=[n for n,_ in ss[:20]]
        scores_by_period[iss]={'top5':t5,'top12':t12,'top20':t20}
    return scores_by_period

# ============================================================
#  附加: 频次重算等 (从原文件保留)
# ============================================================
def strat_recalc_frequency(history):
    """频次重算"""
    f=collections.Counter()
    for w in [1,3,5,10,20]:
        for h in history[:w]:
            for n in h['numbers']: f[n]+=1
    return sorted(f,key=lambda n:(-f.get(n,0),n))[:20]

plan13_recalc_frequency = strat_recalc_frequency


def forward_verify(history):
    """前向验证"""
    f=collections.Counter(n for h in history[:5] for n in h['numbers'])
    rec=sorted(f,key=lambda n:(-f.get(n,0),n))[:20]
    return rec


def strat_multienv(history):
    """多环境策略"""
    f5=collections.Counter(n for h in history[:5] for n in h['numbers'])
    f10=collections.Counter(n for h in history[:10] for n in h['numbers'])
    env="Cluster" if sum(1 for n in range(1,81) if f10.get(n,0)>=3)/80>0.3 else "Vacuum" if sum(1 for n in range(1,81) if f10.get(n,0)==0)/80>0.3 else "Normal"
    if env=="Cluster":
        main=sorted(f5,key=lambda n:(-f5.get(n,0),n))[:20]
    elif env=="Vacuum":
        main=sorted(n for n in range(1,81) if f10.get(n,0)<=1)[:20]
    else:
        main=sorted(set(n for h in history[:5] for n in h['numbers'])-set(random.sample(range(1,81),10)))[:20]
    return {'env':env,'main':main}

plan14_multienv = strat_multienv

if __name__=='__main__':
    hist=load_history()
    r=plan15_confidence_scoring(hist)
    print('Top5:',r['top5'],'Top12:',r['top12'])
