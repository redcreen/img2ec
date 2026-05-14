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

test("project rename + delete lifecycle", async ({ request }) => {
  const name1 = `e2e-rn-${uniq()}`;
  const name2 = `e2e-rn2-${uniq()}`;
  // 建
  const create = await request.post("/api/projects",
    { data: { name: name1, copy_default_scenes: false } });
  expect(create.ok()).toBeTruthy();
  const proj = await create.json();

  // PATCH 改名
  const rn = await request.patch(`/api/projects/${proj.id}`,
    { data: { name: name2, desc: "renamed-by-e2e" } });
  expect(rn.ok()).toBeTruthy();
  const renamed = await rn.json();
  expect(renamed.name).toBe(name2);
  expect(renamed.desc).toBe("renamed-by-e2e");
  expect(renamed.root_path).toMatch(new RegExp(`${name2}$`));

  // DELETE 清理
  const del = await request.delete(`/api/projects/${proj.id}`);
  expect(del.status()).toBe(204);
});

test("upload reference image returns valid path", async ({ request }) => {
  // 借用首个项目
  const projs = await (await request.get("/api/projects")).json();
  if (!Array.isArray(projs) || projs.length === 0) test.skip(true, "no project");
  const pid = projs[0].id;
  // 用 vitest 自带的虚拟图（1x1 PNG bytes）
  const pngBytes = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    "base64",
  );
  const res = await request.post(
    `/api/projects/${pid}/uploads/reference`,
    {
      multipart: {
        file: { name: "ref.png", mimeType: "image/png", buffer: pngBytes },
      },
    },
  );
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.path).toMatch(/ref-[a-f0-9]+\.png$/);
  expect(body.url).toMatch(/^\/static\/ai-previews\/ref-/);
});

test("preview-prompt switches between modes", async ({ request }) => {
  // 找一个有 sku 的项目；没有就 skip
  const projs = await (await request.get("/api/projects")).json();
  if (!Array.isArray(projs) || projs.length === 0) test.skip(true, "no project");
  let pid = "", sid = "";
  for (const p of projs) {
    const skus = await (await request.get(`/api/projects/${p.id}/skus`)).json();
    if (Array.isArray(skus) && skus.length > 0) {
      pid = p.id; sid = skus[0].id; break;
    }
  }
  if (!sid) test.skip(true, "no sku");

  // 三种模式各拉一次 preview，1x1 段必须不一样
  const fetch1x1 = async (qs: string) => {
    const r = await request.get(
      `/api/projects/${pid}/skus/${sid}/preview-prompt${qs}`);
    expect(r.ok()).toBeTruthy();
    const j = await r.json();
    return j.per_ratio?.["1x1"] ?? "";
  };
  const tplt = await fetch1x1("");
  const none = await fetch1x1("?disable_scene=true");
  const ref = await fetch1x1("?has_reference=true");
  // 三段应当不同（用一个 indicator 字段区分）
  expect(ref).toContain("TWO reference images");
  expect(none).not.toContain("TWO reference images");
  // template 模式可能与 none 等价（SKU 没绑模板时），不强制断言其差异
  expect(tplt.length).toBeGreaterThan(0);
});
