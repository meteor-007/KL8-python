#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快乐8 日报引擎 v3.2 — 工业级深度融合版 + FO Baseline 附录
==========================================================
- 主报告: FullReportEngine (20 方案 / 11 模块)
- 附录 A: FO 单通道 baseline + 自学习门控
"""
import os
import sys
import json
import logging
import traceback
from typing import Dict, Optional

import os, sys
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.paths import get_project_root, data_path, _ensure_project_path
_ensure_project_path()
_PROJ = get_project_root()


from pipeline.data_center import DataCenter
from pipeline.full_report_engine import FullReportEngine

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_PROJ, 'logs', 'engine_runtime.log'), encoding='utf-8'),
    ],
)
logger = logging.getLogger("LotteryEngine")


class DailyReportOrchestrator:
    """日报编排：工业级主报告 + FO Baseline 附录"""

    def __init__(self):
        # 不要在外层长持 Excel 锁再 initialize：
        # initialize 内部会同进程写 Excel；若外层持锁再开子进程会抢锁失败。
        # 各步骤已各自 excel_lock，此处只做编排。
        DataCenter.reset_singleton()
        self.dc = DataCenter()
        self.dc.initialize()

    def _load_weekly_monitor(self) -> Dict:
        path = os.path.join(_PROJ, 'cache', 'weekly_channel_monitor.json')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _append_fo_baseline_appendix(self, report_path: str, fo_result: Dict,
                                     gate: Dict, loop_report: Optional[Dict]):
        """在工业级主报告末尾追加 FO Baseline 附录"""
        latest_issue = self.dc.latest_issue
        try:
            target_issue = str(int(latest_issue) + 1)
        except (ValueError, TypeError):
            target_issue = "未知期号"
        weekly = self._load_weekly_monitor()
        ch_stats = (weekly.get('channel_validation') or {}).get('channel_stats', [])

        golden = sorted(fo_result.get('golden', []))
        silver = sorted(fo_result.get('silver', []))
        top12 = sorted(golden + [n for n in silver if n not in golden])[:12]
        top20 = sorted(fo_result.get('top20', []))
        conf = fo_result.get('confidence', {})

        with open(report_path, 'a', encoding='utf-8') as f:
            f.write("\n## 附录 A：FO Baseline 单通道对照\n\n")
            f.write("> FO 单通道用于 Walk-Forward 回测门控，不参与主推荐权重。\n\n")
            f.write(f"- **通道：** `FO` (Feature Optimizer 单通道)\n")
            f.write(f"- **环境：** `{fo_result.get('environment')}` | "
                    f"**说明：** {conf.get('description', 'FO 单通道 baseline')}\n")
            f.write(f"- **金胆 Top5：** `{golden}`\n")
            f.write(f"- **综合 Top12：** `{top12}`\n")
            f.write(f"- **Top20：** `{top20}`\n\n")



            f.write("### 自学习门控\n\n")
            f.write(f"- **状态：** {gate.get('message', 'N/A')}\n")
            f.write(f"- **WF Lift (FO)：** `{gate.get('last_wf_lift', 'N/A')}` | "
                    f"**解锁阈值：** `{gate.get('lift_threshold', 1.1)}`\n")
            if loop_report:
                decision = loop_report.get('optimization_decision', loop_report.get('status', 'N/A'))
                f.write(f"- **闭环决策：** `{decision}`\n")
            f.write("\n")

            if ch_stats:
                f.write("### Weekly 通道监控 (不参与 daily)\n\n")
                f.write("> 完整报告: `cache/weekly_channel_monitor.json` "
                        "(运行 `python main_v2.py --weekly-monitor` 刷新)\n\n")
                for s in ch_stats:
                    flag = ' ✓FDR' if s.get('significant_fdr') else ''
                    f.write(f"- `{s['channel']}`: Lift={s['lift']:.3f}, p={s['p_value']:.4f}{flag}\n")
                f.write("\n")

            f.write("---\n")
            f.write("*Engine v3.2 — 工业级深度融合版 + FO Baseline 附录 via pipeline/auto_generate_daily_report.py*\n")

    def generate_report(self):
        """生成完整日报：工业级主报告 + FO Baseline 附录"""
        try:
            full_engine = FullReportEngine(self.dc)
            report_path = full_engine.generate_report()
            if not report_path:
                logger.critical("工业级主报告生成失败")
                return

            from main_v2 import run_pipeline
            from core.learning_gate import gate_status

            fo_result = run_pipeline(list(self.dc.history), top_k=20, quiet=True)
            gate = gate_status()
            self._append_fo_baseline_appendix(report_path, fo_result, gate, None)
            logger.info(f"完整日报生成完毕 (含 FO 附录): {report_path}")

        except Exception as e:
            logger.critical(f"日报编排失败: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    orchestrator = DailyReportOrchestrator()
    orchestrator.generate_report()
