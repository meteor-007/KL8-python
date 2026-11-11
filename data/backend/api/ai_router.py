# -*- coding: utf-8 -*-
"""
K8-Quant AI 顾问路由模块 (FastAPI Router)
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.gemini_service import GeminiQuantAdvisor

router = APIRouter(prefix="/api/v1/ai", tags=["AI 智能操盘大脑"])

# 全局单例，在 api_server 中初始化时注入 data_service
advisor_instance: Optional[GeminiQuantAdvisor] = None


def get_advisor():
    global advisor_instance
    import importlib
    import backend.api.gemini_service as gem_svc
    try:
        importlib.reload(gem_svc)
    except Exception:
        pass
    data_svc = advisor_instance.data_service if advisor_instance else None
    return gem_svc.GeminiQuantAdvisor(data_service=data_svc)


class ChatMessage(BaseModel):
    role: str = Field(..., description="发言角色: user 或 model")
    content: str = Field(..., description="发言内容")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户提问内容")
    history: Optional[List[ChatMessage]] = Field(default=[], description="上下文历史对话")
    api_key: Optional[str] = Field(default=None, description="前端传入的临时 API Key (可选)")
    model: Optional[str] = Field(default=None, description="调用的模型名称 (可选，留空使用系统默认)")


class AnalyzeRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="前端传入的临时 API Key (可选)")
    model: Optional[str] = Field(default=None, description="调用的模型名称 (可选，留空使用系统默认)")


@router.get("/status")
def get_ai_status(advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """获取当前 AI 服务的配置状态与可用模型"""
    return {
        "configured": advisor.is_configured(),
        "provider": "企业专线 AI 中转站 (DeepSeek / OpenAI Protocol)",
        "default_model": advisor.default_model,
        "relay_url": advisor.relay_url
    }


@router.post("/chat")
def chat_with_ai(req: ChatRequest, advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """与智能操盘手进行对话交互 (普通单包模式)"""
    history_dict = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    res = advisor.chat(
        message=req.message,
        history=history_dict,
        client_key=req.api_key,
        model=req.model
    )
    return res


@router.post("/chat-stream")
def chat_stream_with_ai(req: ChatRequest, advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """与智能操盘手进行 SSE 流式打字机交互 (首字秒开、逐字输出)"""
    history_dict = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    generator = advisor.chat_stream(
        message=req.message,
        history=history_dict,
        client_key=req.api_key,
        model=req.model
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/analyze-today")
def analyze_today_predictions(req: AnalyzeRequest, advisor: GeminiQuantAdvisor = Depends(get_advisor)):
    """一键触发 AI 解读今日量化大盘与推荐号码"""
    res = advisor.analyze_today(
        client_key=req.api_key,
        model=req.model
    )
    return res
