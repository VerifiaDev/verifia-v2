import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { analysisReducer, isBusy, type AnalysisState } from "@/hooks/useAnalysis";

const idle: AnalysisState = { phase: "idle" };
const result = { claims: [], unverifiable: [] };

describe("analysisReducer", () => {
  it("idle → submitting → completed", () => {
    const a = analysisReducer(idle, { type: "start" });
    assert.equal(a.phase, "submitting");
    const b = analysisReducer(a, { type: "done", result, input: "x" });
    assert.equal(b.phase, "completed");
  });
  it("aşama bilgisi yalnızca devam eden istekte işlenir", () => {
    const busy = analysisReducer(idle, { type: "start" });
    assert.equal(analysisReducer(busy, { type: "stage", phase: "verifying" }).phase, "verifying");
    // iptal edilmiş (idle) ya da bitmiş durumda gelen geç bilgi yok sayılır
    assert.equal(analysisReducer(idle, { type: "stage", phase: "verifying" }).phase, "idle");
    const done = analysisReducer(busy, { type: "done", result, input: "x" });
    assert.equal(analysisReducer(done, { type: "stage", phase: "verifying" }).phase, "completed");
  });
  it("hata ve sıfırlama", () => {
    const e = analysisReducer(idle, { type: "fail", error: { code: "NETWORK", message: "m" } });
    assert.equal(e.phase, "error");
    assert.equal(analysisReducer(e, { type: "reset" }).phase, "idle");
  });
  it("isBusy yalnızca devam eden aşamalarda doğrudur", () => {
    assert.equal(isBusy({ phase: "submitting" }), true);
    assert.equal(isBusy({ phase: "extracting_claims" }), true);
    assert.equal(isBusy(idle), false);
  });
});
