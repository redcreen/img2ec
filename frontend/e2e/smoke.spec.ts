/**
 * E2E smoke tests — 跑 dev 实例（localhost:3011）。
 * 用法：
 *   ENV_NAME=dev ./scripts/start.sh   # 先确保 dev 起来
 *   cd frontend && npx playwright test
 *
 * 这里覆盖核心 happy path；不涉及 codex 实际生成（太慢），只验 UI/route/POST 触发。
 */
import { expect, test } from "@playwright/test";

const uniq = () => Math.random().toString(36).slice(2, 8);

test("projects page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/projects/);
});

test("create project via api + see in list", async ({ page, request }) => {
  const projName = `e2e-${uniq()}`;
  const res = await request.post("/api/projects", { data: { name: projName } });
  expect(res.ok()).toBeTruthy();
  const proj = await res.json();
  expect(proj.name).toBe(projName);

  await page.goto("/projects");
  await expect(page.getByText(projName)).toBeVisible({ timeout: 10000 });
});

test("api scenes list responds for a project", async ({ request }) => {
  const projs = await (await request.get("/api/projects")).json();
  if (!Array.isArray(projs) || projs.length === 0) test.skip(true, "no project");
  const res = await request.get(`/api/projects/${projs[0].id}/scenes`);
  expect(res.ok()).toBeTruthy();
  expect(Array.isArray(await res.json())).toBeTruthy();
});

test("api health ok", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.ok()).toBeTruthy();
  expect(await res.json()).toEqual({ status: "ok" });
});

test("api projects list returns array", async ({ request }) => {
  const res = await request.get("/api/projects");
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(Array.isArray(body)).toBeTruthy();
});
