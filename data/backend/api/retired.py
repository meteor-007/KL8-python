# -*- coding: utf-8 -*-
"""退役模块的统一响应契约

放在独立模块而不是 api_server 里，是为了让 `routes_pipeline` 也能复用同一份口径 ——
否则 api_server 与 routes_pipeline 会各自决定"退役接口返回什么"，又变成多头表述。

契约：410 Gone
  404 会让调用方以为路径拼错，分不清「退役」与「写错了」；
  200 + 空数据会把退役伪装成「正常但没数据」——正是本项目一直在防的那种含糊；
  410 的语义恰好是「资源曾经存在、现已永久不可用」。
"""
from __future__ import annotations

from fastapi.responses import JSONResponse

from backend.core.module_gate import MODULE_SEED


def retired_route_response(module_id: str) -> JSONResponse:
    """退役模块的接口被调用时返回 410，并在 body 里自解释。"""
    seed = MODULE_SEED.get(module_id, {}) or {}
    decree = seed.get("decree") or {}
    return JSONResponse(
        status_code=410,
        content={
            "status": "retired",
            "module_id": module_id,
            "name": seed.get("name", module_id),
            "retired_since": decree.get("date"),
            "reason": decree.get("reason"),
            "message": (
                "该模块已退役：不再产出当期号码，也不参与 BH-FDR 校正。"
                "代码仍保留在 backend/modules/legacy/ 下，复启需修改 "
                "module_gate.MODULE_SEED 的判决，而不是改路由。"
            ),
        },
    )