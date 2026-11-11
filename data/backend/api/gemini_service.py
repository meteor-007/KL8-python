# -*- coding: utf-8 -*-
"""
K8-Quant 全栈 AI 智能操盘大脑中继服务
支持企业专属 OpenAI 兼容格式中转站（如 DeepSeek / OneAPI）与 Google 官方 Gemini 原生接口，
自动挂载快乐8最新量化数据快照，提供 100% 大白话、实战级的专业智能解读与问答交互。
"""
import os
import json
import requests
from typing import Dict, Any, List, Optional

DEFAULT_RELAY_URL = os.environ.get("AI_BASE_URL", "http://ai.xinjifamily.com:3000/v1").rstrip("/")
# 2026-09-10 整改 F1：硬编码 Key 已移除（曾泄露于源码与 git 历史，须立即轮换）；
# 必须通过 AI_API_KEY 环境变量提供，缺失时返回空串并由调用方报错。
DEFAULT_RELAY_KEY = os.environ.get("AI_API_KEY", "").strip()
DEFAULT_MODEL = os.environ.get("AI_MODEL", "deepseek-v4-flash-0731").strip()


class GeminiQuantAdvisor:
    """智能操盘顾问大脑中继服务"""

    def __init__(self, data_service=None):
        self.data_service = data_service
        self.relay_url = os.environ.get("AI_BASE_URL", DEFAULT_RELAY_URL).rstrip("/")
        self.relay_key = os.environ.get("AI_API_KEY", DEFAULT_RELAY_KEY).strip()
        self.default_model = os.environ.get("AI_MODEL", DEFAULT_MODEL).strip()
        # 兼容旧版 Google 原生配置
        self.google_api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    def get_api_key(self, client_key: Optional[str] = None) -> str:
        """获取有效的 API Key（优先使用前端传入临时 Key，否则读取中转站 Key 或原生 Key）"""
        if client_key and client_key.strip():
            return client_key.strip()
        if self.relay_key:
            return self.relay_key
        return self.google_api_key

    def get_model(self, client_model: Optional[str] = None) -> str:
        """获取生效的模型名称"""
        if client_model and client_model.strip():
            return client_model.strip()
        return self.default_model

    def is_configured(self) -> bool:
        """检查系统是否配置了可用 Key"""
        return bool(self.relay_key or self.google_api_key)

    def _build_system_prompt(self, latest_context: str = "") -> str:
        """构建操盘顾问系统提示词（老派量化操盘手口吻，大白话实战风格）"""
        return (
            "你是一名身经百战、精打细算的老派量化操盘手兼数据分析大师。你的职责是基于系统提供的快乐8最新全量化数据，"
            "为用户提供客观、通俗易懂（大白话）的走势分析、号码特征解读和风险提示。\n\n"
            "【交流规范】：\n"
            "1. 坚决使用接地气的大白话交流，绝不讲空洞玄学。如果提到专业量化术语，必须在旁边紧跟括号注明大白话含义，例如：\n"
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
            return "（暂未挂载系统实时量化大盘数据）"

        try:
            pred = self.data_service.get_latest_prediction() or {}
            sys_stat = self.data_service.get_system_status() or {}

            target_period = pred.get("period", sys_stat.get("target_period", "未知期号"))
            target_date = pred.get("date", sys_stat.get("target_date", "未知日期"))
            latest_draw_period = sys_stat.get("latest_draw_period", "未知期号")
            latest_draw_nums = sys_stat.get("latest_draw_numbers", [])

            top5_gold = pred.get("top5_gold", [])
            hidden_5 = pred.get("hidden_energy_5", [])
            golden_pair = pred.get("golden_pair", [])
            golden_pair_reason = pred.get("golden_pair_reason", "")
            top12 = pred.get("top12_pool", [])
            golden_core = pred.get("golden_core", [])
            weights_plain = pred.get("weights_plain", "")

            lines = [
                f"- 目标研判期号: 第 {target_period} 期 ({target_date})",
                f"- 上一期实开结果: 第 {latest_draw_period} 期开出 {latest_draw_nums}",
                f"- 今日核心金胆 Top 5: {top5_gold}",
                f"- 首席战略官推荐 5 码: {hidden_5}",
                f"- 今日极简选2黄金搭档: {golden_pair} (协同依据: {golden_pair_reason})",
                f"- 多维共振核心号码池: {golden_core}",
                f"- 综合优选 Top 12 候选池: {top12}",
                f"- 当前三维融合模型权重: {weights_plain}"
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"（提取量化数据上下文发生轻微异常: {e}）"

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        client_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """与 AI 操盘大脑进行交互对话（优先走公司企业中转站，零翻墙、极速直连）"""
        api_key = self.get_api_key(client_key)
        target_model = self.get_model(model)

        if not api_key:
            return {
                "success": False,
                "error": "未检测到有效的 AI API Key，请在系统 .env 中配置 AI_API_KEY。"
            }

        context = self._gather_latest_context()
        system_instruction = self._build_system_prompt(context)

        # ────────── 1. 优先使用企业中转站 (OpenAI 兼容协议) ──────────
        if self.relay_url:
            chat_url = f"{self.relay_url}/chat/completions"
            messages = [{"role": "system", "content": system_instruction}]

            if history:
                for item in history[-8:]:
                    role = "assistant" if item.get("role") in ["model", "assistant"] else "user"
                    messages.append({"role": role, "content": item.get("content", "")})

            messages.append({"role": "user", "content": message})

            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            try:
                resp = requests.post(chat_url, json=payload, headers=headers, timeout=30)
                if resp.status_code != 200:
                    err_msg = resp.text
                    try:
                        err_msg = resp.json().get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"企业 AI 中转站响应异常 (HTTP {resp.status_code}): {err_msg}"
                    }

                res_json = resp.json()
                choices = res_json.get("choices", [])
                if not choices:
                    return {"success": False, "error": "AI 中转站未返回任何有效回复内容"}

                reply_text = choices[0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "reply": reply_text,
                    "model": target_model,
                    "context_period": self.data_service.get_dashboard_summary().get("latest_period", "") if self.data_service else ""
                }
            except requests.exceptions.Timeout:
                return {"success": False, "error": "请求 AI 中转站响应超时，请稍后重试。"}
            except Exception as e:
                return {"success": False, "error": f"调用中转站发生异常: {str(e)}"}

        # ────────── 2. 回退走 Google 官方原生协议 ──────────
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        contents = []
        if history:
            for item in history[-6:]:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": item.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        gemini_payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
        }
        proxies = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
        try:
            resp = requests.post(gemini_url, json=gemini_payload, headers={"Content-Type": "application/json"}, proxies=proxies, timeout=30)
            if resp.status_code != 200:
                return {"success": False, "error": f"Google Gemini 响应异常 (HTTP {resp.status_code}): {resp.text}"}
            result_json = resp.json()
            reply_text = result_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"success": True, "reply": reply_text, "model": target_model}
        except Exception as e:
            return {"success": False, "error": f"Google 直连异常: {str(e)}"}

    def analyze_today(self, client_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """一键让 AI 智能解读今日大盘走势"""
        prompt = (
            "请结合当前系统最新一期的量化指标（核心金胆、特供推荐5码、Top12候选池以及各维度走势），"
            "为用户提供一份结构清晰、语言生动接地气的大白话操盘综述报告，包含：\n"
            "1. 📊 今日大盘走势基调（大白话：今天大势偏向哪种形态，风水轮流转趋势）\n"
            "2. 🎯 核心金胆与热力聚焦（大白话：哪些号底气足、哪些号有连带跟班关系）\n"
            "3. ⚠️ 操盘手风控预警（大白话：哪些区域防冷回补、如何控制仓位）\n"
            "4. 💡 操盘手一句话锦囊"
        )
        return self.chat(message=prompt, history=[], client_key=client_key, model=model)

    def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        client_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """流式与 AI 操盘大脑进行交互 (SSE Server-Sent Events 流式打字机输出)"""
        api_key = self.get_api_key(client_key)
        target_model = self.get_model(model)

        if not api_key:
            err_data = json.dumps({"error": "未检测到有效的 AI API Key，请在系统 .env 中配置 AI_API_KEY。"}, ensure_ascii=False)
            yield f"data: {err_data}\n\n"
            yield "data: [DONE]\n\n"
            return

        context = self._gather_latest_context()
        system_instruction = self._build_system_prompt(context)

        # 优先使用企业中转站 (OpenAI 兼容协议 stream=True)
        if self.relay_url:
            chat_url = f"{self.relay_url}/chat/completions"
            messages = [{"role": "system", "content": system_instruction}]

            if history:
                for item in history[-8:]:
                    role = "assistant" if item.get("role") in ["model", "assistant"] else "user"
                    messages.append({"role": role, "content": item.get("content", "")})

            messages.append({"role": "user", "content": message})

            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
                "stream": True
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            try:
                with requests.post(chat_url, json=payload, headers=headers, stream=True, timeout=45) as resp:
                    if resp.status_code != 200:
                        err_text = f"企业 AI 中转站响应异常 (HTTP {resp.status_code})"
                        yield f"data: {json.dumps({'error': err_text}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    for line in resp.iter_lines():
                        if not line:
                            continue
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:].strip()
                            if data_str == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                j = json.loads(data_str)
                                choices = j.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        chunk_payload = json.dumps({"content": content}, ensure_ascii=False)
                                        yield f"data: {chunk_payload}\n\n"
                            except Exception:
                                pass
            except requests.exceptions.Timeout:
                yield f"data: {json.dumps({'error': '请求 AI 中转站响应超时，请稍后重试。'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'调用中转站发生异常: {str(e)}'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
        else:
            # 降级走普通 chat 并整体一次性 yield
            res = self.chat(message=message, history=history, client_key=client_key, model=model)
            if res.get("success"):
                yield f"data: {json.dumps({'content': res.get('reply', '')}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'error': res.get('error', '未知错误')}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
