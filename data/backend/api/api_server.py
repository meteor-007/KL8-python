# -*- coding: utf-8 -*-
"""
K8-Quant Web Application FastAPI Server
现代化量化大屏后端 RESTful API 服务 (Modular Backend API)

Slim shell: app creation, middleware, static mounts, auth/login, and router includes.
Route handlers live in backend/modules/*/routes.py and backend/api/routes_*.py.
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import hmac
import secrets
import logging
import threading
from datetime import datetime

logger = logging.getLogger("k8quant.api")

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.utils.paths import get_project_root, get_frontend_dir, _ensure_project_path
_ensure_project_path()

from backend.api.deps import (  # noqa: F401 — re-export for callers/tests
    PROJ_DIR,
    data_service,
    TASK_STORE,
    find_script,
    run_script_task,
    run_points_downstream_task,
    ParamUpdateModel,
    DailyPointsSubmitModel,
)
from backend.api.ai_router import router as ai_router, GeminiQuantAdvisor
import backend.api.ai_router as ai_module

# 可选：从项目根目录 .env 读取配置（如 WEB_PASSCODE / WEB_SESSION_SECRET）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJ_DIR, ".env"))
except Exception:
    pass

app = FastAPI(
    title="K8-Quant 智能量化决策终端 API",
    description="快乐8 极致暗黑赛博量化大屏后端 API 服务，支持全流程预测、80码全景矩阵、历史复盘与任务流式调度",
    version="5.1.0"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启用 gzip 压缩，减小大屏(大 HTML/JS)传输体积，提升手机端加载速度
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 注入数据服务单例给 AI 操盘大脑
ai_module.advisor_instance = GeminiQuantAdvisor(data_service=data_service)
app.include_router(ai_router)

# ── Modular route routers ──
from backend.api.routes_ops import router as ops_router
from backend.api.routes_quant import router as quant_router
from backend.api.routes_pipeline import router as pipeline_router

from backend.modules.legacy.genetic_algorithm.routes import router as genetic_router
from backend.modules.legacy.gold_pick2.routes import router as gold_pick2_router
from backend.modules.sixteen.routes import router as sixteen_router
from backend.modules.formula_jingle.routes import router as jingle_router
from backend.modules.point_suppression.routes import router as suppression_router
from backend.modules.datasource.routes import router as datasource_router
from backend.modules.legacy.point_omission.routes import router as point_omission_router
from backend.modules.aggregation.routes import router as aggregation_router
from backend.modules.tri_high.routes import router as tri_high_router
from backend.modules.legacy.unified_brain.routes import router as unified_brain_router
from backend.modules.master_review.routes import router as master_review_router
from backend.modules.legacy.linear_algebra.routes import router as linear_algebra_router
from backend.modules.legacy.random_forest.routes import router as random_forest_router
from backend.modules.legacy.dtw_matching.routes import router as dtw_router
from backend.modules.legacy.transformer_attention.routes import router as transformer_router
from backend.modules.legacy.matrix_profile.routes import router as matrix_profile_router
from backend.modules.legacy.tda_engine.routes import router as tda_router
from backend.modules.markov_line.routes import router as markov_line_router
from backend.modules.error_correction.routes import router as error_correction_router
from backend.modules.spear_shield_portfolio.routes import router as spear_shield_router
from backend.modules.point_road_compressor.routes import router as point_road_router

from backend.modules.legacy.models.lstm.routes import router as lstm_router
from backend.modules.legacy.gemini_pick2.routes import router as gemini_router
from backend.modules.legacy.follow.routes import router as follow_router
from backend.modules.legacy.spatial_points.routes import router as spatial_points_router

app.include_router(ops_router)
app.include_router(quant_router)
app.include_router(pipeline_router)
app.include_router(genetic_router)
app.include_router(gold_pick2_router)
app.include_router(sixteen_router)
app.include_router(jingle_router)
app.include_router(suppression_router)
app.include_router(datasource_router)
app.include_router(point_omission_router)
app.include_router(aggregation_router)
app.include_router(tri_high_router)
app.include_router(unified_brain_router)
app.include_router(master_review_router)
app.include_router(linear_algebra_router)
app.include_router(random_forest_router)
app.include_router(error_correction_router)
app.include_router(spear_shield_router)
app.include_router(point_road_router)
app.include_router(dtw_router)
app.include_router(transformer_router)
app.include_router(matrix_profile_router)
app.include_router(tda_router)
app.include_router(markov_line_router)
app.include_router(lstm_router)
app.include_router(gemini_router)
app.include_router(follow_router)
app.include_router(spatial_points_router)


# 启动后台 22:00 定时调度线程
try:
    from backend.scheduler.nightly_scheduler import scheduler_instance
    scheduler_instance.start()
except Exception as _e:
    print(f"⚠️ 启动夜间定时调度器失败: {_e}")


# 挂载前端静态文件 (优先从 frontend/static 寻找)
STATIC_DIR = os.path.join(get_frontend_dir(), "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(PROJ_DIR, "web_app", "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _verify_frontend_build() -> None:
    """组装 modules/**/view.html -> index.html, 并校验生成物不比源文件旧。

    源目录与产物不一致时只告警不阻断启动 (Web 仍可用), 但绝不能静默。
    """
    modules_dir = os.path.join(STATIC_DIR, "modules")
    layout_dir = os.path.join(STATIC_DIR, "layout")
    index_file = os.path.join(STATIC_DIR, "index.html")

    try:
        from scripts.build_web import build_index_html
        build_index_html()
    except Exception as _e:
        logger.error(
            "❌ 前端视图组装失败 (modules/**/view.html -> index.html): %s: %s —— "
            "页面将继续提供上一次成功生成的 index.html, 可能已过期。",
            type(_e).__name__, _e, exc_info=True,
        )
        return

    try:
        if not os.path.exists(index_file):
            logger.error("❌ index.html 未生成 (预期路径 %s)", index_file)
            return
        index_mtime = os.path.getmtime(index_file)
        newer = []
        for _d in (modules_dir, layout_dir):
            if not os.path.isdir(_d):
                continue
            for _root, _dirs, _files in os.walk(_d):
                for _fn in _files:
                    if not _fn.endswith(".html"):
                        continue
                    _p = os.path.join(_root, _fn)
                    if os.path.getmtime(_p) > index_mtime + 1:
                        newer.append(os.path.relpath(_p, STATIC_DIR))
        if newer:
            logger.warning(
                "⚠️ index.html 比 %d 个源视图旧, 页面内容可能不是最新的: %s",
                len(newer), ", ".join(sorted(newer)[:8]),
            )
        else:
            logger.info("✅ 前端视图组装完成, index.html 与源文件一致")
    except Exception as _e:
        logger.warning("前端陈旧性校验跳过 (%s: %s)", type(_e).__name__, _e)


_verify_frontend_build()


@app.get("/")
def serve_index():
    """提供 Web 端应用首页（禁止缓存，避免侧栏/菜单重构后仍看到旧 HTML）"""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return HTMLResponse("<h1>K8-Quant Web 正在初始化中...</h1>")


@app.get("/favicon.ico")
def get_favicon():
    from fastapi import Response
    return Response(status_code=204)


# ═══════════════════ 应用层访问鉴权（共享口令登录） ═══════════════════
WEB_PASSCODE = os.environ.get("WEB_PASSCODE", "k8quant@2026")
SESSION_SECRET = os.environ.get("WEB_SESSION_SECRET", secrets.token_hex(48))
SESSION_MAX_AGE = 7 * 24 * 3600

LOGIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<title>K8-QUANT · 访问授权</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: radial-gradient(circle at 15% 15%, rgba(6,182,212,0.16) 0%, transparent 42%),
                radial-gradient(circle at 85% 25%, rgba(245,158,11,0.12) 0%, transparent 42%),
                linear-gradient(160deg, #0b1020, #111a35 55%, #0b1020);
    color: #e2e8f0; padding: 16px;
  }
  .card {
    width: 100%; max-width: 400px; padding: 30px 26px; border-radius: 16px;
    background: rgba(17, 25, 40, 0.72); border: 1px solid rgba(56,189,248,0.28);
    box-shadow: 0 0 55px rgba(6,182,212,0.16), inset 0 1px 0 rgba(255,255,255,0.05);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  }
  .logo { font-size: 22px; font-weight: 800; letter-spacing: 0.02em; background: linear-gradient(90deg,#22d3ee,#f59e0b,#c084fc); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .sub { font-size: 12px; color: #94a3b8; margin: 6px 0 22px; letter-spacing: 0.06em; }
  label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
  input {
    width: 100%; padding: 12px 14px; border-radius: 10px; font-size: 16px; -webkit-text-size-adjust: 100%;
    color: #fff; background: rgba(15,23,42,0.7); border: 1px solid rgba(56,189,248,0.24);
    outline: none; transition: border-color .2s, box-shadow .2s;
  }
  input:focus { border-color: #22d3ee; box-shadow: 0 0 0 3px rgba(34,211,238,0.18); }
  button {
    width: 100%; margin-top: 16px; padding: 13px; border-radius: 10px; border: 0; cursor: pointer;
    font-size: 15px; font-weight: 700; color: #06121f;
    background: linear-gradient(90deg,#22d3ee,#38bdf8); box-shadow: 0 8px 24px rgba(34,211,238,0.28);
    transition: transform .1s, box-shadow .2s;
  }
  button:active { transform: scale(0.98); }
  .login-err { margin-top: 14px; padding: 10px 12px; border-radius: 8px; font-size: 13px; background: rgba(244,63,94,0.12); border: 1px solid rgba(244,63,94,0.32); color: #fda4af; }
  .tip { margin-top: 14px; font-size: 11px; color: #64748b; text-align: center; }
</style>
</head>
<body>
  <div class="card">
    <div class="logo">🧬 K8-QUANT</div>
    <div class="sub">智能量化操盘决策终端 · 访问授权</div>
    <form method="post" action="/login" autocomplete="off">
      <label for="passcode">访问口令</label>
      <input type="password" id="passcode" name="passcode" placeholder="请输入共享口令" autofocus required>
      <button type="submit">🔓 进入系统</button>
    </form>
    {errmsg}
    <div class="tip">授权访问 · 仅对信任对象开放</div>
  </div>
</body>
</html>"""

LOGIN_HTML = LOGIN_TEMPLATE.replace("{errmsg}", "")
LOGIN_HTML_ERROR = LOGIN_TEMPLATE.replace(
    "{errmsg}", '<div class="login-err">口令不正确，请重试</div>'
)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(LOGIN_HTML)


@app.post("/login")
def do_login(request: Request, passcode: str = Form(...)):
    if hmac.compare_digest(passcode, WEB_PASSCODE):
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(LOGIN_HTML_ERROR, status_code=401)


@app.get("/logout")
def do_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.middleware("http")
async def auth_guard(request, call_next):
    """保护首页与所有 /api 接口，未登录时跳转登录页或返回 401。"""
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    protected = (
        path == "/"
        or path.startswith("/api/")
        or path in ("/docs", "/redoc", "/openapi.json")
    )
    if not protected:
        return await call_next(request)

    # 1. 会话已认证
    if request.session.get("authenticated"):
        return await call_next(request)

    # 2. 支持 Bearer Token / API Key
    auth_header = request.headers.get("Authorization", "") or request.headers.get("authorization", "")
    api_key = request.headers.get("X-API-Key", "") or request.headers.get("x-api-key", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if hmac.compare_digest(token, WEB_PASSCODE):
            return await call_next(request)
    if api_key and hmac.compare_digest(api_key, WEB_PASSCODE):
        return await call_next(request)

    # 3. 单元测试/CI 环境免拦截
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING") == "1":
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse({"detail": "未授权，请先登录"}, status_code=401)
    if path == "/":
        return HTMLResponse(LOGIN_HTML)
    return RedirectResponse("/login", status_code=302)


# 会话中间件必须最后注册（最外层），保证上面守卫能读到 request.session
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=False,
)


def _warm_caches():
    try:
        _t0 = time.time()
        data_service.get_hit_leaderboard(n=10)
        print(f"🔥 启动预热完成，hit-leaderboard 缓存已就绪 ({time.time() - _t0:.1f}s)")
    except Exception as _e:
        print(f"⚠️ 启动预热失败(不影响服务): {_e}")


def _nightly_watchdog_scan():
    """启动时做一次夜间看门狗扫描 (2026-10-22 告警闭环)。

    为什么放在 Web 服务里: 本次真实事故是「计划任务根本没能启动」——
    那种情况下进程内的失败告警是发不出来的 (进程压根没跑起来)。
    只要 Web 服务还活着, 这条路径就能发现"夜间已停摆"并告警。
    与计划任务内的即时告警互补, 互不依赖。

    2026-10-22 补充：Web 服务以 Windows 服务方式托管，stdout 不落盘，
    导致"看门狗到底跑没跑"无从查证。现同时写一份到 storage/logs/watchdog.log。
    """
    _log_line = ""
    try:
        from backend.utils.nightly_watchdog import run_watchdog
        diag = run_watchdog(notify=True)
        if diag.get("healthy"):
            _log_line = (f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ✅ 健康 "
                         f"(最近成功 {diag.get('last_finished_at') or '—'})")
        else:
            _log_line = (f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 🚨 异常 — "
                         f"{'; '.join(diag.get('problems') or [])}")
        print(_log_line.split('] ', 1)[-1])
    except Exception as _e:
        _log_line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚠️ 看门狗扫描失败: {_e}"
        print(f"⚠️ 夜间看门狗扫描失败(不影响服务): {_e}")
    finally:
        try:
            _log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "storage", "logs")
            os.makedirs(_log_dir, exist_ok=True)
            with open(os.path.join(_log_dir, "watchdog.log"), "a", encoding="utf-8") as _f:
                _f.write(_log_line + "\n")
        except Exception:
            pass


if os.environ.get("WEB_SKIP_WARMUP") != "1":
    threading.Thread(target=_warm_caches, daemon=True).start()

if os.environ.get("WEB_SKIP_WATCHDOG") != "1":
    threading.Thread(target=_nightly_watchdog_scan, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.api_server:app", host="127.0.0.1", port=8000, reload=True)
