# phase3 验证证据 · 首屏加载防护加固 · 2026-11-11

## 背景
排查"数据根本没更新"时定位到：`app.js` 首屏用
`await Promise.allSettled([ fetchA(), fetchB(), ... ])` 直接塞调用。
`Promise.allSettled` 的参数数组**先求值**，任一函数未定义即在构造阶段抛错，
`allSettled` 根本不会被调用，后续请求全部静默丢失。
旧代码只 `console.warn` 一句就吞掉，页面不报错、不提示 —— 静默装死。

## 对照实验（证明失效机制）
```js
await Promise.allSettled([A(), B(), C()])   // B 同步抛错
```
实测输出：
```
旧写法抛错: boom
旧写法实际执行到的: A -> C 未执行, 后续请求全部丢失
```
结论：C 及之后的所有请求从未发出。

## 改动
1. `frontend/static/js/app.js`
   - 新增通用执行器 `runLoaders(loaders)`：每项包成 thunk
     `Promise.resolve().then(item.run)`，逐个执行并收集失败项 `{label, message}`。
     定义在 908 行，所有使用点（929 / 3680 / 3784 / 3812）均在其后，无 TDZ。
   - 首屏 13 项 → `FIRST_SCREEN_LOADERS` 带标签 thunk，由 `loadFirstScreen()` 执行。
   - 后台预热 6 项 → `PREWARM_LOADERS`，同样走 `runLoaders`。
   - `fetchAllAiMathModels`（7 项）、`fetchAllClassicModels`（7 项）同样改造。
   - **成功日志改为按实际结果输出**：有失败项时打 `⚠️ ... 未能加载`，
     不再无条件打"已完成"（旧代码即使整组丢失也会报成功）。
   - 新增 `bootFailures` ref，并在 setup 返回值中暴露 `bootFailures` / `loadFirstScreen`。
2. `frontend/static/layout/header.html`
   - 新增红色横幅：显示失败项数量、逐项 `标签 —— 错误信息`、一键「重试」，
     文案明确「这是加载故障，不是数据源停更」。

## 行为测试（对真实源码执行，非复述）
从 `app.js` 抽取 `runLoaders` 真实源码（908–923 行，16 行）在 Node 中 eval 后测试
4 个 loader：A 正常 / B 同步抛错 / C 异步 reject / D 正常。

```
实际执行到的: A,C,D (期望 A,C,D)
失败项: [{"label":"B 同步抛错","message":"boom-undefined-fn"},
        {"label":"C 异步 reject","message":"http-500"}]
>>> PASS: 单项失败不再拖垮其余项
```

## 静态校验
- `node --check frontend/static/js/app.js` → exit 0
- 新名单引用的 18 个函数逐个确认有定义（app.js 或 pages 模块），零 MISSING
- `index.html` 重新组装：43 个视图 / 12778 行（较加固前 +17 行，即横幅）
- 服务端实测：`/static/index.html` 含 `bootFailures` 3 处，
  v_tag 刷新为 `20261111_184558`，`/static/js/app.js?v=20261111_184558` → 200

## 未验证项
本机 in-app Browser 预览与 playwright/puppeteer 均不可用，
未做真实浏览器渲染验证。横幅的实际视觉效果需人工确认（页面上若加载全成功则**不显示**，
这是预期行为；可临时断网或用错误 token 触发）。