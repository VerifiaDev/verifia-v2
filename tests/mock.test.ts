import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it, mock } from "node:test";
import { parseCheckResponse } from "@/lib/api/adapter";
import { MOCK_EXAMPLES, mockService } from "@/lib/api/mock";
import type { RawCheckRequest } from "@/lib/api/contract";
import type { AnalysisStage } from "@/lib/types";

const req = (text: string): RawCheckRequest => ({ text, input_type: "text" });

/** sleep'leri mock zamanlayıcıyla ilerletir. */
async function run(text: string, signal = new AbortController().signal) {
  const stages: AnalysisStage[] = [];
  const p = mockService.check(req(text), { signal, onStage: (s) => stages.push(s) });
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
    mock.timers.tick(1000);
  }
  return { raw: await p, stages };
}

describe("mockService", () => {
  beforeEach(() => mock.timers.enable({ apis: ["setTimeout"] }));
  afterEach(() => mock.timers.reset());

  it("normal örneklerde aşama bildirmez (sahte ilerleme yok)", async () => {
    const { stages, raw } = await run("#dogru x");
    assert.deepEqual(stages, []);
    assert.equal(parseCheckResponse(raw).claims.length, 1);
  });

  it("#asamali ile aşamaları sırayla bildirir ve sonuç döner", async () => {
    const { stages, raw } = await run("#asamali x");
    assert.deepEqual(stages, ["extracting_claims", "retrieving_evidence", "verifying"]);
    assert.ok(parseCheckResponse(raw).claims.length > 0);
  });

  it("her senaryonun cevabı gerçek adapter'dan geçer (mock ve gerçek aynı yolu izler)", async () => {
    for (const key of ["#dogru", "#yanlis", "#yetersiz", "#celiski", "#gorus", "genel metin"]) {
      const { raw } = await run(`${key} x`);
      assert.doesNotThrow(() => parseCheckResponse(raw), key);
    }
  });

  it("#eksik kısmi sonuç verir: okunabilen iddia gösterilir, tanınmayan ayrı listelenir", async () => {
    const r = parseCheckResponse((await run("#eksik x")).raw);
    assert.equal(r.claims.length, 1);
    assert.equal(r.unreadable.length, 1);
  });

  it("#incelenemedi backend_v2 biçimini verir: bir iddia gösterilir, ikisi incelenemedi listesinde", async () => {
    const r = parseCheckResponse((await run("#incelenemedi x")).raw);
    assert.equal(r.claims.length, 1);
    assert.deepEqual(r.unfinished?.map((u) => u.reason), ["timeout", "skipped"]);
  });

  it("hata senaryoları ApiRequestError fırlatır", async () => {
    await assert.rejects(run("#hata-ag x"), (e: { code?: string }) => e.code === "NETWORK");
  });

  it("teknik senaryolar geliştirici örneği olarak işaretlidir; sonuç türü örnekleri değildir", () => {
    const dev = MOCK_EXAMPLES.filter((ex) => ex.dev).map((ex) => ex.content);
    assert.equal(dev.length, 3);
    assert.ok(dev.every((c) => c.includes("#asamali") || c.includes("#hata-") || c.includes("#eksik")));
    assert.equal(MOCK_EXAMPLES.filter((ex) => !ex.dev).length, 4);
  });

  it("kullanıcı vazgeçince bekleme hemen durur", async () => {
    const ctrl = new AbortController();
    const p = mockService.check(req("#dogru x"), { signal: ctrl.signal });
    ctrl.abort();
    await assert.rejects(p, (e: { name?: string }) => e.name === "AbortError");
  });
});
