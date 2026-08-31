# -*- coding: utf-8 -*-
"""
K8-Quant AI 顾问路由模块 (FastAPI Router)
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.api.gemini_service import GeminiQuantAdvisor

router = APIRouter(prefix="/api/v1/ai", tags=["AI 智能操盘大脑"])

# 全局单例，在 api_server 中初始化时注入 data_service
advisor_instance: Optional[GeminiQuantAdvisor] = None


def get_advisor() -> GeminiQuantAdvisor:
    global advisor_instance
    if advisor_instance is None:
        advisor_instance = GeminiQuantAdvisor()
    return advisor_instance


class ChatMessage(BaseModel):
    role: str = Field(..., description="发言角色: user 或 model")
    content: str = Field(..., description="发言内容")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户提问内容")
    history: Optional[List[ChatMessage]] = Field(default=[], description="上下文历史对话")
    api_key: Optional[str] = Field(default=None, description="前端传入的临时 Gemini API Key (可选)")
    model: Optional[str] = Field(default="gemini-1.5-flash", description="调用的 Gemini 模型名称")


class AnalyzeRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="前端传入的临时 Gemini API Key (可选)")
    model: Optional[str] = Field(default="gemini-1.5-flash", description="调用的 Gemini 模型名称")


@router.get("/status")
def get_ai_status(advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """获取当前 AI 服务的配置状态与可用模型"""
    return {
        "configured": advisor.is_configured(),
        "provider": "Google Gemini",
        "default_model": "gemini-1.5-flash",
        "available_models": [
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash (极速推荐)"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (新一代多模态)"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (深度推理)"}
        ]
    }


@router.post("/chat")
def chat_with_ai(req: ChatRequest, advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """与 Gemini 智能操盘手进行对话交互"""
    history_dict = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    res = advisor.chat(
        message=req.message,
        history=history_dict,
        client_key=req.api_key,
        model=req.model or "gemini-1.5-flash"
    )
    if not res.get("success"):
        return res
    return res


@router.post("/analyze-today")
def analyze_today_predictions(req: AnalyzeRequest, advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """一键触发 Gemini 解读今日量化大盘与推荐号码"""
    res = advisor.analyze_today(
        client_key=req.api_key,
        model=req.model or "gemini-1.5-flash"
    )
    return res
