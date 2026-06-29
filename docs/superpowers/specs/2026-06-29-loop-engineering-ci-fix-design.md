# Loop Engineering 实战：自动修复 CI 失败的循环

## 概述

本文档描述了一个 Loop Engineering 实战学习项目的设计，构建一个每天早上自动运行、修复前一天 CI 回归失败的循环系统。项目采用**三阶段渐进式学习路径**，本文档覆盖 Phase 1——纯 bash 实现的闭环基础。

## 核心概念

### Loop Engineering

Loop Engineering 是一种 AI 编程范式，核心思想是**设计一个能自动发现需求、分发任务、检查成果、记录状态并决定下一步行动的自循环系统**，而非手动向 AI 工具逐条输入提示词。

### 学习路径三阶段

| 阶段 | 内容 | 核心能力 |
|------|------|---------|
| Phase 1 | 纯 bash + gh CLI 实现闭环 | 循环骨架：Detect → Diagnose → Fix → Notify |
| Phase 2 | 引入 skill 体系（SKILL.md）+ 状态管理 | 知识外部化：状态在磁盘不在上下文 |
| Phase 3 | 引入子代理（ci-fixer + code-reviewer） | 多 Agent 协作 + 审查机制 |

## 技术栈

- **运行时**: Node.js + TypeScript + Vitest
- **CI 平台**: GitHub Actions
- **仓库**: 独立 GitHub 仓库
- **版本管理**: Git (完整历史，支持 bisect)
- **通知**: GitHub Issues (gh CLI)

## 整体架构

### Phase 1 循环流程

```
cron (08:00 UTC)
    │
    ▼
┌─────────────┐      ┌────────────────┐
│  DETECT     │ ───→ │  测试通过?      │
│  run test   │      │  yes → 退出     │
└─────────────┘      │  no  → 继续     │
                     └────────┬───────┘
                              │
                              ▼
┌─────────────┐      ┌────────────────┐
│  DIAGNOSE   │ ───→ │  定位回归?      │
│  git bisect │      │  yes → 继续     │
└─────────────┘      │  no  → 退出     │
                     └────────┬───────┘
                              │
                              ▼
┌─────────────┐      ┌────────────────┐
│  FIX        │ ───→ │  revert 成功?   │
│  git revert │      │  yes → push     │
└─────────────┘      │  no  → 记录     │
                     └────────┬───────┘
                              │
                              ▼
┌─────────────┐
│  NOTIFY     │
│  GitHub     │
│  Issue      │
└─────────────┘
```

## 仓库结构

```
ci-loop-lab/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # 日常 CI（push 触发）
│       └── ci-fix-loop.yml           # 🔁 修复循环（cron 触发）
├── scripts/
│   ├── inject-regression.sh          # 模拟回归（教学工具）
│   ├── run-and-collect-failures.sh   # 检测阶段：跑测试 + 收集失败
│   ├── auto-fix.sh                   # 诊断+修复：bisect → revert
│   └── notify.sh                     # 通知阶段：创建 Issue
├── src/
│   ├── math.ts                       # 示例源码
│   └── __tests__/
│       └── math.test.ts              # 示例测试
├── package.json
├── tsconfig.json
├── vitest.config.ts
└── STATE.md                          # 运行状态
```

## 详细设计

### 1. 日常 CI (`ci.yml`)

每次 push/PR 触发，运行测试并上传失败结果。

```yaml
- 触发: push, pull_request
- 步骤:
  1. checkout + setup-node
  2. npm ci
  3. npx vitest run --reporter=json --outputFile=test-results.json
  4. if failure(): upload test-results.json 作为 artifact
```

### 2. 修复循环 (`ci-fix-loop.yml`)

每天早上 08:00 UTC 触发，串联四步修复流程。

- **触发器**: cron `0 8 * * *` + workflow_dispatch
- **权限**: contents:write, issues:write
- **关键配置**: fetch-depth: 0（bisect 需要完整历史）

### 3. 检测阶段 (`run-and-collect-failures.sh`)

- 运行 vitest 并输出 JSON 格式结果
- 解析 JSON 判断是否所有测试通过
- 输出 `has_failures` 供后续步骤判断
- 保存失败详情到 test-failures.json

### 4. 诊断 + 修复阶段 (`auto-fix.sh`)

核心逻辑——git bisect 定位回归 + 自动 revert。

**bisect 策略**:
1. 标记 HEAD 为 bad
2. 标记最近一个不含 `[regression-sim]` 标记的提交为 good
3. 运行 bisect，每次用 `npm ci + vitest run` 判断好坏
4. 提取第一个坏提交

**revert 策略**:
1. 检查坏提交的 message 是否包含 `regression-sim`
2. 如果是模拟回归 → 安全 revert
3. 如果是真实提交 → 尝试 revert
4. revert 冲突时尝试 `--strategy=resolve` 解决
5. 输出 `fix_applied` 供后续步骤判断

### 5. 通知阶段 (`notify.sh`)

使用 gh CLI 创建 GitHub Issue，包含：
- 检测到的回归提交 hash
- 提交信息 + 作者
- 修复时间线
- 建议人工复核的提醒

### 6. 状态记录 (`STATE.md`)

记录每次运行的诊断结果、修复状态、关联 Issue。

### 7. 回归模拟 (`inject-regression.sh`)

教学辅助工具，在 `src/math.ts` 中注入 +1 bug 并 commit，模拟真实回归场景。

## 模拟回归机制

```
正常状态 (基线):
  commit A: add(a,b) { return a + b; }     ✅ 测试通过

引入 bug (模拟"昨天"的回归):
  commit B: add(a,b) { return a + b + 1; } ❌ 测试失败

Fix loop 运行:
  git bisect bad = commit B
  git bisect good = commit A
  → 定位到 commit B → git revert B

仓库回到 commit A 状态 → 测试通过 ✅
```

## 错误处理

| 场景 | 处理策略 |
|------|---------|
| 所有测试通过 | 直接退出，什么都不做 |
| bisect 找不到坏提交 | 输出 warning，跳过 Fix 和 Notify |
| revert 冲突 | 尝试 `--strategy=resolve`，失败则跳过 |
| 并发 push 冲突 | 第二天重试，Issue 记录冲突 |
| STATE.md 不存在 | 自动创建空模板 |

## 测试方法

三种测试方式（推荐按顺序掌握）：

1. **本地手动测试**: 执行 inject-regression → 分别执行各脚本 → 观察输出
2. **GitHub Actions 手动触发**: 在 GitHub 页面点 "Run workflow"
3. **自动化测试脚本**: 备份 → 注入回归 → 跑循环 → 验证恢复 → 还原

## Phase 2 预告

Phase 2 将在本架构基础上叠加 skill 层：
- `skills/ci-triage/SKILL.md` — CI 失败分类知识
- `skills/code-fixer/SKILL.md` — 代码修复规范
- 脚本通过读取 SKILL.md 获得上下文指导
- STATE.md 升级为完整的状态追踪

## Phase 3 预告

Phase 3 将引入子代理：
- `.claude/agents/ci-fixer.toml` — 修复代理
- `.claude/agents/code-reviewer.toml` — 审查代理
- 用 Claude Code 的 agent 能力替代 bash 脚本
- 文章的完整架构形态

## 设计决策记录

| 决策 | 选项 | 选择 | 原因 |
|------|------|------|------|
| 循环驱动 | AI Agent vs bash | bash (Phase 1) | 零成本学习循环概念 |
| 修复策略 | AI 分析修复 vs git revert | git revert | 回归类失败的最精确修复 |
| 通知方式 | PR vs Issue | Issue | Issue 更适合"记录"而非"审查" |
| 回归模拟 | 日期条件 vs commit 标记 | commit 标记 | bisect 依赖 git 历史，不能有运行时条件 |
| 触发方式 | cron vs webhook | cron | 固定时间点，简单可靠 |
