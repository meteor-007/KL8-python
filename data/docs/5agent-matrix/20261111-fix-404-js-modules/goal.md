# goal.md · 修复前端页面模块 404 与 fetchUnifiedBrain 未定义

## 需求一句话
浏览器控制台报 6 个 404（unified_brain / psychological_game / linear_algebra / random_forest / genetic 等）与
`TypeError: fetchUnifiedBrain is not a function`，首屏核心数据加载失败，请修复。

## R0 工程就绪体检（R0-lite）
| 项 | 结论 | 说明 |
|---|---|---|
| R1 构建可复现 | 通过 | 前端为 CDN Vue3 无打包，`scripts/build_web.py::build_index_html()` 组装 `modules/**/view.html` → `index.html` |
| R2 测试基建 | 降级接受 | 仓库无前端单测；本需求采用**策略 B**（构建成功 + 手工/脚本联调留痕） |
| R5 验收标准 | 通过 | 全部脚本引用可 200、页面可挂载无 TypeError、7 个功能页视图重新拼入 index.html |

## 根因
提交 `652ecf9` 把 11 个 `js/pages/*.js` 模块和 11 个 `modules/*/view.html` 移入 `_retired/`，
但以下消费方未同步，形成"半退役"：

1. `frontend/static/index.html` — 仍按 `/static/js/pages/<name>.js` 引用 7 个文件 → 404
2. `frontend/static/js/app.js` — 仍从 `__k8PageBindings` 解构这些模块提供的 307 个绑定；
   `fetchUnifiedBrain` 全仓库仅在 `_retired/unified_brain.js` 有定义 → `is not a function`
3. `scripts/build_web.py::ORDERED_VIEWS` — 仍列出 7 个 `hub_*/<name>/view.html`，文件却已移至 `modules/_retired/` → 构建告警且功能页视图缺失

## G1–G5 达成
| Goal | 结论 | 证据 |
|---|---|---|
| G1 需求契约保真 | 达成 | 控制台 6 条 404 全消除；TypeError 消除 |
| G2 权限与数据脚本伴随 | N/A | 纯前端静态资源归位，无表/数据变更，无 ACL 体系 |
| G3 编译与验证绿灯（策略 B） | 达成 | `evidence/phase3-verify-20261111.md` |
| G4 工业质检达标 | 达成 | 仅 `git mv` 归位 + 生成器补 4 行脚本引用，无新增逻辑 |
| G5 发布就绪 | 达成 | 见下「变更清单」 |

## 变更清单
- 11 个 `js/pages/_retired/*.js` → `frontend/static/js/pages/`（恢复原路径）
- 7 个 `modules/_retired/*/view.html` → `modules/hub_core|hub_engine/<name>/view.html`
- `scripts/build_web.py`：补 dtw / transformer / matrix_profile / tda 四个 script 引用
  （这 4 个触发器 `triggerDTWRun` 等仍被 app.js 解构，但视图与菜单为既有退役状态，不在 ORDERED_VIEWS）
- 重新生成 `frontend/static/index.html`（43 个视图，v_tag 自动刷新为 20261111_172157，天然打破缓存）

## 自愈上限
默认 6 轮，本次 0 轮返工。