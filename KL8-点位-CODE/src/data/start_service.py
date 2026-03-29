#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务启动器：启动 Web 服务前执行数据更新、分析和前端数据同步。
"""

import csv
import json
import locale
import logging
import time
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from scientific_engine import ScientificEngine


固定端口 = 5173
固定主机 = "127.0.0.1"
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
URL_RE = re.compile(rf"http://(?:localhost|127\.0\.0\.1):{固定端口}/?")


def 获取控制台编码() -> str:
    return sys.stdout.encoding or locale.getpreferredencoding(False) or "utf-8"


def 安全文本(text: str) -> str:
    encoding = 获取控制台编码()
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def 清理控制台文本(text: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", text).replace("\u200b", "").strip()
    cleaned = cleaned.replace("➜", "地址").replace("★", "*")
    url_match = URL_RE.search(cleaned)
    if "Local:" in cleaned and url_match:
        cleaned = f"本地地址: {url_match.group(0)}"
    elif "Network:" in cleaned:
        cleaned = "网络地址: 如需局域网访问，请额外使用 --host 参数。"
    elif "ready in" in cleaned and "VITE" in cleaned:
        cleaned = re.sub(r"\s+", " ", cleaned)
    return 安全文本(cleaned)


class 安全格式化器(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return 安全文本(super().format(record))


def 创建日志器() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    common_format = "%(asctime)s - %(levelname)s - %(message)s"

    file_handler = logging.FileHandler("service_starter.log", encoding="utf-8", mode="a")
    file_handler.setFormatter(logging.Formatter(common_format))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(安全格式化器(common_format))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = 创建日志器()


def 获取子进程编码() -> str:
    return locale.getpreferredencoding(False) or sys.stdout.encoding or "utf-8"


def _get_latest_data_sum_date(data_sum_dir: Path) -> str:
    date_dirs = sorted([d.name for d in data_sum_dir.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)
    return date_dirs[0] if date_dirs else ""


def _log_expert_dashboard_summary(script_dir: Path) -> None:
    dashboard_path = script_dir / "expert_dashboard.json"
    data_sum_dir = script_dir.parent / "data-sum"
    if not dashboard_path.exists():
        logger.error("未找到专家看板导出文件：%s", dashboard_path)
        return

    try:
        data = json.loads(dashboard_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("读取专家看板导出文件失败：%s", 安全文本(str(exc)))
        return

    latest_date = str((data.get("meta") or {}).get("latestDate") or "")
    daily_views = data.get("dailyMatrixViews") or []
    latest_view_date = str(daily_views[0].get("date")) if daily_views else ""
    latest_data_sum_date = _get_latest_data_sum_date(data_sum_dir)

    logger.info("专家看板导出摘要：latestDate=%s, dailyMatrixViews=%s, recentView=%s", latest_date or "未知", len(daily_views), latest_view_date or "未知")

    if latest_data_sum_date and latest_date and latest_date < latest_data_sum_date:
        logger.warning(
            "专家看板最新日期落后于 data-sum 最新目录：dashboard=%s, data-sum=%s。请检查矩阵解析与导出链路。",
            latest_date,
            latest_data_sum_date,
        )


def 运行脚本(script_path: Path, cwd: Path, description: str) -> bool:
    if not script_path.exists():
        logger.warning("%s脚本不存在，跳过：%s", description, script_path)
        return False

    logger.info("%s：%s", description, script_path)
    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=获取子进程编码(),
        errors="replace",
    )

    if process.stdout:
        for line in process.stdout:
            line_str = 清理控制台文本(line.rstrip())
            if line_str:
                logger.info("  [%s] %s", description, line_str)

    process.wait()
    return process.returncode == 0


def 查询端口占用(port: int) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding=获取子进程编码(),
            errors="replace",
            check=False,
        )
    except OSError as exc:
        logger.error("查询端口占用失败：%s", 安全文本(str(exc)))
        return []

    listeners: list[dict[str, str]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or "LISTENING" not in line.upper():
            continue
        if f":{port}" not in line:
            continue

        parts = re.split(r"\s+", line)
        if len(parts) < 5:
            continue

        local_address = parts[1]
        state = parts[3]
        pid = parts[4]
        listeners.append(
            {
                "local_address": local_address,
                "state": state,
                "pid": pid,
                "process_name": 查询进程名(pid),
            }
        )

    return listeners


def 查询进程名(pid: str) -> str:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding=获取子进程编码(),
            errors="replace",
            check=False,
        )
    except OSError:
        return "未知进程"

    line = result.stdout.strip()
    if not line or line.startswith("INFO:"):
        return "未知进程"

    try:
        row = next(csv.reader([line]))
        return row[0] if row else "未知进程"
    except Exception:
        return "未知进程"


def 终止占用端口进程(port: int) -> bool:
    listeners = 查询端口占用(port)
    if not listeners:
        return True

    logger.warning("固定端口 %s 已被占用，准备自动终止占用进程后继续启动。", port)
    for item in listeners:
        logger.warning(
            "占用信息：PID=%s，进程=%s，地址=%s，状态=%s",
            item["pid"],
            item["process_name"],
            item["local_address"],
            item["state"],
        )

    terminated = True
    for item in listeners:
        pid = item["pid"]
        try:
            result = subprocess.run(
                ["taskkill", "/PID", pid, "/F", "/T"],
                capture_output=True,
                text=True,
                encoding=获取子进程编码(),
                errors="replace",
                check=False,
            )
        except OSError as exc:
            logger.error("终止 PID=%s 失败：%s", pid, 安全文本(str(exc)))
            terminated = False
            continue

        if result.returncode == 0:
            logger.info("已终止占用进程 PID=%s。", pid)
        else:
            logger.error(
                "终止 PID=%s 失败，返回码=%s，输出=%s",
                pid,
                result.returncode,
                清理控制台文本((result.stdout or result.stderr or "").strip()),
            )
            terminated = False

    if terminated:
        for _ in range(10):
            if not 查询端口占用(port):
                logger.info("端口 %s 已释放。", port)
                return True
            time.sleep(0.5)

        logger.warning("端口 %s 仍在释放中，将继续尝试启动。", port)
        return True

    return False


def 执行数据更新() -> bool:
    logger.info("=" * 60)
    logger.info("开始执行数据增量更新...")
    logger.info("=" * 60)

    try:
        script_dir = Path(__file__).parent
        update_script = script_dir / "data_fetcher_and_converter.py"

        if not update_script.exists():
            logger.error("数据更新脚本不存在：%s", update_script)
            return False

        logger.info("执行脚本：%s", update_script)
        process = subprocess.Popen(
            [sys.executable, str(update_script)],
            cwd=str(script_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=获取子进程编码(),
            errors="replace",
        )

        if process.stdout:
            for line in process.stdout:
                line_str = 清理控制台文本(line.rstrip())
                if line_str:
                    logger.info("  [数据更新] %s", line_str)

        process.wait()

        data_sum_dir = script_dir.parent / "data-sum"
        workflow_script = data_sum_dir / "main_workflow.py"
        expert_script = script_dir / "generate_expert_excel.py"
        export_script = script_dir / "export_expert_dashboard.py"

        logger.info("生成专家 4-sheet 汇总报表...")
        workflow_ok = 运行脚本(workflow_script, data_sum_dir, "专家汇总")
        if not workflow_ok:
            logger.warning("4-sheet 专家汇总生成失败，尝试回退到简版 Excel 生成脚本。")
            运行脚本(expert_script, script_dir, "简版专家汇总")

        logger.info("导出专家前端看板 JSON...")
        export_ok = 运行脚本(export_script, script_dir, "专家看板导出")
        if not export_ok:
            logger.warning("专家看板 JSON 导出失败，前端专家页可能无法展示最新数据。")
        else:
            _log_expert_dashboard_summary(script_dir)

        if process.returncode == 0:
            logger.info("=" * 60)
            logger.info("数据增量更新完成。")
            logger.info("=" * 60)
            return True

        logger.error("数据更新失败，返回码：%s", process.returncode)
        return False
    except Exception as exc:
        logger.error("数据更新异常：%s", 安全文本(str(exc)))
        logger.exception("详细错误信息:")
        return False


def 执行科学演变分析() -> bool:
    logger.info("=" * 60)
    logger.info("开始执行科学演变分析...")
    logger.info("=" * 60)

    try:
        base_dir = Path(__file__).parent.parent / "data-sum"
        engine = ScientificEngine(str(base_dir))
        date_dirs = sorted([d.name for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()])

        if len(date_dirs) < 2:
            logger.warning("数据不足，无法执行流形稳定性分析。")
            return True

        latest = date_dirs[-1]
        prev = date_dirs[-2]
        analysis = engine.analyze_evolution(latest, prev)

        logger.info("核心状态诊断：%s", 安全文本(str(analysis.get("entropy_state", "未知"))))
        logger.info("流形偏移率：%.1f%%", float(analysis.get("drift_rate", 0)) * 100)
        logger.info(
            "跨系统共振节点：%s",
            "、".join(analysis.get("resonance_nodes", [])) or "无",
        )

        if float(analysis.get("drift_rate", 0)) < 0.3:
            logger.info("系统处于较稳定状态，当前共振节点更值得参考。")
        else:
            logger.warning("系统存在较明显漂移，建议降低对历史惯性的依赖。")

        return True
    except Exception as exc:
        logger.error("科学演变分析执行异常：%s", 安全文本(str(exc)))
        return False


def 同步前端数据() -> bool:
    try:
        script_dir = Path(__file__).parent
        src_file = script_dir.parent / "data-sum" / "recommendation_history.csv"
        dst_file = script_dir / "recommendation_history.csv"

        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            logger.info("已同步专家推演历史至 Web 目录：%s", dst_file.name)
            return True

        logger.warning("专家推演文件不存在，跳过同步：%s", src_file)
        return False
    except Exception as exc:
        logger.error("同步前端数据失败：%s", 安全文本(str(exc)))
        return False


def 启动Web服务器() -> bool:
    logger.info("=" * 60)
    logger.info("启动 Web 服务器...")
    logger.info("=" * 60)

    try:
        project_root = Path(__file__).parent.parent.parent
        package_json = project_root / "package.json"
        if not package_json.exists():
            logger.error("项目根目录不存在 package.json：%s", project_root)
            return False

        if not 终止占用端口进程(固定端口):
            return False

        npm_cmd = shutil.which("npm") or "npm"
        command = [
            npm_cmd,
            "run",
            "dev",
            "--",
            "--host",
            固定主机,
            "--port",
            str(固定端口),
            "--strictPort",
        ]

        logger.info("项目根目录：%s", project_root)
        logger.info(
            "使用固定地址启动开发服务器：http://%s:%s/",
            固定主机,
            固定端口,
        )
        logger.info("启动命令：%s", " ".join(command))

        process = subprocess.Popen(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=获取子进程编码(),
            errors="replace",
            shell=False,
        )

        opened = False
        if process.stdout:
            for line in process.stdout:
                line_str = 清理控制台文本(line.rstrip())
                if not line_str:
                    continue

                logger.info("[Web] %s", line_str)

                url_match = URL_RE.search(line)
                if url_match and not opened:
                    url = url_match.group(0)
                    logger.info("检测到服务就绪，自动打开浏览器：%s", url)
                    webbrowser.open(url)
                    opened = True

        process.wait()

        if process.returncode == 0:
            logger.info("Web 服务器已正常退出。")
            return True

        logger.error("Web 服务器异常退出，返回码：%s", process.returncode)
        return False
    except Exception as exc:
        logger.error("启动 Web 服务器失败：%s", 安全文本(str(exc)))
        logger.exception("详细错误信息:")
        return False


def 主程序入口() -> bool:
    logger.info("")
    logger.info("数据分析系统启动引擎")
    logger.info("")

    logger.info("步骤 1/4：同步多源专家数据")
    update_success = 执行数据更新()
    if not update_success:
        logger.warning("数据更新未完全成功，将继续使用当前缓存。")

    logger.info("")
    logger.info("步骤 2/4：执行流形演变与共振检测分析")
    执行科学演变分析()

    logger.info("")
    logger.info("步骤 3/4：同步前端视图缓存")
    同步前端数据()

    logger.info("")
    logger.info("步骤 4/4：启动 Web 决策看板")
    return 启动Web服务器()


if __name__ == "__main__":
    成功 = 主程序入口()
    sys.exit(0 if 成功 else 1)
