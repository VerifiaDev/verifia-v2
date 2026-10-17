import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { analysisReducer, isBusy, sampleEntryVisible, type AnalysisState } from "@/hooks/useAnalysis";

const idle: AnalysisState = { phase: "idle" };
const result = { claims: [], unverifiable: [], unreadable: [] };

describe("analysisReducer", () => {
  it("idle → submitting → completed", () => {
    const a = analysisReducer(idle, { type: "start" });
    assert.equal(a.phase, "submitting");
    const b = analysisReducer(a, { type: "done", result });
    assert.equal(b.phase, "completed");
  });
  it("aşama bilgisi yalnızca devam eden istekte işlenir", () => {
    const busy = analysisReducer(idle, { type: "start" });
    assert.equal(analysisReducer(busy, { type: "stage", phase: "verifying" }).phase, "verifying");
    // iptal edilmiş (idle) ya da bitmiş durumda gelen geç bilgi yok sayılır
    assert.equal(analysisReducer(idle, { type: "stage", phase: "verifying" }).phase, "idle");
    const done = analysisReducer(busy, { type: "done", result });
    assert.equal(analysisReducer(done, { type: "stage", phase: "verifying" }).phase, "completed");
  });
  it("sunucu beklenirken 'waiting_server' olur; yanıt gelince 'submitting'e döner", () => {
    const busy = analysisReducer(idle, { type: "start" });
    const waiting = analysisReducer(busy, { type: "server_wait", waiting: true });
    assert.equal(waiting.phase, "waiting_server");
    assert.equal(isBusy(waiting), true);
    assert.equal(analysisReducer(waiting, { type: "server_wait", waiting: false }).phase, "submitting");
  });
  it("bekleme bildirimi vazgeçilmiş, bitmiş ya da aşaması bildirilmiş istekte durumu değiştirmez", () => {
    assert.equal(analysisReducer(idle, { type: "server_wait", waiting: true }).phase, "idle");
    const done = analysisReducer(idle, { type: "done", result });
    assert.equal(analysisReducer(done, { type: "server_wait", waiting: true }).phase, "completed");
    const staged = analysisReducer(analysisReducer(idle, { type: "start" }), { type: "stage", phase: "verifying" });
    assert.equal(analysisReducer(staged, { type: "server_wait", waiting: false }).phase, "verifying");
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

describe("örnek sonuç ve çevrimdışı hatası", () => {
  it("örnek sonuç 'sample' olarak işaretlenir; gerçek sonuç işaretlenmez", () => {
    const real = analysisReducer(idle, { type: "done", result });
    assert.ok(real.phase === "completed" && !real.sample);
    const sample = analysisReducer(idle, { type: "done", result, sample: true });
    assert.ok(sample.phase === "completed" && sample.sample === true);
  });
  it("çevrimdışıyken ağ hatası 'OFFLINE' olur; çevrimiçiyken 'NETWORK' kalır", async () => {
    const { toApiError } = await import("@/hooks/useAnalysis");
    const { ApiRequestError } = await import("@/lib/api/errors");
    const net = new ApiRequestError("NETWORK", "x");
    assert.equal(toApiError(net, false).code, "OFFLINE");
    assert.equal(toApiError(net, true).code, "NETWORK");
    assert.equal(toApiError(new ApiRequestError("TIMEOUT", "x"), false).code, "TIMEOUT");
    assert.equal(toApiError(new Error("x"), true).code, "INTERNAL_ERROR");
  });
});

describe("hazır örnek girişi", () => {
  it("gerçek sonuç ekrandayken sunulmaz: tek tıkla sonucu silerdi ve sonuç saklanmıyor", () => {
    const real = analysisReducer(idle, { type: "done", result });
    assert.equal(sampleEntryVisible(real), false);
  });
  it("sonuç yokken (boş, bekleme, hata) sunulur; örnek açıkken yinelenmez", () => {
    assert.equal(sampleEntryVisible(idle), true);
    assert.equal(sampleEntryVisible({ phase: "submitting" }), true);
    assert.equal(sampleEntryVisible({ phase: "error", error: { code: "NETWORK", message: "m" } }), true);
    assert.equal(sampleEntryVisible(analysisReducer(idle, { type: "done", result, sample: true })), false);
  });
});
