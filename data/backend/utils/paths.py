# -*- coding: utf-8 -*-
"""
路径中枢工具模块 (Unified Paths Resolver)
统一解析系统根目录、后端模块、前端静态资源与持久化数据存储路径。
自动向上回溯定位项目根目录，避免子目录中 __file__ 引用指向错误位置。

v5.4: 活数据统一落在 storage/{cache,outputs,reports,reviews,...}；
根目录同名路径仅作只读兼容回退。
"""
import os
import sys

_PROJECT_ROOT_CACHE = None


def get_project_root():
    """获取项目根目录 (即 data/ 目录)"""
    global _PROJECT_ROOT_CACHE
    if _PROJECT_ROOT_CACHE is not None:
        return _PROJECT_ROOT_CACHE

    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        # 项目根目录 data/ 必须同时包含 backend 以及 (storage 或 frontend 或 GEMINI.md)
        if os.path.exists(os.path.join(curr, 'backend')) and \
           (os.path.exists(os.path.join(curr, 'storage')) or \
            os.path.exists(os.path.join(curr, 'frontend')) or \
            os.path.exists(os.path.join(curr, 'GEMINI.md'))):
            if os.path.basename(curr) != 'backend':
                _PROJECT_ROOT_CACHE = curr
                return _PROJECT_ROOT_CACHE
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    file_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(os.path.dirname(file_dir)) == 'backend':
        _PROJECT_ROOT_CACHE = os.path.dirname(os.path.dirname(file_dir))
    else:
        _PROJECT_ROOT_CACHE = os.path.dirname(file_dir)
    return _PROJECT_ROOT_CACHE


def get_backend_dir():
    """获取后端模块根目录 (data/backend/)"""
    return os.path.join(get_project_root(), "backend")


def get_modules_dir():
    """获取按菜单划分的业务模块根目录 (data/backend/modules/)"""
    return os.path.join(get_backend_dir(), "modules")


def get_frontend_dir():
    """获取前端模块根目录 (data/frontend/)"""
    return os.path.join(get_project_root(), "frontend")


def get_storage_dir():
    """获取活数据持久化根目录 (data/storage/)。

    不再优先 archive/storage_legacy（避免读到陈旧副本）；
    legacy 仅在 data_path 单文件回退时使用。
    """
    return os.path.join(get_project_root(), "storage")


def get_storage_legacy_dir():
    return os.path.join(get_project_root(), "archive", "storage_legacy")


def get_cache_dir():
    """运行期缓存目录: storage/cache"""
    p = os.path.join(get_storage_dir(), "cache")
    os.makedirs(p, exist_ok=True)
    return p


def get_outputs_dir():
    """流水线产出目录: storage/outputs"""
    p = os.path.join(get_storage_dir(), "outputs")
    os.makedirs(p, exist_ok=True)
    return p


def get_reports_dir():
    """研报目录: storage/reports"""
    p = os.path.join(get_storage_dir(), "reports")
    os.makedirs(p, exist_ok=True)
    return p


def get_reviews_dir():
    """复盘 JSON 目录: storage/reviews"""
    p = os.path.join(get_storage_dir(), "reviews")
    os.makedirs(p, exist_ok=True)
    return p


def storage_path(*subpaths):
    """拼接 storage/ 下路径；若传入 cache/outputs/reports/reviews 前缀则确保父目录存在。"""
    base = get_storage_dir()
    path = os.path.join(base, *subpaths) if subpaths else base
    parent = path if (subpaths and not os.path.splitext(path)[1]) else os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path


def resolve_runtime_dir(name: str) -> str:
    """解析 cache|outputs|reports|reviews|output 到 storage 下的标准目录。

    兼容旧写法 join(proj, 'cache')：调用方应改为本函数或 get_*_dir()。
    """
    key = (name or "").strip().lower().replace("\\", "/").strip("/")
    mapping = {
        "cache": get_cache_dir,
        "outputs": get_outputs_dir,
        "output": get_outputs_dir,
        "reports": get_reports_dir,
        "reviews": get_reviews_dir,
    }
    if key in mapping:
        return mapping[key]()
    # 其它名字落到 storage/<name>
    p = os.path.join(get_storage_dir(), key)
    os.makedirs(p, exist_ok=True)
    return p


def proj_join(*parts):
    """智能 join：若首段是 cache/outputs/reports/reviews/output，自动改写到 storage/。

    用法替代 os.path.join(PROJ_DIR, "cache", ...)
    """
    if not parts:
        return get_project_root()
    head = str(parts[0]).replace("\\", "/").strip("/")
    top = head.split("/")[0].lower()
    if top in ("cache", "outputs", "output", "reports", "reviews"):
        rest = list(parts[1:])
        if "/" in head:
            rest = head.split("/")[1:] + rest
        return os.path.join(resolve_runtime_dir(top), *rest)
    return os.path.join(get_project_root(), *parts)


def get_python_runner() -> str:
    """获取真正的 python.exe 执行器，防止在 Windows Service 环境下被识别为 pythonservice.exe"""
    exe = sys.executable
    if "pythonservice" in os.path.basename(exe).lower():
        dir_name = os.path.dirname(exe)
        python_exe = os.path.join(dir_name, "python.exe")
        if os.path.exists(python_exe):
            return python_exe
    return exe


def get_config_dir():
    """获取配置模块根目录 (data/backend/config/ 或 data/config/)"""
    backend_cfg = os.path.join(get_backend_dir(), "config")
    if os.path.exists(backend_cfg):
        return backend_cfg
    return os.path.join(get_project_root(), "config")


def _ensure_project_path():
    """确保项目根、backend、modules、scripts 在 sys.path 中。

    modules 入 path 后可 `import point_omission` 等包
    （实体位于 backend/modules/），无需根目录 shim。
    scripts 入 path 后可 `from daily_run_guard import ...`。
    """
    root = get_project_root()
    backend_dir = get_backend_dir()
    modules_dir = get_modules_dir()
    retired_dir = os.path.join(modules_dir, "legacy")
    scripts_dir = os.path.join(root, "scripts")
    for p in [root, backend_dir, modules_dir, retired_dir, scripts_dir]:
        if p not in sys.path:
            sys.path.insert(0, p)


def get_raw_dir():
    """原始数据目录: storage/raw（历史开奖、点位、Excel 等）"""
    p = os.path.join(get_storage_dir(), "raw")
    os.makedirs(p, exist_ok=True)
    return p


def get_stats_dir():
    p = os.path.join(get_storage_dir(), "stats")
    os.makedirs(p, exist_ok=True)
    return p


def get_logs_dir():
    p = os.path.join(get_storage_dir(), "logs")
    os.makedirs(p, exist_ok=True)
    return p


def data_path(*subpaths):
    """
    智能解析数据文件路径：
    优先顺序：
    1. storage/ 下标准活数据 (含 raw/stats/cache/outputs/reports/reviews)
    2. 单文件名自动在 storage/raw|stats|cache 中查找（兼容旧根目录数据文件）
    3. 相对于 data/ 根目录
    4. 兼容历史 archive 映射与 storage_legacy
    5. backend/config
    6. 兜底写入 storage（cache/outputs/...）或 storage/raw（未知单文件）
    """
    root = get_project_root()
    storage = get_storage_dir()

    if not subpaths:
        return root

    # 活数据优先：storage/<subpaths>
    storage_direct = os.path.join(storage, *subpaths)
    if os.path.exists(storage_direct):
        return storage_direct

    # 兼容 join 风格：首段已是 cache/outputs/...
    top = str(subpaths[0]).replace("\\", "/").split("/")[0].lower()
    if top in ("cache", "outputs", "output", "reports", "reviews", "raw", "stats", "logs"):
        mapped = proj_join(*subpaths) if top in ("cache", "outputs", "output", "reports", "reviews") else os.path.join(storage, *subpaths)
        if top in ("raw", "stats", "logs"):
            mapped = os.path.join(storage, *subpaths)
        if os.path.exists(mapped):
            return mapped

    # 单段文件名：在 raw / stats / cache 中搜索（历史根目录散落文件归位后）
    if len(subpaths) == 1 and not str(subpaths[0]).replace("\\", "/").startswith(("storage/", "backend/")):
        name = subpaths[0]
        for folder in ("raw", "stats", "cache", "reports", "logs"):
            cand = os.path.join(storage, folder, name)
            latest = cand + ".latest"
            # 若正式文件被占用/过期，优先返回更新的 .latest 兜底
            if os.path.exists(latest) and os.path.exists(cand):
                try:
                    if os.path.getmtime(latest) >= os.path.getmtime(cand):
                        return latest
                except OSError:
                    pass
            if os.path.exists(cand):
                return cand
            if os.path.exists(latest):
                return latest

    direct_path = os.path.join(root, *subpaths)
    if os.path.exists(direct_path):
        return direct_path

    if subpaths and subpaths[0] in ('热码统计', 'historical_stats'):
        hist_stats = os.path.join(root, "archive", "historical_stats", *subpaths[1:])
        if os.path.exists(hist_stats):
            return hist_stats

    if subpaths and subpaths[0] == 'backup':
        backup_p = os.path.join(root, "archive", "backup", *subpaths[1:])
        if os.path.exists(backup_p):
            return backup_p

    if subpaths and subpaths[0] == 'scratch':
        scratch_p = os.path.join(root, "archive", "scratch", *subpaths[1:])
        if os.path.exists(scratch_p):
            return scratch_p

    archive_path = os.path.join(root, "archive", *subpaths)
    if os.path.exists(archive_path):
        return archive_path

    legacy = get_storage_legacy_dir()
    if os.path.isdir(legacy):
        legacy_path = os.path.join(legacy, *subpaths)
        if os.path.exists(legacy_path):
            return legacy_path
        legacy_raw = os.path.join(legacy, "raw", *subpaths)
        if os.path.exists(legacy_raw):
            return legacy_raw

    cfg_path = os.path.join(get_config_dir(), *subpaths)
    if os.path.exists(cfg_path):
        return cfg_path

    if subpaths and subpaths[0] in ('热码统计', 'historical_stats'):
        return os.path.join(root, 'archive', 'historical_stats', *subpaths[1:])

    # 新建文件：cache/outputs/reports/reviews 写入 storage
    if top in ("cache", "outputs", "output", "reports", "reviews"):
        return proj_join(*subpaths)

    # 单文件默认落到 storage/raw（便于新建点位/历史类资产）
    if len(subpaths) == 1 and "." in str(subpaths[0]):
        return os.path.join(get_raw_dir(), subpaths[0])

    return storage_direct if top not in ("",) else direct_path


def script_path(module_name):
    """拼接同级或 backend 目录下脚本路径 (优先委托 find_module_script 寻址)"""
    try:
        cand_mod = find_module_script(module_name)
        if cand_mod and os.path.exists(cand_mod):
            return cand_mod
    except Exception:
        pass

    caller_dir = os.path.dirname(os.path.abspath(
        __import__('sys')._getframe(1).f_globals.get('__file__', __file__)
    ))
    candidates = [
        os.path.join(caller_dir, module_name),
        os.path.join(os.path.dirname(caller_dir), module_name),
        os.path.join(get_backend_dir(), module_name),
        os.path.join(get_modules_dir(), module_name),
        os.path.join(get_project_root(), module_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(caller_dir, module_name)


def find_module_script(script_name: str) -> str:
    """按 run_*_daily.py 或逻辑名定位 modules 内 run_daily.py。"""
    root = get_project_root()
    modules = get_modules_dir()

    SCRIPT_MAP = {
        "run_pick2_daily.py": "legacy/gold_pick2/run_daily.py",
        "run_sixteen_daily.py": "sixteen/run_daily.py",
        "run_jingle_daily.py": "formula_jingle/run_daily.py",
        "run_suppression_daily.py": "point_suppression/run_daily.py",
        "run_aggregation_daily.py": "aggregation/run_daily.py",
        "run_unified_brain_daily.py": "legacy/unified_brain/run_daily.py",
        "run_evolution_daily.py": "legacy/unified_brain/run_evolution_daily.py",
        "run_datasource_daily.py": "datasource/run_daily.py",
        "run_psychological_game_daily.py": "legacy/psychological_game/run_daily.py",
        "run_prime_composite_daily.py": "prime_composite/run_daily.py",
        "run_master_review_daily.py": "master_review/run_daily.py",
        "run_multi_resonance_daily.py": "multi_resonance/run_daily.py",
        "run_point_omission_daily.py": "legacy/point_omission/run_daily.py",
        "run_omission_daily.py": "legacy/point_omission/run_daily.py",
        "run_kl8_lab_daily.py": "kl8_lab/run_daily.py",
        "run_tri_high_daily.py": "tri_high/tri_high_engine.py",
        "run_error_correction_daily.py": "error_correction/run_daily.py",
        "run_random_forest_daily.py": "legacy/random_forest/run_daily.py",
        "run_dtw_daily.py": "legacy/dtw_matching/run_daily.py",
        "run_tda_daily.py": "legacy/tda_engine/run_daily.py",
        "run_matrix_profile_daily.py": "legacy/matrix_profile/run_daily.py",
        "run_transformer_daily.py": "legacy/transformer_attention/run_daily.py",
        "run_linear_algebra_daily.py": "legacy/linear_algebra/run_daily.py",
        "run_genetic_daily.py": "legacy/genetic_algorithm/run_daily.py",
        "run_unified_audit_daily.py": "unified_audit/run_daily.py",
        "run_follow_daily.py": "legacy/follow/run_daily.py",
        "run_lstm_daily.py": "legacy/models/lstm/run_daily.py",
        "run_geminixuan2_daily.py": "legacy/gemini_pick2/run_daily.py",
        "run_points_daily.py": "legacy/spatial_points/run_daily.py",
        "run_compressor_daily.py": "point_road_compressor/run_daily.py",
        "run_point_road_compressor_daily.py": "point_road_compressor/run_daily.py",
        "run_golden_split.py": "golden_split/run_split.py",
        "run_nightly_daily.py": None,  # special: pipeline
        "run_full_pipeline.py": None,
    }

    base = os.path.basename(script_name)
    mapped = SCRIPT_MAP.get(base)
    candidates = []
    if mapped:
        candidates.append(os.path.join(modules, mapped.replace("/", os.sep)))
    # Prefer backend/pipeline and backend paths; root shims are legacy fallback only.
    candidates.extend([
        os.path.join(get_backend_dir(), "pipeline", base),
        os.path.join(root, "backend", script_name),
        os.path.join(root, "backend", base),
        os.path.join(root, script_name),
        os.path.join(root, base),
    ])
    if base == "run_nightly_daily.py":
        candidates.insert(0, os.path.join(get_backend_dir(), "pipeline", "run_nightly_pipeline.py"))
        candidates.insert(0, os.path.join(get_backend_dir(), "pipeline", "run_nightly_daily.py"))
    if base == "run_full_pipeline.py":
        candidates.insert(0, os.path.join(get_backend_dir(), "pipeline", "run_full_pipeline.py"))

    for c in candidates:
        if c and os.path.exists(c):
            return c
    return os.path.join(get_backend_dir(), "pipeline", base) if base in (
        "run_full_pipeline.py", "run_nightly_daily.py",
    ) else os.path.join(modules, base)


# 模块导入时自动确保 sys.path
_ensure_project_path()

if __name__ == '__main__':
    print(f"Project root : {get_project_root()}")
    print(f"Backend dir  : {get_backend_dir()}")
    print(f"Modules dir  : {get_modules_dir()}")
    print(f"Frontend dir : {get_frontend_dir()}")
    print(f"Storage dir  : {get_storage_dir()}")
    print(f"Cache dir    : {get_cache_dir()}")
    print(f"Outputs dir  : {get_outputs_dir()}")
    print(f"Reports dir  : {get_reports_dir()}")
    print(f"History file : {data_path('kl8_history_final.txt')}")
