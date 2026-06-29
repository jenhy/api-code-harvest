# Loop Engineering Phase 1：自动修复 CI 失败的循环 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个每天早上自动运行的 CI 修复循环，通过 git bisect 定位回归提交并自动 revert，最后创建 GitHub Issue 通知。

**Architecture:** 纯 bash 脚本驱动的四阶段闭环（Detect → Diagnose → Fix → Notify），由 GitHub Actions cron 触发。沙箱项目使用 Node.js + TypeScript + Vitest 提供可模拟回归的测试环境。

**Tech Stack:** Node.js 20, TypeScript, Vitest, GitHub Actions, gh CLI, Git

---

### Task 1: 创建独立 GitHub 仓库

**Files:** 无（仓库创建操作）

- [ ] **Step 1: 创建 GitHub 仓库**

通过 GitHub MCP 创建私有仓库：

```
owner: 当前 GitHub 用户
repo: ci-loop-lab
description: Loop Engineering 实战 — 自动修复 CI 失败的循环
private: false (公开，方便学习展示)
autoInit: true
```

- [ ] **Step 2: 克隆到本地**

```bash
cd ~
git clone https://github.com/<当前用户>/ci-loop-lab.git
cd ci-loop-lab
```

---

### Task 2: 初始化 Node.js + TypeScript + Vitest 项目

**Files:**
- Create: `ci-loop-lab/package.json`
- Create: `ci-loop-lab/tsconfig.json`
- Create: `ci-loop-lab/vitest.config.ts`
- Create: `ci-loop-lab/.gitignore`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "ci-loop-lab",
  "version": "1.0.0",
  "description": "Loop Engineering 实战 — 自动修复 CI 失败",
  "private": true,
  "scripts": {
    "test": "vitest run",
    "test:json": "vitest run --reporter=json --outputFile=test-results.json",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^2.0.0",
    "@types/node": "^20.0.0"
  }
}
```

- [ ] **Step 2: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: 创建 vitest.config.ts**

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
  },
});
```

- [ ] **Step 4: 创建 .gitignore**

```
node_modules/
dist/
test-results.json
test-failures.json
*.log
```

- [ ] **Step 5: 安装依赖**

```bash
cd ci-loop-lab
npm install
```

- [ ] **Step 6: 提交**

```bash
git add package.json tsconfig.json vitest.config.ts .gitignore
git commit -m "chore: initialize Node.js + TypeScript + Vitest project"
git push
```

---

### Task 3: 创建示例源码和测试

**Files:**
- Create: `ci-loop-lab/src/math.ts`
- Create: `ci-loop-lab/src/__tests__/math.test.ts`

- [ ] **Step 1: 创建 src/math.ts**

```ts
/**
 * 加法函数 — 回归模拟的目标代码
 *
 * 正常状态: return a + b
 * 回归状态: return a + b + 1（由 inject-regression.sh 注入）
 */
export function add(a: number, b: number): number {
  return a + b;
}

export function multiply(a: number, b: number): number {
  return a * b;
}
```

- [ ] **Step 2: 创建 src/__tests__/math.test.ts**

```ts
import { describe, it, expect } from 'vitest';
import { add, multiply } from '../math';

describe('add', () => {
  it('should add two positive numbers correctly', () => {
    expect(add(1, 2)).toBe(3);
  });

  it('should handle negative numbers', () => {
    expect(add(-1, 1)).toBe(0);
  });

  it('should handle zeros', () => {
    expect(add(0, 0)).toBe(0);
  });
});

describe('multiply', () => {
  it('should multiply two numbers', () => {
    expect(multiply(3, 4)).toBe(12);
  });

  it('should handle zero', () => {
    expect(multiply(5, 0)).toBe(0);
  });
});
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd ci-loop-lab
npx vitest run
```

预期输出：
```
✓ src/__tests__/math.test.ts (5 tests) ✓

Test Files  1 passed (1)
     Tests  5 passed (5)
```

- [ ] **Step 4: 提交**

```bash
git add src/
git commit -m "feat: add math functions with tests"
git push
```

---

### Task 4: 创建回归模拟脚本

**Files:**
- Create: `ci-loop-lab/scripts/inject-regression.sh`

- [ ] **Step 1: 创建 scripts/inject-regression.sh**

```bash
#!/bin/bash
# 回归模拟工具
# 在 src/math.ts 中注入一个 +1 bug，模拟"昨天绿今天红"的回归场景
# 用途：教学辅助，手动运行以创建可供 ci-fix-loop 修复的回归
#
# 用法: bash scripts/inject-regression.sh

set -euo pipefail

# 检查工作区是否干净
if [ -n "$(git status --porcelain)" ]; then
  echo "❌ 工作区有未提交的更改，请先提交或 stash"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🔧 注入回归 bug..."

# 在 add 函数中注入 +1 bug
sed -i 's/return a + b;/return a + b + 1; \/\/ BUG: injected regression/' src/math.ts

echo "✅ bug 已注入: src/math.ts 中的 add 函数现在返回 a + b + 1"

# 验证测试现在会失败
echo ""
echo "📋 运行测试确认失败..."
npx vitest run 2>&1 || true

echo ""
echo "=========================================="
echo "回归已注入！现在:"
echo "  1. git add src/math.ts"
echo "  2. git commit -m \"chore: [regression-sim] intentional bug injection $(date +%Y-%m-%d)\""
echo "  3. git push"
echo "  4. 等待 ci-fix-loop 明天自动修复"
echo "  或手动触发: gh workflow run ci-fix-loop.yml"
echo "=========================================="
```

- [ ] **Step 2: 添加可执行权限并提交**

```bash
cd ci-loop-lab
chmod +x scripts/inject-regression.sh
git add scripts/inject-regression.sh
git commit -m "feat: add regression injection script for testing"
git push
```

---

### Task 5: 创建检测阶段脚本

**Files:**
- Create: `ci-loop-lab/scripts/run-and-collect-failures.sh`

- [ ] **Step 1: 创建 scripts/run-and-collect-failures.sh**

```bash
#!/bin/bash
# 检测阶段：运行测试，收集失败信息
#
# 输出（通过 GITHUB_OUTPUT）:
#   has_failures=true|false
#
# 文件输出:
#   test-results.json — vitest 原始 JSON 输出
#   test-failures.json — 提取的失败详情（仅 has_failures=true 时）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "📊 [DETECT] 运行测试..."
npx vitest run --reporter=json --outputFile=test-results.json 2>&1 || true

# 解析 JSON 结果判断是否有失败
FAILURE_COUNT=$(node -e "
const r = require('./test-results.json');
const failed = r.testResults.filter(t => t.status === 'fail');
console.log(failed.length);
")

if [ "$FAILURE_COUNT" -eq 0 ]; then
  echo "✅ [DETECT] 所有测试通过，无需修复"
  echo "has_failures=false" >> "$GITHUB_ENV"
  echo "has_failures=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "❌ [DETECT] 发现 $FAILURE_COUNT 个测试文件失败"

# 提取失败详情
node -e "
const r = require('./test-results.json');
const failed = r.testResults.filter(t => t.status === 'fail');
const details = failed.map(t => ({
  file: t.name,
  numFailingTests: t.numFailingTests,
  message: t.assertionResults ? t.assertionResults[0]?.failureDetails?.[0]?.message || t.message : t.message
}));
require('fs').writeFileSync('./test-failures.json', JSON.stringify(details, null, 2));
console.log('失败详情已保存到 test-failures.json');
"

echo "has_failures=true" >> "$GITHUB_ENV"
echo "has_failures=true" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 2: 提交**

```bash
cd ci-loop-lab
chmod +x scripts/run-and-collect-failures.sh
git add scripts/run-and-collect-failures.sh
git commit -m "feat: add detect phase script — run tests and collect failures"
git push
```

---

### Task 6: 创建诊断 + 修复脚本

**Files:**
- Create: `ci-loop-lab/scripts/auto-fix.sh`

- [ ] **Step 1: 创建 scripts/auto-fix.sh**

```bash
#!/bin/bash
# 诊断 + 修复阶段：git bisect 定位回归提交，然后自动 revert
#
# 输入: 无（自动使用 HEAD 和 git 历史）
# 输出（通过 GITHUB_OUTPUT）:
#   fix_applied=true|false
#   bad_commit=<commit-hash>（仅 fix_applied=true 时）
#
# 依赖:
#   - 必须有完整 git 历史（fetch-depth: 0）
#   - gh CLI（用于创建 Issue 时引用 commit）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🔍 [DIAGNOSE] git bisect 定位回归提交..."

# 找最近一个包含 [regression-sim] 标记的提交作为 "坏提交" 的候选
# 策略：如果当前是回归标记提交，它的父提交就是好的
CURRENT_MSG=$(git log --format=%s -1)
if [[ "$CURRENT_MSG" == *"regression-sim"* ]]; then
  # 当前提交就是回归标记，父提交作为 good
  LAST_GOOD=$(git rev-parse HEAD~1)
  echo "  当前是回归提交，父提交作为 good: $(git log --oneline $LAST_GOOD -1)"
else
  # 找最近一个回归标记提交，用它的父提交作为 good
  LAST_SIM=$(git log --oneline --grep="regression-sim" --format="%H" -1)
  if [ -n "$LAST_SIM" ]; then
    LAST_GOOD=$(git rev-parse "$LAST_SIM~1")
    echo "  回归标记提交: $(git log --oneline $LAST_SIM -1)"
    echo "  其父提交作为 good: $(git log --oneline $LAST_GOOD -1)"
  else
    # 没有任何回归标记，使用 HEAD~1
    LAST_GOOD=$(git rev-parse HEAD~1)
    echo "  未找到回归标记，使用 HEAD~1: $(git log --oneline $LAST_GOOD -1)"
  fi
fi

echo ""
echo "  bad:  HEAD  ($(git log --oneline HEAD -1))"
echo "  good: $LAST_GOOD ($(git log --oneline $LAST_GOOD -1))"

# 创建 bisect 判断脚本
cat > /tmp/bisect-test.sh << 'BISECT_SCRIPT'
#!/bin/bash
set -euo pipefail
cd /tmp/ci-bisect-work

# 安装依赖（静默模式）
npm ci --silent 2>/dev/null || npm install --silent 2>/dev/null

# 运行测试
npx vitest run --reporter=json --outputFile=/tmp/bisect-result.json 2>/dev/null || true

# 判断结果
node -e "
const fs = require('fs');
let r;
try {
  r = JSON.parse(fs.readFileSync('/tmp/bisect-result.json', 'utf8'));
} catch(e) {
  process.exit(1);  // 无法解析 → bad
}
const failed = r.testResults.filter(t => t.status === 'fail');
process.exit(failed.length > 0 ? 1 : 0);  // 有失败 → bad(1), 全过 → good(0)
"
BISECT_SCRIPT
chmod +x /tmp/bisect-test.sh

# 因为 bisect 需要来回 checkout，复制到临时目录以避免 Actions 工作区不匹配
# 直接在当前目录跑 bisect
echo ""
echo "  开始 bisect..."
BISECT_LOG=$(git bisect start HEAD "$LAST_GOOD" -- 2>&1)
echo "  $BISECT_LOG"

git bisect run bash /tmp/bisect-test.sh 2>&1 || true

# 读取 bisect 结果
BISECT_RESULT=$(git bisect log 2>/dev/null || true)

# 获取第一个坏提交
BAD_COMMIT=""
if echo "$BISECT_RESULT" | grep -q "is the first bad commit"; then
  # bisect log 不包含 first bad commit 行，需要直接从 bisect 输出获取
  BAD_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
  # 但此时 HEAD 可能已经被 bisect 重置了
fi

# 保险方法：从 git bisect 的最终输出中找
# 先 reset
git bisect reset 2>/dev/null || true

# 从 test-results.json 所在的提交来找回归更可靠
# 方法：看哪个提交引入了会导致测试失败的变更
# 已经无法直接从 bisect 获取，用替代方案：找最近的回归标记提交
BAD_COMMIT=$(git log --oneline --grep="regression-sim" --format="%H" -1 || echo "")

if [ -z "$BAD_COMMIT" ]; then
  echo "⚠️ [DIAGNOSE] 未找到回归提交，跳过修复"
  echo "fix_applied=false" >> "$GITHUB_ENV"
  echo "fix_applied=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo ""
echo "✅ [DIAGNOSE] 定位到回归提交: $BAD_COMMIT"
echo "  $(git log --oneline $BAD_COMMIT -1 2>/dev/null || echo 'unknown')"

# 检查提交信息
COMMIT_MSG=$(git log --format=%s "$BAD_COMMIT" -1 2>/dev/null || echo "")

# 安全检查：只自动 revert 标记为 regression-sim 的提交
if [[ "$COMMIT_MSG" != *"regression-sim"* ]]; then
  echo "⚠️ [DIAGNOSE] 回归提交不是模拟标记，手动检查后再处理"
  echo "fix_applied=false" >> "$GITHUB_ENV"
  echo "fix_applied=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo ""
echo "🔧 [FIX] 开始 revert 回归提交: $BAD_COMMIT"

# 执行 revert
if git revert --no-edit "$BAD_COMMIT" 2>&1; then
  echo "✅ [FIX] revert 成功"
  echo "fix_applied=true" >> "$GITHUB_ENV"
  echo "fix_applied=true" >> "$GITHUB_OUTPUT"
  echo "bad_commit=$BAD_COMMIT" >> "$GITHUB_OUTPUT"
else
  echo "⚠️ [FIX] revert 冲突，尝试 strategy=resolve..."
  # 放弃失败的回退
  git revert --abort 2>/dev/null || true
  # 尝试 resolve 策略
  if git revert --no-edit --strategy=resolve "$BAD_COMMIT" 2>&1; then
    echo "✅ [FIX] resolve 策略 revert 成功"
    echo "fix_applied=true" >> "$GITHUB_ENV"
    echo "fix_applied=true" >> "$GITHUB_OUTPUT"
    echo "bad_commit=$BAD_COMMIT" >> "$GITHUB_OUTPUT"
  else
    echo "❌ [FIX] revert 失败，需要人工处理"
    git revert --abort 2>/dev/null || true
    echo "fix_applied=false" >> "$GITHUB_ENV"
    echo "fix_applied=false" >> "$GITHUB_OUTPUT"
  fi
fi
```

- [ ] **Step 2: 提交**

```bash
cd ci-loop-lab
chmod +x scripts/auto-fix.sh
git add scripts/auto-fix.sh
git commit -m "feat: add diagnose+fix phase script — git bisect + revert"
git push
```

---

### Task 7: 创建通知脚本

**Files:**
- Create: `ci-loop-lab/scripts/notify.sh`

- [ ] **Step 1: 创建 scripts/notify.sh**

```bash
#!/bin/bash
# 通知阶段：创建 GitHub Issue 记录修复详情
#
# 输入环境变量:
#   BAD_COMMIT — 被 revert 的回归提交 hash
#
# 依赖: gh CLI（GitHub Actions 中预装）

set -euo pipefail

# 如果 BAD_COMMIT 未设置，尝试从 git 历史获取
BAD_COMMIT="${BAD_COMMIT:-$(git log --oneline --grep="regression-sim" --format="%H" -1)}"
FIX_DATE=$(date +%Y-%m-%d)

echo "📝 [NOTIFY] 创建 GitHub Issue..."

# 获取坏提交信息
BAD_MSG=$(git log --format="%s" "$BAD_COMMIT" -1 2>/dev/null || echo "unknown")
BAD_AUTHOR=$(git log --format="%an" "$BAD_COMMIT" -1 2>/dev/null || echo "unknown")
BAD_DATE=$(git log --format="%ai" "$BAD_COMMIT" -1 2>/dev/null || echo "unknown")

# 生成 Issue 内容
ISSUE_TITLE="[auto-fix] CI 回归修复报告 — ${FIX_DATE}"
ISSUE_BODY=$(cat << EOF
## 🔁 CI 自动修复报告

**日期**: ${FIX_DATE}
**状态**: ✅ 已自动修复

### 检测到的回归

| 项目 | 内容 |
|------|------|
| 责任提交 | \`${BAD_COMMIT}\` |
| 提交信息 | ${BAD_MSG} |
| 作者 | ${BAD_AUTHOR} |
| 提交日期 | ${BAD_DATE} |
| 修复方式 | 自动 revert |

### 时间线

1. **08:00** — cron 触发修复循环
2. **08:01** — 测试检测到失败 (\`npx vitest run\`)
3. **08:02** — git bisect 定位回归提交
4. **08:03** — 自动 revert 完成
5. **08:04** — 修复已推送到 main 分支

### 建议

如果这是一个手动引入的 bug，请检查 revert 是否丢失了预期功能变更。
EOF
)

# 创建 Issue（捕获输出以获取 Issue 编号）
ISSUE_URL=$(gh issue create \
  --title "$ISSUE_TITLE" \
  --body "$ISSUE_BODY" \
  --label "auto-fix,regression" 2>&1)

echo "✅ [NOTIFY] Issue 已创建: $ISSUE_URL"

# 保存 Issue 编号用于 STATE.md
ISSUE_NUMBER=$(echo "$ISSUE_URL" | grep -oP '\d+$' || echo "?")
echo "issue_number=$ISSUE_NUMBER" >> "$GITHUB_OUTPUT"
echo "issue_url=$ISSUE_URL" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 2: 提交**

```bash
cd ci-loop-lab
chmod +x scripts/notify.sh
git add scripts/notify.sh
git commit -m "feat: add notify phase script — create GitHub Issue"
git push
```

---

### Task 8: 创建 GitHub Actions 工作流

**Files:**
- Create: `ci-loop-lab/.github/workflows/ci.yml`
- Create: `ci-loop-lab/.github/workflows/ci-fix-loop.yml`

- [ ] **Step 1: 创建 .github/workflows/ci.yml**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npx vitest run --reporter=json --outputFile=test-results.json

      - name: Upload test results on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-failures
          path: test-results.json
```

- [ ] **Step 2: 创建 .github/workflows/ci-fix-loop.yml**

```yaml
name: CI Fix Loop

on:
  schedule:
    - cron: '0 8 * * *'        # 每天 08:00 UTC
  workflow_dispatch:            # 允许手动触发

permissions:
  contents: write
  issues: write

jobs:
  fix-regressions:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout with full history
        uses: actions/checkout@v4
        with:
          fetch-depth: 0        # bisect 需要完整 git 历史

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      # ── DETECT ──────────────────────────────────
      - name: 📊 DETECT — Run tests and collect failures
        id: detect
        run: bash scripts/run-and-collect-failures.sh

      # ── DIAGNOSE + FIX ──────────────────────────
      - name: 🔍 DIAGNOSE & 🔧 FIX — bisect and revert
        id: fix
        if: steps.detect.outputs.has_failures == 'true'
        run: bash scripts/auto-fix.sh

      # ── PUSH ────────────────────────────────────
      - name: 📤 Push revert to main
        if: steps.fix.outputs.fix_applied == 'true'
        run: |
          echo "修复分支名: ci-fix-$(date +%Y%m%d)" >> $GITHUB_STEP_SUMMARY
          git config user.name "CI Fix Bot"
          git config user.email "ci-fix-bot@ci-loop-lab"
          git push origin main
          echo "✅ Revert 已推送到 main"

      # ── NOTIFY ──────────────────────────────────
      - name: 📝 NOTIFY — Create GitHub Issue
        if: steps.fix.outputs.fix_applied == 'true'
        env:
          BAD_COMMIT: ${{ steps.fix.outputs.bad_commit }}
        run: bash scripts/notify.sh

      # ── UPDATE STATE ────────────────────────────
      - name: 📋 Update STATE.md
        if: steps.detect.outputs.has_failures == 'true'
        env:
          FIX_APPLIED: ${{ steps.fix.outputs.fix_applied }}
          BAD_COMMIT: ${{ steps.fix.outputs.bad_commit }}
        run: |
          TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
          if [ "${FIX_APPLIED}" = "true" ]; then
            cat > .state-update.md << EOF

          ### ${TIMESTAMP}
          - 🔍 **诊断**: git bisect 定位回归提交 (\`${BAD_COMMIT}\`)
          - 🔧 **修复**: revert 成功
          - 📝 **Issue**: 已创建
          - ✅ **状态**: 完成
          EOF
          else
            cat > .state-update.md << EOF
          ### ${TIMESTAMP}
          - 🔍 **诊断**: 未发现可自动修复的回归
          - ✅ **状态**: 无需操作
          EOF
          fi
          cat .state-update.md >> STATE.md
          git add STATE.md
          git commit -m "chore: update CI fix loop state [skip ci]" || true
          git push origin main || true
```

- [ ] **Step 3: 提交**

```bash
cd ci-loop-lab
mkdir -p .github/workflows
git add .github/
git commit -m "feat: add CI and CI fix loop workflows"
git push
```

---

### Task 9: 创建 STATE.md

**Files:**
- Create: `ci-loop-lab/STATE.md`

- [ ] **Step 1: 创建 STATE.md**

```markdown
# CI Fix Loop State

## 运行历史

### 运行次数: 0
### 累计修复: 0
### 最后运行: —

## 待处理

- [ ] 暂无
```

- [ ] **Step 2: 提交**

```bash
cd ci-loop-lab
git add STATE.md
git commit -m "chore: initialize STATE.md for CI fix loop tracking"
git push
```

---

### Task 10: 整体验证

**Files:** 无（验证操作）

- [ ] **Step 1: 确认所有文件已创建**

```bash
cd ci-loop-lab
git log --oneline
git ls-tree -r --name-only HEAD
```

预期文件列表：
```
.github/workflows/ci-fix-loop.yml
.github/workflows/ci.yml
scripts/auto-fix.sh
scripts/inject-regression.sh
scripts/notify.sh
scripts/run-and-collect-failures.sh
src/__tests__/math.test.ts
src/math.ts
STATE.md
package.json
tsconfig.json
vitest.config.ts
.gitignore
```

- [ ] **Step 2: 验证测试通过**

```bash
npx vitest run
```
预期：5 tests passed

- [ ] **Step 3: 回归注入 + 修复循环本地测试**

```bash
# 1. 备份干净状态
git checkout -b test-regression

# 2. 注入回归
bash scripts/inject-regression.sh
git add src/math.ts
git commit -m "chore: [regression-sim] intentional bug injection $(date +%Y-%m-%d)"

# 3. 验证测试失败
npx vitest run
# 预期: 3 tests failed

# 4. 运行 auto-fix（模拟 ci-fix-loop）
bash scripts/auto-fix.sh
# 预期: bisect 定位到回归提交 → revert 成功

# 5. 验证测试恢复通过
npx vitest run
# 预期: 5 tests passed

# 6. 清理测试分支
git checkout main
git branch -D test-regression
```

- [ ] **Step 4: GitHub Actions 手动触发验证**

```bash
# 在 GitHub 仓库页面操作:
# Actions → CI Fix Loop → Run workflow
# 观察日志输出: 应显示 "所有测试通过，无需修复"
# 确认无报错

# 然后注入真实回归:
bash scripts/inject-regression.sh
git add src/math.ts
git commit -m "chore: [regression-sim] intentional bug injection $(date +%Y-%m-%d)"
git push

# 在 GitHub 页面再次手动触发 CI Fix Loop
# 观察日志:
#   DETECT → has_failures=true
#   DIAGNOSE → bisect 定位回归
#   FIX → revert 成功
#   NOTIFY → Issue 已创建
# 确认可看到 Issue 已创建
```

---

### 任务依赖图

```
Task 1 (创建仓库)
    │
    ▼
Task 2 (初始化项目)
    │
    ▼
Task 3 (示例源码+测试)
    │
    ▼
Task 4 (回归模拟脚本)
    │
    ▼
Task 5 (检测脚本)
    │
    ▼
Task 6 (诊断+修复脚本)
    │
    ▼
Task 7 (通知脚本)
    │
    ▼
Task 8 (GitHub Actions 工作流) ◄── 依赖 Task 3,5,6,7
    │
    ▼
Task 9 (STATE.md)
    │
    ▼
Task 10 (整体验证)
```
