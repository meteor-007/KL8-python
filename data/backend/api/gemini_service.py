# -*- coding: utf-8 -*-
"""
K8-Quant Gemini AI 智能操盘大脑服务
集成 Google Gemini API，结合快乐8全量化数据提供专业、大白话的智能解读与交互问答。
"""
import os
import json
import requests
from typing import Dict, Any, List, Optional

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiQuantAdvisor:
    """Gemini 智能操盘手顾问服务"""

    def __init__(self, data_service=None):
        self.data_service = data_service
        self.default_api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    def get_api_key(self, client_key: Optional[str] = None) -> str:
        """获取有效的 API Key（优先使用前端传入的临时 Key，否则使用系统环境变量）"""
        if client_key and client_key.strip():
            return client_key.strip()
        return self.default_api_key

    def is_configured(self) -> bool:
        """检查系统是否配置了默认 API Key"""
        return bool(self.default_api_key)

    def _build_system_prompt(self, latest_context: str = "") -> str:
        """构建操盘顾问系统提示词（老派量化操盘手口吻，大白话）"""
        return (
            "你是一名身经百战、精打细算的老派量化操盘手兼数据分析大师。你的职责是基于系统提供的快乐8量化数据，"
            "为用户提供客观、通俗易懂（大白话）的走势分析、号码特征解读和风险提示。\n\n"
            "【交流规范】：\n"
            "1. 坚决使用接地气的大白话交流，如果提到专业量化术语，必须在旁边紧跟括号注明大白话含义，例如：\n"
            "   - 多维共振（大白话：几个方法算出来的交集金胆）\n"
            "   - 导数变化率（大白话：冷热势头是上升还是下降）\n"
            "   - 遗漏回补（大白话：冷号憋久了找机会回补）\n"
            "   - 均值回归（大白话：风水轮流转，冷号必出、火号必死）\n"
            "   - 结构性突变（大白话：大环境变盘了）\n"
            "   - 物理熔断（大白话：信号太弱时紧急刹车少买）\n"
            "2. 保持严谨客观，彩票本质是独立随机事件，分析基于历史统计走势与算法模型，严禁承诺百分之百中奖，提示合理风控。\n"
            "3. 语言生动有力、条理分明，善于运用列表和重点标粗。\n\n"
            f"【当前系统最新量化快照数据】：\n{latest_context}\n"
        )

    def _gather_latest_context(self) -> str:
        """自动从 DataService 提取最新一期的核心量化指标作为背景上下文"""
        if not self.data_service:
            return "（暂未获取到最新量化大盘数据）"

        try:
            summary = self.data_service.get_dashboard_summary()
            latest_period = summary.get("latest_period", "未知期号")
            latest_date = summary.get("latest_date", "未知日期")
            
            # 提取终审共识或推荐
            consensus = summary.get("consensus_core", {})
            gold_pool = consensus.get("golden_core", [])
            recommended = summary.get("recommended_5", [])
            top12 = summary.get("top12", [])
            
            overview = summary.get("overview_snapshot", {})
            
            lines = [
                f"- 目标分析期号: 第 {latest_period} 期 ({latest_date})",
                f"- 系统金胆核心 (Golden Core): {gold_pool}",
                f"- 首席特供推荐5码: {recommended}",
                f"- 综合优选 Top 12: {top12}",
                f"- 各模块快照概览: {json.dumps(overview, ensure_ascii=False) if overview else '正常'}"
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"（提取量化数据上下文发生轻微异常: {e}）"

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        client_key: Optional[str] = None,
        model: str = DEFAULT_MODEL
    ) -> Dict[str, Any]:
        """与 Gemini 进行问答交互"""
        api_key = self.get_api_key(client_key)
        if not api_key:
            return {
                "success": False,
                "error": "未检测到 Gemini API Key。请在系统环境变量设置 GEMINI_API_KEY，或在前端界面右上角输入您的 Google Gemini API Key！"
            }

        context = self._gather_latest_context()
        system_instruction = self._build_system_prompt(context)

        contents = []
        if history:
            for item in history[-6:]:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": item.get("content", "")}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": message}]
        })

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "maxOutputTokens": 2048
            }
        }

        url = f"{GEMINI_API_URL.format(model=model)}?key={api_key}"

        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=35)
            if resp.status_code != 200:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": f"Gemini API 响应异常 (HTTP {resp.status_code}): {err_detail}"
                }

            result_json = resp.json()
            candidates = result_json.get("candidates", [])
            if not candidates:
                return {"success": False, "error": "Gemini 未返回任何生成内容"}

            reply_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {
                "success": True,
                "reply": reply_text,
                "model": model,
                "context_period": self.data_service.get_dashboard_summary().get("latest_period", "") if self.data_service else ""
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "请求 Gemini API 超时，请检查网络连接或稍后重试。"}
        except Exception as e:
            return {"success": False, "error": f"调用 Gemini 发生异常: {str(e)}"}

    def analyze_today(self, client_key: Optional[str] = None, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
        """一键让 Gemini 解读今日量化大屏走势"""
        prompt = (
            "请结合当前系统最新一期的量化指标（金胆核心、首席推荐5码、Top12以及各维度分布），"
            "为用户提供一份结构清晰、语言生动接地气的大白话操盘综述报告，包含：\n"
            "1. 📊 今日大盘走势基调（大白话：今天大势偏向哪种形态，风水轮流转趋势）\n"
            "2. 🎯 核心金胆与热力聚焦（大白话：哪些号底气足、哪些号有连带跟班关系）\n"
            "3. ⚠️ 操盘手风控预警（大白话：哪些区域防冷回补、如何控制仓位）\n"
            "4. 💡 操盘手一句话锦囊"
        )
        return self.chat(message=prompt, history=[], client_key=client_key, model=model)
