# phase3 验证证据 · 2026-11-11

## 1. 静态引用完整性
命令（cwd = `data/frontend/static`）：
```
grep -oE 'src="[^"]*\.js[^"]*"' index.html | sed 's/src="//; s/?[^"]*"//; s/"$//' | sort -u \
 | while read -r p; do rel="${p#/static/}"; [ -f "$rel" ] || echo "MISSING: $p"; done
```
修复前输出：7 个 MISSING（genetic / gold_pick2 / linear_algebra / point_omission /
psychological_game / random_forest / unified_brain）
修复后输出：空 —— 全部脚本引用均可解析

## 2. JS 语法检查
命令（cwd = `data/frontend/static/js`）：`node --check pages/*.js app.js k8_pages.js`
结果：exit 0，无输出

## 3. 绑定合并仿真（Node + vm 沙箱）
加载 `k8_pages.js` + `menu_registry.js` + 全部 `pages/*.js`，执行 `K8Pages.apply(vueApi, ctx)`，
再与 `app.js` 中 `const { ... } = __k8PageBindings;` 的解构清单逐项比对。

```
注册模块数: 23
合并出的绑定数: 315
app.js 解构绑定: 307
缺失: 0 (无)
```
关键函数抽查全部为 function：
fetchUnifiedBrain / triggerUnifiedBrainRun / triggerPsychologicalGameRun / triggerPrimeCompositeRun /
triggerLinearAlgebraRun / triggerRandomForestRun / triggerDTWRun / triggerTransformerRun /
triggerMatrixProfileRun / triggerTDARun / fetchPointOmissionSummary / triggerPointOmissionRun /
fetchGoldPick2Summary / triggerGoldPick2Run

> 说明：修复前 `fetchUnifiedBrain`、`triggerUnifiedBrainRun`、`triggerPsychologicalGameRun`、
> `triggerLinearAlgebraRun`、`triggerRandomForestRun`、`triggerPrimeCompositeRun` 在 app.js 中定义数为 0，
> 且仅存在于 `_retired/` 下，直接导致 `TypeError: fetchUnifiedBrain is not a function`。

## 4. 视图组装
命令（cwd = `data`）：`python -c "from scripts.build_web import build_index_html; build_index_html()"`
修复前：`⚠️ 缺失子视图文件: hub_core/unified_brain/view.html` 等 7 条告警，36 个视图
修复后：`🚀 Web 视图组装完成: 包含 43 个模块化视图, 总行数 12761 行, 体积 795.9 KB` —— 零告警

## 5. 实际服务端 HTTP 校验（服务运行于 127.0.0.1:8000）
```
unified_brain.js     200
psychological_game.js 200
linear_algebra.js    200
random_forest.js     200
genetic.js           200
gold_pick2.js        200
point_omission.js    200
dtw.js               200
transformer.js       200
matrix_profile.js    200
tda.js               200
```
`GET /static/index.html` → 200，脚本引用含全部 23 个 pages 模块（含新增 dtw/transformer/matrix_profile/tda）。

## 结论
G3（策略 B）达成。未做浏览器可视化验证：本机 Browser 预览未启用，改以
「静态引用 + 语法检查 + 绑定合并仿真 + 真实 HTTP 状态 + 视图组装产物」五重证据替代。
建议用户强制刷新（Ctrl+F5）后确认控制台无报错。