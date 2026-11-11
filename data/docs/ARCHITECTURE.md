# K8-QUANT 系统目录架构与模块设计总纲

> **版本**：v5.5 Directory Cleanup (P0–P3)  
> **根目录**：`C:\D-pan\Dpanqianyi\Python-Project\data`  
> **设计理念**：前后端按菜单分模块；活数据只认根 `storage/`；根目录不堆业务包与日更壳。

**模块中英文对照** → [`MODULE_INDEX.md`](MODULE_INDEX.md)  
**模块舱位说明** → [`backend/modules/README.md`](../backend/modules/README.md)

---

## 1. 总体目录全景图

```
data/
├── frontend/static/                 # Web 大屏
├── backend/
│   ├── api/                         # FastAPI
│   ├── modules/<name>/              # 扁平英文包（见 MODULE_INDEX）
│   ├── modules/_retired/            # 已退役代码
│   ├── modules/README.md            # daily / research / retired 分组
│   ├── core/  pipeline/  utils/     # 横切 + 流水线 + paths
│   └── …                            # 勿再放 storage/outputs 活数据
│
├── storage/                         # 【唯一】活数据：raw/cache/outputs/reports/…
├── scripts/                         # 正式运维脚本
│   ├── build_web.py  daily_run_guard.py  input_daily_points.py
│   ├── _rerun_predict_modules_today.py  _smoke_full_cleanup.py
│   └── ops/                         # bat/ps1/Windows 服务
├── archive/
│   └── scratch/
│       ├── migration_scripts/       # 一次性 _fix_* / _rewrite_* …
│       └── legacy_backend_data/     # 旧 backend/storage、backend/outputs
├── docs/  tests/  deploy/
├── GEMINI.md  PROJECT.md  requirements.txt
├── run_server.py  start_web.bat/.ps1
├── windows_service.py  daily_run_guard.py  input_daily_points.py
└── （根目录不再保留 run_*_daily / run_full_pipeline 业务壳）
```

---

## 2. 前端改哪里

| 改什么 | 路径 |
|:---|:---|
| HTML 视图 | `frontend/static/modules/<hub>/<menu>/view.html` |
| 菜单 Tab / 共享壳 | `frontend/static/js/app.js` |
| 某菜单的请求与页内逻辑 | `frontend/static/js/pages/<module>.js`（`K8Pages.register`） |
| 组装 | `python scripts/build_web.py` |

脚本顺序：`k8_pages.js` → `pages/*.js` → `app.js` → `ai_assistant.js`。

---

## 3. 后端改哪里

| 改什么 | 路径 |
|:---|:---|
| 算法 / 日更脚本 | `backend/modules/<name>/` + `run_daily.py` |
| HTTP 路由 | `backend/modules/<name>/routes.py`（或 `api/routes_*.py`） |
| 大屏数据装配 | `backend/modules/<name>/service.py` mixin |
| 横切门禁/进化等 | `backend/core/` |
| 触发日更 | `find_module_script("run_xxx_daily.py")` → modules 内实体 |

`backend/modules` 与 `backend/modules/_retired` 已加入 `sys.path`，因此 `import gemini_pick2` 等仍可解析（无需根目录 shim）。KillSeeker 已拆除，勿再 `import kill_seeker`。  
**不要**把包物理挪进 `modules/daily/` 子目录（会打断 import）；舱位只在文档与 `module_gate.lane` 中表达。

---

## 4. 统一路径中枢 (`paths.py`)

- `get_cache_dir()` / `get_outputs_dir()` / `get_reports_dir()` / `get_reviews_dir()` → **根** `storage/...`
- **禁止**再向 `backend/storage`、`backend/outputs` 写入（旧残留已归档）
- `data_path()` / `proj_join()`：优先根 `storage/`；`archive/storage_legacy` 仅缺文件时回退
- `find_module_script()`：逻辑名 → `backend/modules/*/run_daily.py` 或 `backend/pipeline/`

---

## 5. 常用命令

```bash
python run_server.py
python -m backend.pipeline.run_full_pipeline
python -m backend.pipeline.run_nightly_daily
python -m backend.modules.unified_brain.run_daily
python -m backend.modules.unified_brain.run_evolution_daily
python scripts/build_web.py
python -m pytest tests/
```

更多模块命令见 [`MODULE_INDEX.md`](MODULE_INDEX.md)。
