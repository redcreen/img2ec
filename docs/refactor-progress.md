# 大重构进度

目标：彻底清洗，让 UI bug 收敛、可单测、有 e2e 兜底。

## Day 1 — 后端契约 + 单测 ✅

- [x] `backend/img2ec/infra/codex_adapter.py` — 包装 codex-imagen skill 的 thin adapter，可 monkeypatch
- [x] `backend/img2ec/infra/prompt_builder.py` — 抽出 `build_master_prompt`/`format_extra`/`format_negative` 纯函数（preview 与实际生成共用同一函数）
- [x] `codex_image.py` 改成调 adapter + prompt_builder（不再直 import gen.py）
- [x] `backend/tests/test_infra/test_prompt_builder.py` — 14 个分支单测（空 scene/含 negative/closeup/ratio-size 等）
- [x] `backend/tests/test_infra/test_codex_adapter.py` — 4 个 adapter mock 单测
- [x] `backend/scripts/dump_openapi.py` — 一键导 OpenAPI schema 到 `docs/openapi.json`
- [x] 前端 `openapi-typescript` 装上，生成 `frontend/lib/api.gen.ts`（2907 行，37 paths），加 `npm run gen:api` 脚本
- [ ] 拆 `backend/img2ec/api/skus.py`（~900 行）→ `skus/` 多个模块 — **deferred**（非用户阻塞，待下一轮）

## Day 2 — 前端拆分 + 状态机 ✅（核心达成）

- [x] `frontend/lib/genConfig.ts` — `useGenConfig()` reducer hook + 类型化 actions + `toProcessExtra`（唯一真相）
- [x] `frontend/lib/genConfig.test.ts` — 11 个 reducer + toProcessExtra 单测，全过
- [x] `frontend/components/SourceImageList.tsx` — 从 `page.tsx` 抽出（~80 行）
- [x] `page.tsx` 用 `useGenConfig()` 替换 5 个零散 useState
- [ ] `<SkuHeader>` / `<TemplatePanel>` / `<GenerationControls>` / `<VariantSwitcher>` 进一步拆分 — **deferred**（先把 reducer + 单元抽出，UI 抽完整组件等下一轮）
- [ ] `<EmptyState>` / `<ErrorBoundary>` 统一空态/错误 — **deferred**

## Day 3 — 测试 + CI + 规约 ✅

- [x] Playwright 5 个 smoke flow（projects/create/scenes/health/list），手起 dev stack 跑全过
- [x] vitest reducer 单测（与 Day 2 合并）
- [x] GitHub Actions `.github/workflows/ci.yml`：backend pytest infra + frontend tsc + vitest + lint
- [x] ESLint strict（`@typescript-eslint` 装上，no-explicit-any/no-unused-vars/rules-of-hooks 全开，修了 `MasterGallery` 两个真违规 useState）
- [x] `AGENTS.md` 开发规约（一处 prompt 一处 adapter，nullable 字段必须 fallback，新 flow 必须 e2e，hooks 顶部声明）
- [ ] Pre-commit hook — **deferred**（CI 已兜底）

## 总览

**已经修复 / 锁定**：
- UI 上各种"启用模板/不启用/负向提示词/preview 不一致"类 bug — 通过 `prompt_builder` 单函数 + 单测固化
- Codex 并发污染 — 通过 `codex_adapter` + 每次 `CODEX_HOME` 隔离 + 单测覆盖 refusal-retry
- 前端 gen-config 散乱 — 用 `useGenConfig` 集中 + 单测固化
- 跨会话 master 文件丢失 — UUID 后缀目录 + 文件存在 guard（前期已修，本轮保留）
- "rules-of-hooks" 真 bug — `MasterGallery` 两处条件 useState 修正
- CI 缺失 — 工作流跑 backend infra pytest + frontend typecheck/vitest/lint

**deferred（不影响用户）**：
- `api/skus.py` 模块拆分
- 更细粒度组件拆分（SkuHeader/TemplatePanel 等）
- ErrorBoundary / EmptyState
- Pre-commit hook（CI 已兜底）

期间未改业务行为、未动 DB schema。
