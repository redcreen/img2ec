# img2ec — Development Rules

Read this file before doing any non-trivial work in this repo. These rules exist because we got bitten by the failure they prevent. Don't relax them without discussing first.

## Architecture invariants

- **Prompt construction is one function.** `backend/img2ec/infra/prompt_builder.py::build_master_prompt` is the *single* source of truth for what gets sent to Codex. Both the preview API and the actual generate path call it. If you need a tweak, change it there — never inline a copy.
- **Codex adapter is the only path to Codex.** `backend/img2ec/infra/codex_adapter.py::generate_image` wraps the codex-imagen skill. Business code (`codex_image.py`, pipelines) must go through it so unit tests can monkeypatch. Don't import `gen.py` from anywhere else.
- **Codex per-call isolation is non-negotiable.** Each Codex invocation runs in a fresh `CODEX_HOME` tempdir (symlinks for auth/config). See `docs/codex-concurrency.md`. If you add a new Codex caller, route it through the adapter — never share `~/.codex/`.
- **SKU disk layout uses UUID suffix.** Path is `<project>/<sku_name>-<id8>/`. Renaming a SKU does NOT rename the directory. Two SKUs with the same display name must coexist on disk.
- **Frontend gen-config has one reducer.** `frontend/lib/genConfig.ts` is the single source of truth for "本次生成"配置 (prompt/weight/negative/useTemplate/selected). Don't sprinkle `useState` across `page.tsx` for these fields.

## Workflow rules

- **Change a backend route → regenerate types.** Run `npm run gen:api` in `frontend/` after any FastAPI signature change. The committed `frontend/lib/api.gen.ts` must match the live OpenAPI dump.
- **Add a Pydantic field → write a fallback in the consumer.** A new nullable field on a response model is silently `undefined` in the frontend; if any UI reads it without a default, you ship a runtime error.
- **Add a complex flow → write an e2e.** Anything that crosses API + DB + UI (create-project / upload-image / process-trigger / version-switch) needs a Playwright smoke in `frontend/e2e/smoke.spec.ts`. The bar is low: just verify the route + a visible element.
- **Pure logic → write a unit test.** `prompt_builder`, `codex_adapter` parsing, and `genConfigReducer` all have unit tests. New pure functions should follow suit.
- **Don't `--amend` past a commit you've pushed.** Make a new commit. Force-push to `main` is forbidden.

## React hooks discipline

- **All `useState/useEffect/useMemo` calls go at the top of the component**, before any early return. ESLint enforces `react-hooks/rules-of-hooks`. If you put a hook after `if (...) return ...`, CI fails.
- **`useEffect` deps must list every value used inside the effect.** `exhaustive-deps` is warn — read the warnings, don't ignore them.

## Testing layers

| Layer | Tool | Where | What |
|---|---|---|---|
| Backend unit | pytest | `backend/tests/test_infra/` | pure functions (prompt builder, adapter parsing) |
| Backend integration | pytest | `backend/tests/test_api/` etc. | DB + route (skipped in CI for now — requires fixtures) |
| Frontend unit | vitest | `frontend/lib/*.test.ts` | reducers, pure utils |
| Frontend e2e | Playwright | `frontend/e2e/` | requires `start.sh` dev stack running |
| Type | tsc + mypy | both | CI-gated |
| Style | ruff + eslint | both | CI-gated |

CI (`.github/workflows/ci.yml`) runs: backend `pytest tests/test_infra`, frontend `tsc --noEmit + vitest + lint`. E2E is local-only for now (requires real services).

## "Why did this UI bug keep coming back?"

Pre-refactor, gen-config lived in 5 scattered `useState` calls; preview prompt and actual prompt were built by two different functions; Codex was called inline so we couldn't unit-test it; e2e smoke didn't exist. Every UI fix risked breaking something else because nothing was a contract.

Post-refactor:
- One reducer ⇒ impossible to forget a field.
- One prompt function ⇒ preview == actual, always.
- Adapter + unit tests ⇒ refactors don't silently change Codex behavior.
- E2E ⇒ "still loads" is a tripwire on every push.

If you're about to add another `useState` in `page.tsx` for a gen-config field, or copy `build_master_prompt` logic elsewhere — stop. You're rebuilding the problem we just solved.
