# Skills 能力清单（当前环境快照）

本清单用于回答“当前内置了哪些能力（skills）”以及“什么时候该用/不该用”。

## 1. 使用说明

- 本文档是“当前环境快照”，不是永久固定名单。
- 环境变化后（安装/卸载 skill）请手动刷新本文件。
- 使用原则：优先选“最小必要 skill 组合”，避免堆叠导致上下文噪音。

## 2. 能力分类（高频）

### 2.1 数据分析与工程

- `kl8-analysis`
- `spreadsheet`
- `jupyter-notebook`
- `pdf`

### 2.2 前端与设计实现

- `frontend-skill`
- `figma`
- `figma-implement-design`
- `figma-generate-design`
- `figma-use`
- `figma-code-connect-components`
- `figma-generate-library`
- `figma-create-design-system-rules`
- `figma-create-new-file`

### 2.3 Web 自动化与验证

- `playwright`
- `playwright-interactive`
- `screenshot`

### 2.4 部署与交付

- `cloudflare-deploy`
- `netlify-deploy`
- `render-deploy`
- `vercel-deploy`

### 2.5 文档与内容生产

- `doc`
- `slides`
- `imagegen`
- `speech`
- `transcribe`
- `sora`

### 2.6 平台协作与任务系统

- `linear`
- `notion-knowledge-capture`
- `notion-meeting-intelligence`
- `notion-research-documentation`
- `notion-spec-to-implementation`
- `sentry`

### 2.7 GitHub 与工程协作

- `gh-address-comments`
- `gh-fix-ci`
- `yeet`

### 2.8 架构与安全专项

- `security-best-practices`
- `security-ownership-map`
- `security-threat-model`
- `aspnet-core`
- `winui-app`
- `chatgpt-apps`
- `develop-web-game`

### 2.9 系统技能（OpenAI / Skill 生态）

- `openai-docs`
- `skill-creator`
- `skill-installer`

## 3. 何时不用 Skill

- 纯小改动（单文件、低复杂度）优先直接实现。
- 需求已明确且上下文很小，不必额外引入重流程 skill。
- 若 skill 引导与项目现状冲突，优先项目实际约束。

## 4. 多 Skill 组合建议

- 设计到代码：`figma` -> `figma-implement-design` -> `frontend-skill`
- UI 自动验收：`frontend-skill` -> `playwright`
- 数据报告链路：`kl8-analysis` -> `spreadsheet` -> `doc` 或 `slides`
- PR 闭环：`gh-fix-ci` -> `gh-address-comments` -> `yeet`

## 5. 典型输入模板

```text
需求：
目标页面：
数据来源：
约束：
验收标准：
是否需要自动化验证：
```

## 6. 刷新机制

- 触发条件：新增/删除 skills，或开发环境迁移。
- 刷新动作：更新分类、组合建议、典型输入模板。
- 建议频率：每两周或每个里程碑手动校对一次。

