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

  it("set_use_template toggles", () => {
    expect(initialGenConfig.useTemplate).toBe(true);
    const s = genConfigReducer(initialGenConfig, { type: "set_use_template", value: false });
    expect(s.useTemplate).toBe(false);
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

  it("emits disableScene=true when useTemplate=false", () => {
    const r = toProcessExtra({ ...initialGenConfig, useTemplate: false });
    expect(r).toBeDefined();
    expect(r!.disableScene).toBe(true);
  });

  it("trims extra prompts", () => {
    const r = toProcessExtra({ ...initialGenConfig, extraPrompt: "  hi  " });
    expect(r!.prompt).toBe("hi");
  });

  it("passes negative prompt", () => {
    const r = toProcessExtra({ ...initialGenConfig, extraNegativePrompt: "no text" });
    expect(r!.negative).toBe("no text");
  });
});
