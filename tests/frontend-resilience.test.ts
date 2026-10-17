import assert from "node:assert/strict";
import { afterEach, it, mock } from "node:test";
import { parseCheckResponse, InvalidResponseError } from "../lib/api/adapter";
import { claimAnchor, sourceAnchor, formatDate } from "../lib/format";
import { httpService } from "../lib/api/http";
import { ApiRequestError } from "../lib/api/errors";
import { HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "../lib/config";

const good = { claim_id: "a", claim: "Geçerli iddia", verdict: "SUPPORTED", sources: [{ id: "s1", url: "https://example.com" }] };
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

it("malformed rows preserve valid claims and explicitly report unreadable rows", () => {
  const result = parseCheckResponse({ results: [good, null, { verdict: "SUPPORTED" }] });
  assert.equal(result.claims.length, 1);
  assert.deepEqual(result.unreadable, ["2. iddia (metin okunamadı)", "3. iddia (metin okunamadı)"]);
  assert.throws(() => parseCheckResponse({ results: [null] }), InvalidResponseError);
});
it("unsafe or malformed sources never count as evidence", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,test", "/relative", "not a url"]) {
    const result = parseCheckResponse({ results: [{ ...good, sources: [{ url }] }] });
    assert.equal(result.claims[0].sources.length, 0);
    assert.equal(result.claims[0].verdict, "NOT_ENOUGH_EVIDENCE");
  }
  const result = parseCheckResponse({ results: [{ ...good, sources: [{ url: "javascript:bad" }, ...good.sources] }] });
  assert.equal(result.claims[0].sources[0].id, "s1");
  assert.equal(result.claims[0].verdict, "SUPPORTED");
});
it("unknown processing states cannot become verdicts", () => {
  const result = parseCheckResponse({ results: [good, { ...good, status: "pending", claim: "Bekleyen iddia" }] });
  assert.equal(result.claims.length, 1);
  assert.deepEqual(result.unreadable, ["Bekleyen iddia"]);
});
it("duplicate IDs keep every claim and reserve IDs supplied by other rows", () => {
  const result = parseCheckResponse({ results: [good, good, { ...good, claim_id: "a__2" }, good] });
  assert.equal(result.claims.length, 4);
  assert.equal(new Set(result.claims.map((c) => c.id)).size, 4);
  assert.equal(result.claims[2].id, "a__2");
});
it("distinct arbitrary IDs have distinct anchors; existing ordinary anchors stay stable", () => {
  const ids = ["a.b", "a/b", "a_b", "a~2e~b", "a b", "İddia", "😀"];
  assert.equal(new Set(ids.map(claimAnchor)).size, ids.length);
  assert.equal(new Set(ids.map((id) => sourceAnchor(id, 1))).size, ids.length);
  assert.equal(claimAnchor("apollo_date"), "claim-apollo_date");
  assert.equal(sourceAnchor("apollo_date", 1), "src-apollo_date-1");
});
it("calendar-invalid dates are never normalized into plausible dates", () => {
  for (const date of ["2026-02-30", "2025-02-29", "2026-04-31", "2026-02-30T12:00:00Z", "Mon, 30 Feb 2026 12:00:00 GMT", "1900-02-29"]) {
    assert.equal(formatDate(date), null, date);
  }
  assert.equal(formatDate("2024-02-29"), "29 Şubat 2024");
  assert.equal(formatDate("2000-02-29"), "29 Şubat 2000");
});
it("degraded and unsuccessful health responses stop before POST /verify", async () => {
  for (const [status, body, code] of [
    [200, { status: "degraded" }, "SERVICE_UNAVAILABLE"],
    [200, { status: "error" }, "SERVICE_UNAVAILABLE"],
    [503, {}, "SERVICE_UNAVAILABLE"],
    [429, { error: "BUSY" }, "SERVER_BUSY"],
  ] as const) {
    let calls = 0;
    globalThis.fetch = (async () => { calls++; return Response.json(body, { status }); }) as typeof fetch;
    await assert.rejects(httpService("https://backend.test").check({ text: "iddia", input_type: "text" }, { signal: new AbortController().signal }),
      (e: unknown) => e instanceof ApiRequestError && e.code === code);
    assert.equal(calls, 1);
  }
});
it("already cancelled requests do not send even a health request", async () => {
  let calls = 0;
  globalThis.fetch = (async () => { calls++; return Response.json({ results: [] }); }) as typeof fetch;
  const ctrl = new AbortController();
  ctrl.abort();
  await assert.rejects(httpService("https://backend.test").check({ text: "iddia", input_type: "text" }, { signal: ctrl.signal }), { name: "AbortError" });
  assert.equal(calls, 0);
});
it("cancellation while reading health prevents verification", async () => {
  let calls = 0;
  const ctrl = new AbortController();
  globalThis.fetch = (async () => {
    calls++;
    const response = Response.json({ status: "ok" });
    response.json = async () => { ctrl.abort(); return { status: "ok" }; };
    return response;
  }) as typeof fetch;
  await assert.rejects(httpService("https://backend.test").check({ text: "iddia", input_type: "text" }, { signal: ctrl.signal }), { name: "AbortError" });
  assert.equal(calls, 1);
});

for (const stage of ["health", "verify"] as const) {
  it(`${stage} timeout still applies while reading the response body`, async () => {
    mock.timers.enable({ apis: ["setTimeout"] });
    try {
      let calls = 0;
      globalThis.fetch = (async (url: string, init: RequestInit) => {
        calls++;
        const response = Response.json({ status: "ok" });
        if (url.endsWith(stage)) {
          response.json = () => new Promise((_, reject) => {
            init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
          });
        }
        return response;
      }) as typeof fetch;
      const pending = assert.rejects(httpService("https://backend.test").check({ text: "iddia", input_type: "text" }, { signal: new AbortController().signal }),
        (e: unknown) => e instanceof ApiRequestError && e.code === (stage === "health" ? "SERVER_BUSY" : "TIMEOUT"));
      await new Promise<void>((resolve) => setImmediate(resolve));
      mock.timers.tick(stage === "health" ? HEALTH_TIMEOUT_MS : REQUEST_TIMEOUT_MS);
      await pending;
      assert.equal(calls, stage === "health" ? 1 : 2);
    } finally {
      mock.timers.reset();
    }
  });
}
