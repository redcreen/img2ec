import { describe, expect, it } from "vitest";
import { genConfigReducer, initialGenConfig, toProcessExtra } from "./genConfig";

describe("genConfigReducer", () => {
  it("set_prompt updates extraPrompt", () => {
    const s = genConfigReducer(initialGenConfig, { type: "set_prompt", value: "warm" });
    expect(s.extraPrompt).toBe("warm");
  });

  it("set_weight updates extraWeight", () => {
    const s = genConfigReducer(initialGenConfig, { type: "set_weight", value: 0.9 });
    expect(s.extraWeight).toBe(0.9);
  });

  it("toggle_img adds then removes", () => {
    let s = genConfigReducer(initialGenConfig, { type: "toggle_img", id: "a" });
    expect(s.selectedImgIds.has("a")).toBe(true);
    s = genConfigReducer(s, { type: "toggle_img", id: "a" });
    expect(s.selectedImgIds.has("a")).toBe(false);
  });

  it("select_all replaces selection", () => {
    let s = genConfigReducer(initialGenConfig, { type: "toggle_img", id: "x" });
    s = genConfigReducer(s, { type: "select_all", ids: ["a", "b", "c"] });
    expect([...s.selectedImgIds].sort()).toEqual(["a", "b", "c"]);
  });

  it("clear_selection empties set", () => {
    let s = genConfigReducer(initialGenConfig, { type: "select_all", ids: ["a", "b"] });
    s = genConfigReducer(s, { type: "clear_selection" });
    expect(s.selectedImgIds.size).toBe(0);
  });

  it("set_mode switches between template and reference", () => {
    expect(initialGenConfig.mode).toBe("template");
    const s = genConfigReducer(initialGenConfig, { type: "set_mode", value: "reference" });
    expect(s.mode).toBe("reference");
  });

  it("set_reference attaches image meta", () => {
    const ref = { path: "/tmp/ref-x.jpg", url: "/static/ai-previews/ref-x.jpg", name: "ref.jpg" };
    const s = genConfigReducer(initialGenConfig, { type: "set_reference", value: ref });
    expect(s.referenceImage).toEqual(ref);
  });

  it("hydrate replaces state wholesale", () => {
    const next = {
      ...initialGenConfig,
      mode: "reference" as const,
      extraPrompt: "x",
    };
    const s = genConfigReducer(initialGenConfig, { type: "hydrate", value: next });
    expect(s).toEqual(next);
  });

  it("reset returns initial", () => {
    let s = genConfigReducer(initialGenConfig, { type: "set_prompt", value: "x" });
    s = genConfigReducer(s, { type: "toggle_img", id: "i" });
    s = genConfigReducer(s, { type: "reset" });
    expect(s).toEqual(initialGenConfig);
  });
});

describe("toProcessExtra", () => {
  it("returns undefined when default + no extras", () => {
    expect(toProcessExtra(initialGenConfig)).toBeUndefined();
  });

  it("trims extra prompts", () => {
    const r = toProcessExtra({ ...initialGenConfig, extraPrompt: "  hi  " });
    expect(r!.prompt).toBe("hi");
  });

  it("passes negative prompt", () => {
    const r = toProcessExtra({ ...initialGenConfig, extraNegativePrompt: "no text" });
    expect(r!.negative).toBe("no text");
  });

  it("reference mode without uploaded image → still no extras (defensive)", () => {
    // mode=reference 但没图：实际 UI 应该禁用 generate；这里 toProcessExtra
    // 也不应当返回 reference path（returns disableScene=true 然 referencePath=null）
    const r = toProcessExtra({ ...initialGenConfig, mode: "reference" });
    // 切到 reference 模式本身就算"有变更"，应当返回非空
    expect(r).toBeDefined();
    expect(r!.disableScene).toBe(true);
    expect(r!.referencePath).toBeNull();
  });

  it("reference mode with image → disableScene=true + path", () => {
    const ref = { path: "/tmp/ref-x.jpg", url: "/x.jpg", name: "x" };
    const r = toProcessExtra({ ...initialGenConfig, mode: "reference", referenceImage: ref });
    expect(r!.disableScene).toBe(true);
    expect(r!.referencePath).toBe("/tmp/ref-x.jpg");
  });

  it("template mode + no extras → undefined", () => {
    const r = toProcessExtra({ ...initialGenConfig, mode: "template" });
    expect(r).toBeUndefined();
  });

  it("none mode → disableScene=true, no reference path", () => {
    const r = toProcessExtra({ ...initialGenConfig, mode: "none" });
    expect(r).toBeDefined();
    expect(r!.disableScene).toBe(true);
    expect(r!.referencePath).toBeNull();
  });
});
