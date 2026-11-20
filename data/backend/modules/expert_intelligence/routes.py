# -*- coding: utf-8 -*-
"""
快乐8 专家情报与自动复盘 API 路由
"""
from fastapi import APIRouter, Query, Body, HTTPException
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from backend.modules.expert_intelligence.service import expert_service

router = APIRouter(prefix="/api/expert", tags=["expert_intelligence"])

class ExpertSubmitModel(BaseModel):
    period: str
    date: Optional[str] = None
    kill_numbers: List[int] = []
    experts: Dict[str, Any] = {}

class QuickParseModel(BaseModel):
    raw_text: str

@router.get("/periods")
def get_periods():
    """获取所有已录入的专家情报期次列表"""
    return {"status": "success", "periods": expert_service.get_history_periods()}

@router.get("/current")
def get_current(period: Optional[str] = Query(None, description="指定期号，不传则默认最新期")):
    """获取指定期或最新期的完整专家推码、杀号池与对冲雷达"""
    return expert_service.get_period_data(period=period)

@router.get("/review/{period}")
def get_review(period: str):
    """获取指定期的详细对账复盘（真实开奖红球对照与专家战绩）"""
    return expert_service.get_period_review(period)

@router.post("/submit")
def submit_record(payload: ExpertSubmitModel):
    """手机端或桌面端提交/更新专家推码与杀号"""
    return expert_service.save_period_data(payload.dict())

@router.post("/quick-parse")
def quick_parse_text(payload: QuickParseModel):
    """
    智能文本快速解析器：
    支持直接将微信群或记事本内容粘贴，自动切分提取出专家号码与杀号
    """
    import re
    text = payload.raw_text.strip()
    result = {
        "kill_numbers": [],
        "experts": {}
    }

    # 解析杀号
    kill_match = re.search(r'杀号[：:\s]*([\d\s,，.]+)', text)
    if kill_match:
        nums = re.findall(r'\b\d{1,2}\b', kill_match.group(1))
        result["kill_numbers"] = sorted(list(set([int(x) for x in nums if 1 <= int(x) <= 80])))

    # 匹配各类专家行
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 发如雪
        if "发如雪" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["发如雪"] = {
                    "type": "选三/选四",
                    "pick3": nums[:3],
                    "pick4": nums[:4] if len(nums) >= 4 else nums
                }
        # 小巷
        elif "小巷" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["小巷"] = {"type": "选三单式", "pick3": nums[:3]}
        # 妹妹
        elif "妹妹" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            result["experts"]["妹妹"] = {
                "type": "点位/连号",
                "focus_point": nums[0] if nums else 12,
                "trio": nums[1:4] if len(nums) >= 4 else [30, 31, 32],
                "tail_pairs": nums[4:6] if len(nums) >= 6 else [79, 80]
            }
        # 北哥
        elif "北哥" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                dan = nums[0]
                combos = [[dan, t] for t in nums[1:6]]
                result["experts"]["北哥"] = {"type": "选二单式", "dan": dan, "combos": combos}
        # 娟子
        elif "娟子" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["娟子"] = {"type": "银胆+独荐4码", "dan": nums[0], "pick4": nums[:4]}
        # 大哥
        elif "大哥" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["大哥"] = {"type": "精选6码", "pick6": nums[:6]}
        # 老赵
        elif "老赵" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["老赵"] = {"type": "选三实战", "pick3": nums[:3]}
        # 管家
        elif "管家" in line:
            nums = [int(x) for x in re.findall(r'\b\d{1,2}\b', line) if 1 <= int(x) <= 80]
            if nums:
                result["experts"]["管家"] = {"type": "同尾特色6码", "pick6": nums[:6]}

    return {"status": "success", "parsed": result}
