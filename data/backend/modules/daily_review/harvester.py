# -*- coding: utf-8 -*-
"""
逐模块预测收割器 (Per-Module Picks Harvester)
================================================================================
大白话: 各模块每天各写各的产物(md/txt/json), 格式五花八门, 谁也不汇总。
本收割器把每个模块"当期推荐了哪几个号"抽取出来, 写进**追加式**前瞻账
(`storage/cache/paper_trading_modules.jsonl`)。

为什么这样做:
  1. 前瞻账是 append-only 的, 一旦写入就永久留档 —— 于是研究舱那批
     "覆盖式落盘"(`*_latest.json`)的模块也终于有了按期历史, 不必改它们 12 个模块的落盘逻辑;
  2. 只用 `record_module_picks()` 官方入口, 幂等(同期同模块不重复), 不新增并行账本;
  3. 号码全部来自真实产物正则抽取, 抽不到就**如实跳过并记录原因**, 绝不编造兜底号。

用法:
    python -m backend.modules.daily_review.run_daily harvest            # 自动推断目标期
    python -m backend.modules.daily_review.run_daily harvest 2026257    # 指定期号
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _p in [_PROJ_DIR, os.path.join(_PROJ_DIR, "backend")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.utils.paths import data_path, get_reports_dir  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════
#  定位器 (finder) —— 决定"去哪里找这个模块当期的产物"
# ══════════════════════════════════════════════════════════════════════════

def _find_file(template: str, period: str, date: str) -> Optional[str]:
    """按模板定位文件; 模板支持 {period} / {date} / {date_c} 占位。"""
    rel = template.format(period=period, date=date, date_c=date.replace('-', ''))
    p = os.path.join(_PROJ_DIR, rel)
    return p if os.path.exists(p) else None


def _find_latest_json(template: str, period: str, date: str) -> Optional[str]:
    """定位覆盖式落盘的 *_latest.json, 由调用方核对内部 target 字段。"""
    return _find_file(template, period, date)


def _find_daily_report(period: str, date: str) -> Optional[str]:
    """按目标期号反查日报 (工业级大报引擎产出的模块都只在这里留档)。"""
    cands = sorted(
        glob.glob(os.path.join(get_reports_dir(), "daily_analysis_report_*.md")),
        key=os.path.getmtime, reverse=True,
    )[:8]
    for p in cands:
        try:
            head = open(p, encoding='utf-8', errors='replace').read(1200)
        except OSError:
            continue
        if re.search(r'目标期号[：:]\s*\**\s*%s' % re.escape(period), head):
            return p
    return None


def _find_point_omission(period: str, date: str) -> Optional[str]:
    """点位+遗漏按"日期目录"落盘, 目录内无期号文件名, 只按日期定位。"""
    return _find_file('storage/outputs/point_omission/{date}/daily_report.md', period, date)


def _find_state_history(period: str) -> Optional[Dict[str, Any]]:
    """从大报引擎的自学习状态里取该目标期的记录。

    `storage/cache/self_learning_state.json` 的 history 是**按期索引**的, 是大报引擎内部
    子推荐(极简选2/传统AI/mRMR/方案2)唯一按期留档的地方 —— 这些子模块没有独立产物文件。
    同一期可能有多次运行记录, 取 run_time 最新的一条。"""
    p = os.path.join(_PROJ_DIR, 'storage', 'cache', 'self_learning_state.json')
    if not os.path.exists(p):
        return None
    try:
        state = json.load(open(p, encoding='utf-8', errors='replace'))
    except Exception:
        return None
    cands = [r for r in (state.get('history') or [])
             if str(r.get('target_issue')) == str(period)]
    if not cands:
        return None
    cands.sort(key=lambda r: str(r.get('run_time') or ''), reverse=True)
    return cands[0]


def _extract_state_key(key: str, take: Optional[int] = None) -> Callable[[str, Dict], List[int]]:
    """从自学习状态记录里取某个键的号码列表。"""
    def _fn(text: str, d: Dict[str, Any]) -> List[int]:
        if not d:
            return []
        v = d.get(key)
        if not v or not isinstance(v, list):
            return []
        nums = [int(x) for x in v if isinstance(x, (int, float)) and 1 <= int(x) <= 80]
        return nums[:take] if take else nums
    return _fn


# ══════════════════════════════════════════════════════════════════════════
#  抽取器 (extractor) —— 决定"从产物里抠出哪几个号"
# ══════════════════════════════════════════════════════════════════════════

def _grab_nums(text: str, pattern: str, take: Optional[int] = None,
               group: int = 1, unique: bool = True) -> List[int]:
    """按正则抠号码。支持 `01 02 03` 与 `[1, 2, 3]` 两种写法。"""
    m = re.search(pattern, text, re.S)
    if not m:
        return []
    raw = m.group(group)
    nums = [int(x) for x in re.findall(r'\d+', raw)]
    nums = [n for n in nums if 1 <= n <= 80]
    if unique:
        seen, out = set(), []
        for n in nums:
            if n not in seen:
                seen.add(n)
                out.append(n)
        nums = out
    return nums[:take] if take else nums


def _json_target(d: Dict[str, Any]) -> Optional[str]:
    """从 JSON 里取出它自称的目标期号。"""
    for k in ("target_period", "target_issue", "period"):
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    t = d.get("target")
    if isinstance(t, dict) and t.get("period"):
        return str(t["period"]).strip()
    return None


def _extract_json_dated(keys: List[str], take: Optional[int] = None,
                        listify: bool = False) -> Callable[[str, Dict], List[int]]:
    """从已核对目标期号的 JSON 里按键取值 (支持 `a.b.c` 嵌套路径)。

    值为 list[int] / list[dict] / 标量 int 均可。
    """
    def _dig(d: Dict[str, Any], path: str) -> Any:
        cur: Any = d
        for seg in path.split('.'):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(seg)
        return cur

    def _fn(text: str, d: Dict[str, Any]) -> List[int]:
        for k in keys:
            v = _dig(d, k)
            if not v:
                continue
            if listify and isinstance(v, list) and v and isinstance(v[0], dict):
                nums = [int(x.get("number") or x.get("num")) for x in v if (x.get("number") or x.get("num"))]
            elif isinstance(v, (int, float)):
                nums = [int(v)]
            else:
                nums = [int(x) for x in v if isinstance(x, (int, float))]
            nums = [n for n in nums if 1 <= n <= 80]
            if nums:
                return nums[:take] if take else nums
        return []
    return _fn


def _extract_suppression_top3(text: str, d: Dict[str, Any]) -> List[int]:
    """未开点位反弹: 取**首重反弹胆**(第 1 条) —— 与汇总引擎 `点位反弹` 口径一致(1 码)。

    大白话: 这个模块的账本口径历史上就是"1 码"(主复盘天梯显示 推荐规模 1.0 码),
    多收几个号会让它的 Lift 统计和门禁进度对不上, 所以只取第一条。
    该模块的 `反弹Top3金胆: 03-05-34` 一行只写在覆盖式 txt 里, 按期留档的 md 用编号列表。
    """
    m = re.search(r'核心反弹推荐(.*?)(?=\n##|\Z)', text, re.S)
    if not m:
        return []
    return [int(x) for x in re.findall(r'\*\*号码\s*(\d{1,2})\*\*', m.group(1))][:1]


def _extract_jingle_7(text: str, d: Dict[str, Any]) -> List[int]:
    """顺口溜: 取**触发口诀推荐码**(7 码) —— 与汇总引擎 `顺口溜` 口径一致。"""
    return _grab_nums(text, r'触发口诀推荐码[^:：]*[：:]\s*([\d\s]+)', take=7)


def _extract_gold_pick2(text: str, d: Dict[str, Any]) -> List[int]:
    """定胆选2: 取 Top5 黄金配对组合里出现过的全部号码(≤6) —— 与汇总引擎 `定金选2` 口径一致。"""
    nums: List[int] = []
    for m in re.finditer(r'\[(\d{2})-(\d{2})\]', text):
        nums += [int(m.group(1)), int(m.group(2))]
    seen, uniq = set(), []
    for n in nums:
        if 1 <= n <= 80 and n not in seen:
            seen.add(n)
            uniq.append(n)
    if uniq:
        return uniq[:6]
    # 兜底: 若票面 txt 无配对行(老格式), 退回 JSON 的金胆 + 热胆 + 温号池
    out: List[int] = []
    for k in ('golden', 'hot'):
        v = d.get(k)
        if isinstance(v, (int, float)) and 1 <= int(v) <= 80:
            out.append(int(v))
    out += [int(x) for x in (d.get('warm_pool') or []) if isinstance(x, (int, float))]
    seen, uniq = set(), []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq[:6]


def _extract_omission_top5(text: str, d: Dict[str, Any]) -> List[int]:
    """点位+遗漏: 只抠 §6.1 五码核心表格的 `| **NN** |` 单元格。

    整段正则抠数字会把表格里的区间(61-70)、小数(0.78)一起抓进来, 必须按单元格精确取。
    """
    m = re.search(r'###\s*6\.1\s*五码核心(.*?)(?=\n###|\n##|\Z)', text, re.S)
    if not m:
        return []
    return [int(x) for x in re.findall(r'\|\s*\*\*(\d{1,2})\*\*\s*\|', m.group(1))][:5]


# 每个条目的字段含义:
#   id        前瞻账模块 id (尽量对齐 backend/config/module_vote_registry.json)
#   name      中文名 (报告里显示)
#   lane      daily | research | retired
#   finder    产物定位方式
#   require_target_json  True 表示该产物为覆盖式落盘, 必须核对内部目标期号一致才敢收
#   extract   抽取函数
EXTRACTORS: List[Dict[str, Any]] = [
    # ── daily 舱: 有按期(period)命名产物的模块 ──
    dict(id='sixteen_hot', name='16期中热号出窗进窗推演', lane='daily',
         finder=('md_period', 'storage/outputs/reports/sixteen_analysis_report_{period}.md'),
         extract=lambda t, d: _grab_nums(t, r'最优3码[：:]\s*`([\d\s]+)`', take=3)),
    dict(id='lstm', name='双层LSTM时序深度学习', lane='retired',
         finder=('txt_period', 'storage/outputs/predictions/prediction_{period}.txt'),
         extract=lambda t, d: _grab_nums(t, r'Top10:\s*([\d\-]+)', take=10)),
    dict(id='datasource', name='数据源1×2 矩阵联动', lane='daily',
         finder=('json_period', 'storage/outputs/deep_association/深层关联预测_{period}.json'),
         extract=_extract_json_dated(['top_hot_numbers'], take=5)),
    dict(id='unified_brain', name='统一决策脑', lane='research',
         finder=('json_period', 'storage/outputs/unified_brain/unified_decision_{period}.json'),
         extract=_extract_json_dated(['top5', 'top3_gold'], take=5)),
    dict(id='aggregation', name='子系统汇总陈列', lane='daily',
         finder=('json_period', 'storage/outputs/aggregation/aggregation_{period}.json'),
         extract=_extract_json_dated(['top3_gold'], take=3)),
    dict(id='aggregation_stable10', name='终审共识 Stable Top 10', lane='daily',
         finder=('json_period', 'storage/outputs/aggregation/aggregation_{period}.json'),
         extract=_extract_json_dated(['stable_top10'], take=10)),
    dict(id='genetic', name='遗传算法', lane='research',
         finder=('md_period', 'storage/reports/genetic_algorithm_report_{period}.md'),
         extract=lambda t, d: _grab_nums(t, r'尖刀金胆[^`]*`(\d+)`', take=1)),
    # ── daily 舱: 无期号文件名, 靠日期定位 ──
    dict(id='point_suppression', name='空间高压反弹与影子追踪', lane='daily',
         finder=('md_period_date', 'storage/outputs/point_suppression/未开点位反弹分析_{date_c}_T{period}.md'),
         extract=_extract_suppression_top3),
    dict(id='point_omission', name='点位与遗漏', lane='daily',
         finder=('omission_date', 'storage/outputs/point_omission/{date}/daily_report.md'),
         extract=_extract_omission_top5),
    # ── daily 舱: 覆盖式落盘, 必须核对内部目标期号 ──
    dict(id='tri_high', name='三高×点位协同', lane='daily',
         finder=('json_latest', 'storage/points/tri_high_analysis.json'),
         require_target_json=True, extract=_extract_json_dated(['recommendations.top3_gold'], take=3)),
    dict(id='prime_composite', name='质合数与尾数香农熵推演', lane='daily',
         finder=('json_latest', 'storage/stats/prime_tail_entropy_analysis.json'),
         require_target_json=True, extract=_extract_json_dated(['top3_gold'], take=3)),
    dict(id='psychological_game', name='心理博弈论逆向推演', lane='daily',
         finder=('json_latest', 'storage/stats/psychological_game_analysis.json'),
         require_target_json=True, extract=_extract_json_dated(['top3_gold'], take=3)),
    dict(id='multi_resonance', name='多维共振', lane='daily',
         finder=('json_latest', 'storage/stats/multi_resonance_consensus.json'),
         require_target_json=True, extract=_extract_json_dated(['golden_core_details'], take=5, listify=True)),
    dict(id='follow_rank', name='跟随统计推演 (1码×70期窗口)', lane='daily',
         finder=('json_period', 'storage/outputs/follow_rank/follow_rank_{period}.json'),
         require_target_json=True, extract=_extract_json_dated(['top3_gold'], take=3)),
    dict(id='thirty_ball', name='30码黄金实战大底 (成员=被回测算法)', lane='daily',
         finder=('json_period', 'storage/outputs/thirty_ball/thirty_ball_{period}.json'),
         require_target_json=True, extract=_extract_json_dated(['picks'], take=30)),
    dict(id='gold_pick2', name='黄金定胆选2搭档', lane='daily',
         finder=('txt_period', 'storage/outputs/gold_pick2/定金选2预测_{period}.txt'),
         extract=_extract_gold_pick2),
    # ── research 舱: 覆盖式落盘 ──
    dict(id='dtw', name='DTW 动态时间规整', lane='research',
         finder=('json_latest', 'storage/outputs/dtw_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    dict(id='tda', name='TDA 拓扑数据分析', lane='research',
         finder=('json_latest', 'storage/outputs/tda_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    dict(id='transformer', name='Transformer 时序', lane='research',
         finder=('json_latest', 'storage/outputs/transformer_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    dict(id='matrix_profile', name='Matrix Profile', lane='research',
         finder=('json_latest', 'storage/outputs/matrix_profile_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    dict(id='linear_algebra', name='线性代数特征', lane='research',
         finder=('json_latest', 'storage/outputs/linear_algebra_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    dict(id='random_forest', name='随机森林', lane='research',
         finder=('json_latest', 'storage/outputs/random_forest_latest.json'),
         require_target_json=True, extract=_extract_json_dated(['top5_gold', 'top3_gold'], take=5)),
    # ── 大报引擎内部模块: 只在日报里留档 ──
    dict(id='trinity_top5', name='Trinity 三维融合 Top 5', lane='daily',
         finder=('daily_report', ''),
         extract=lambda t, d: _grab_nums(t, r'极秘 Top 5\**\s*[：:]\s*`\[([\d,\s]+)\]`', take=5)),
    dict(id='trinity_top12', name='Trinity 三维融合 Top 12', lane='daily',
         finder=('daily_report', ''),
         extract=lambda t, d: _grab_nums(t, r'极秘 Top 12\**\s*[：:]\s*`\[([\d,\s]+)\]`', take=12)),
    # ── 大报引擎内部子推荐: 只在自学习状态里按期留档 ──
    dict(id='optimal_pick2', name='极简选2 黄金搭档(全场唯一推荐)', lane='daily',
         finder=('state_history', ''),
         extract=_extract_state_key('optimal_pick2', take=2)),
    dict(id='traditional_ai_top5', name='传统AI置信度 Top 5 (对照组)', lane='daily',
         finder=('state_history', ''),
         extract=_extract_state_key('conf_top5', take=5)),
    dict(id='traditional_ai_top12', name='传统AI综合拦截 Top 12 (对照组)', lane='daily',
         finder=('state_history', ''),
         extract=_extract_state_key('conf_top12', take=12)),
    dict(id='mrmr_top12', name='熵控优化 mRMR Top 12', lane='daily',
         finder=('state_history', ''),
         extract=_extract_state_key('mrmr_top12', take=12)),
    dict(id='deep_assoc_consensus', name='方案2 跨规则共识', lane='daily',
         finder=('state_history', ''),
         extract=_extract_state_key('deep_consensus', take=4)),
    # ── 未被注册表收录, 但有真实票面的模块 (复盘需要, 不参与投票) ──
    dict(id='spear_shield', name='一胆拖三盾 · 选2组合拳', lane='daily',
         finder=('md_period', 'storage/outputs/reports/spear_shield_report_{period}.md'),
         extract=lambda t, d: _grab_nums(t, r'4\s*码钢铁防守包围圈\**\s*[：:]\s*`([\d\s]+)`', take=4)),
    dict(id='point_road_compressor', name='点位012偏态压缩', lane='daily',
         finder=('json_period', 'storage/outputs/point_road_compressor/point_road_compressed_{period}.json'),
         require_target_json=True, extract=_extract_json_dated(['top3_gold'], take=3)),
    dict(id='road_prime_shrink', name='决策树012路质合多梯度缩水', lane='daily',
         finder=('json_period', 'storage/outputs/road_prime_shrink/road_prime_shrink_{period}.json'),
         require_target_json=True, extract=_extract_json_dated(['top3_gold'], take=3)),
]


# ══════════════════════════════════════════════════════════════════════════
#  收割主流程
# ══════════════════════════════════════════════════════════════════════════

def infer_target_period() -> Tuple[str, str]:
    """推断当前应录入的目标期号与其日期 (最新开奖期 + 1)。"""
    from backend.utils.history_loader import load_history
    hist = load_history()
    if not hist:
        raise RuntimeError("历史开奖为空, 无法推断目标期")
    latest = str(hist[0]["issue"])
    latest_date = str(hist[0].get("date") or "")
    target = str(int(latest) + 1)
    try:
        d = datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)
        target_date = d.strftime("%Y-%m-%d")
    except Exception:
        target_date = datetime.now().strftime("%Y-%m-%d")
    return target, target_date


def harvest(target_period: Optional[str] = None, target_date: Optional[str] = None,
            verbose: bool = True, refresh_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """把各模块当期的推荐号码收割进追加式前瞻账。返回明细报告 dict。

    refresh_ids: 需要**显式重收**的模块 id 列表(口径修正用)。
                 默认 None = 只补新账(幂等); 点名者会覆盖其同期旧账(已开奖对账的账仍受保护)。
    """
    from backend.core.module_gate import record_module_picks, refresh_module_picks

    if not target_period:
        target_period, target_date = infer_target_period()
    target_period = str(target_period)
    target_date = target_date or datetime.now().strftime("%Y-%m-%d")

    # 2026-10-21 P1 缺陷修复 (Bug#9)：收割器原先不看注册表状态，
    # 已判 retired / vote_weight=0 的模块 (实测 lstm、datasource_1x2_hot) 每天仍被收进前瞻账。
    # 后果：(a) 全模块看板把退役模块当"当期现役推荐"陈列；
    #       (b) module_ledger_report 按退役模块算 Lift 并纳入 BH-FDR 检验族，
    #           平白多算试验 → 稀释所有真信号的 q 值。
    # 退役即停账。历史口径补录请直接用 core.module_gate.refresh_module_picks（显式底层 API），
    # 不要借 harvest(refresh_ids=) 复活退役票 —— 2026-10-22 Bug#6 已收紧本入口。
    try:
        from backend.core.module_gate import ModuleGate
        _gate = ModuleGate()
        _retired_ids = set(_gate.retired_ids())
    except Exception as _ge:
        _gate, _retired_ids = None, set()
        print('  ⚠️ 注册表状态读取失败，本次不拦退役模块收割: %s' % _ge)

    refresh_ids = set(str(x) for x in (refresh_ids or []))
    # 2026-10-22 护栏修复 (Bug#6)：原设计中 refresh_ids 可以点名退役模块强制入账
    # (spec['id'] not in refresh_ids)，导致批量重收脚本把已退役的 lstm 又写回了 2026281 期账。
    # 退役是无条件地板：refresh_ids 只能重收「未退役」模块，绝不允许借重收复活退役票。
    if refresh_ids & _retired_ids:
        revived = sorted(refresh_ids & _retired_ids)
        refresh_ids -= _retired_ids
        print('  ⚠️ refresh_ids 点名了退役模块，已拒绝强制入账: %s' % ', '.join(revived))
    recorded: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for spec in EXTRACTORS:
        # Bug#6 后退役拦截为无条件地板 (refresh_ids 已剔除退役 id)
        if spec['id'] in _retired_ids:
            skipped.append({'id': spec['id'], 'name': spec['name'],
                            'reason': '已退役 (注册表 status=retired, 无出号表决权)，停止记账'})
            continue

        finder_kind, template = spec['finder']
        path: Optional[str] = None
        payload: Dict[str, Any] = {}
        err = ''

        try:
            if finder_kind in ('md_period', 'txt_period', 'json_period'):
                path = _find_file(template, target_period, target_date)
            elif finder_kind == 'md_period_date':
                path = _find_file(template, target_period, target_date)
            elif finder_kind == 'omission_date':
                path = _find_point_omission(target_period, target_date)
            elif finder_kind == 'json_latest':
                path = _find_latest_json(template, target_period, target_date)
            elif finder_kind == 'daily_report':
                path = _find_daily_report(target_period, target_date)
            elif finder_kind == 'state_history':
                payload = _find_state_history(target_period) or {}
                path = 'state_history' if payload else None
                if not path:
                    skipped.append({'id': spec['id'], 'name': spec['name'],
                                    'reason': '自学习状态里没有 %s 期的记录' % target_period})
                    continue
            else:
                err = '未知定位方式: %s' % finder_kind
        except Exception as e:
            err = '定位异常: %s' % e

        if err:
            skipped.append({'id': spec['id'], 'name': spec['name'], 'reason': err})
            continue
        if not path:
            skipped.append({'id': spec['id'], 'name': spec['name'],
                            'reason': '当期产物不存在 (%s)' % (template or finder_kind)})
            continue

        try:
            if finder_kind == 'state_history':
                text = ''
                src_label = 'storage/cache/self_learning_state.json#%s' % target_period
            elif path.endswith('.json'):
                payload = json.load(open(path, encoding='utf-8', errors='replace'))
                claimed = _json_target(payload)
                # 覆盖式落盘必须核对自己声称的目标期, 防止把上一期号码当本期收进来
                if spec.get('require_target_json') and claimed != target_period:
                    skipped.append({'id': spec['id'], 'name': spec['name'],
                                    'reason': '产物目标期=%s, 与本期 %s 不符(未刷新)' % (claimed, target_period)})
                    continue
                text = ''
                src_label = os.path.relpath(path, _PROJ_DIR).replace('\\', '/')
            else:
                text = open(path, encoding='utf-8', errors='replace').read()
                src_label = os.path.relpath(path, _PROJ_DIR).replace('\\', '/')
        except Exception as e:
            skipped.append({'id': spec['id'], 'name': spec['name'], 'reason': '读取失败: %s' % e})
            continue

        try:
            picks = list(spec['extract'](text, payload) or [])
        except Exception as e:
            skipped.append({'id': spec['id'], 'name': spec['name'], 'reason': '抽取异常: %s' % e})
            continue

        if not picks:
            skipped.append({'id': spec['id'], 'name': spec['name'],
                            'reason': '产物存在但未抽取到号码 (%s)' % os.path.basename(path)})
            continue

        recorded.append({'id': spec['id'], 'name': spec['name'], 'lane': spec['lane'],
                         'picks': picks, 'source': src_label})

    refresh_set = set(refresh_ids or [])
    added = record_module_picks(
        int(target_period),
        {r['id']: r['picks'] for r in recorded if r['id'] not in refresh_set},
    )
    refreshed = 0
    if refresh_set:
        refreshed = refresh_module_picks(
            int(target_period),
            {r['id']: r['picks'] for r in recorded if r['id'] in refresh_set},
        )

    result = {
        'status': 'ok',
        'target_period': target_period,
        'target_date': target_date,
        'generated_at': datetime.now().isoformat(),
        'recorded_count': len(recorded),
        'newly_added': added,
        'refreshed': refreshed,
        'skipped_count': len(skipped),
        'recorded': recorded,
        'skipped': skipped,
    }

    if verbose:
        print('=' * 76)
        print('  📥 逐模块预测收割 (Per-Module Picks Harvest)  目标期 %s (%s)' % (target_period, target_date))
        print('=' * 76)
        for r in recorded:
            print('  ✅ %-22s %-28s %s' % (r['id'], r['name'],
                                          ' '.join('%02d' % n for n in r['picks'])))
        print('  ── 已收 %d 个模块, 新写入前瞻账 %d 条, 重收修正 %d 条 ──' % (len(recorded), added, refreshed))
        if skipped:
            print('  ⚠️  未收割 %d 个:' % len(skipped))
            for s in skipped:
                print('     · %-22s %s' % (s['id'], s['reason']))
        print('=' * 76)

    # 留档收割明细, 便于事后追责"这天到底收了谁的号"
    out_dir = os.path.join(_PROJ_DIR, 'storage', 'reviews', 'harvest')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'harvest_%s.json' % target_period)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result['report_file'] = out_file
    return result


if __name__ == '__main__':
    harvest(verbose=True)