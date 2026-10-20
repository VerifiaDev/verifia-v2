import assert from "node:assert/strict";
import { afterEach, describe, it, mock } from "node:test";
import { httpService } from "../lib/api/http";
import { ApiRequestError } from "../lib/api/errors";
import { parseCheckResponse } from "../lib/api/adapter";
import { REQUEST_TIMEOUT_MS, STREAM_IDLE_TIMEOUT_MS } from "../lib/config";
import type { AnalysisStage } from "../lib/types";

/**
 * POST /verify/stream (backend_v2/app/streaming.py): olaylar `event: <ad>\ndata: <json>\n\n`, ara sıra `: keep-alive`.
 * Arayüz aynı ham cevabı ({ results }) üretir; aşamalar yalnızca backend bildirdikçe gösterilir.
 */
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; mock.timers.reset(); });

const enc = new TextEncoder();
const ev = (type: string, data: object) => `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`;
const health = () => Response.json({ status: "ok" });

/** Parçaları sırayla gönderen akış; `open` ise kapanmaz (iptal/süre testleri için). */
function sse(chunks: string[], { open = false, headers = {} as Record<string, string> } = {}): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      if (!open) controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream", "X-Request-ID": "req-12345678", ...headers } });
}

const CLAIMS = [
  { claim_id: "c1", claim: "Ankara başkenttir.", is_verifiable: true },
  { claim_id: "c2", claim: "Bence güzel.", is_verifiable: false },
];
const R1 = { claim_id: "c1", claim: "Ankara başkenttir.", is_verifiable: true, verdict: "SUPPORTED", explanation: "Doğru [source_1].",
  used_sources: ["source_1"], sources: [{ id: "source_1", url: "https://a.example/1", text: "kanıt" }], status: "ok" };
const R2 = { claim_id: "c2", claim: "Bence güzel.", is_verifiable: false, verdict: null, explanation: null, used_sources: [], sources: [], status: "ok" };

const HAPPY = [
  ev("started", { request_id: "req-12345678" }),
  ev("stage", { stage: "extract", status: "started" }),
  ev("stage", { stage: "extract", status: "finished", ms: 10 }),
  ev("claims", { claims: CLAIMS, extract_ms: 10 }),
  ev("stage", { stage: "verify", status: "started", total: 2 }),
  ": keep-alive\n\n",
  ev("result", { result: R2 }),
  ev("something_new", { x: 1 }),
  ev("result", { result: R1 }),
  ev("stage", { stage: "verify", status: "finished", ms: 20 }),
  ev("done", { partial: false, timings: {}, request_id: "req-12345678" }),
];

function route(stream: () => Response, calls: { url: string; body?: string; signal?: AbortSignal }[] = []) {
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body as string | undefined, signal: init?.signal ?? undefined });
    return url.endsWith("/health") ? health() : stream();
  }) as typeof fetch;
  return calls;
}

const run = (signal = new AbortController().signal, onStage?: (s: AnalysisStage) => void) =>
  httpService("http://backend.test").check({ text: "metin", input_type: "text" }, { signal, onStage });

describe("POST /verify/stream", () => {
  it("yalnızca { text } ile /verify/stream'e gider; sonuçlar iddia sırasıyla döner", async () => {
    const calls = route(() => sse(HAPPY));
    const raw = await run();
    assert.deepEqual(calls.map((c) => c.url), ["http://backend.test/health", "http://backend.test/verify/stream"]);
    assert.deepEqual(JSON.parse(calls[1].body!), { text: "metin" });
    assert.deepEqual(raw, { results: [R1, R2], partial: false });
    const parsed = parseCheckResponse(raw);
    assert.equal(parsed.claims[0].verdict, "SUPPORTED");
    assert.deepEqual(parsed.unverifiable, ["Bence güzel."]);
  });

  it("olay bir parçanın ortasında bölünse de doğru okunur", async () => {
    const whole = HAPPY.join("");
    const pieces = whole.match(/[\s\S]{1,7}/g)!;
    route(() => sse(pieces));
    assert.deepEqual(await run(), { results: [R1, R2], partial: false });
  });

  it("aşamaları backend'in bildirdiği sırayla verir: ayrıştırma, kaynak arama, ilk hükümde karşılaştırma", async () => {
    route(() => sse(HAPPY));
    const stages: AnalysisStage[] = [];
    await run(undefined, (s) => stages.push(s));
    assert.deepEqual(stages, ["extracting_claims", "retrieving_evidence", "verifying"]);
  });

  it("error olayı ApiRequestError olur (kod eşlenir, destek kodu korunur)", async () => {
    route(() => sse([ev("started", { request_id: "req-12345678" }), ev("error", { error: "EXTRACTION_FAILED", message: "İddialar ayrıştırılamadı.", request_id: "req-12345678" })]));
    await assert.rejects(run(), (e: unknown) => e instanceof ApiRequestError && e.code === "SERVICE_UNAVAILABLE" && e.requestId === "req-12345678");
  });

  it("akış başlamadan gelen HTTP hatası eskisi gibi çevrilir (yedek /verify denenmez)", async () => {
    const calls = route(() => Response.json({ status: "error", error: "BUSY", message: "x" }, { status: 429 }));
    await assert.rejects(run(), (e: unknown) => e instanceof ApiRequestError && e.code === "SERVER_BUSY");
    assert.equal(calls.filter((c) => c.url.endsWith("/verify")).length, 0);
  });

  it("/verify/stream yoksa (404) eski POST /verify kullanılır", async () => {
    const calls: { url: string }[] = [];
    globalThis.fetch = (async (url: string) => {
      calls.push({ url });
      if (url.endsWith("/health")) return health();
      if (url.endsWith("/verify/stream")) return Response.json({ detail: "Not Found" }, { status: 404 });
      return Response.json({ results: [R1] });
    }) as typeof fetch;
    assert.deepEqual(await run(), { results: [R1] });
    assert.deepEqual(calls.map((c) => c.url), ["http://backend.test/health", "http://backend.test/verify/stream", "http://backend.test/verify"]);
  });

  it("akış yerine düz JSON gelirse eskisi gibi okunur", async () => {
    route(() => Response.json({ results: [R1] }));
    assert.deepEqual(await run(), { results: [R1] });
  });

  it("done gelmeden bağlantı kapanırsa NETWORK hatası", async () => {
    route(() => sse(HAPPY.slice(0, 7)));
    await assert.rejects(run(), (e: unknown) => e instanceof ApiRequestError && e.code === "NETWORK");
  });

  it("kullanıcı vazgeçince istek iptal edilir (backend bağlantı kopunca işi durdurur)", async () => {
    const calls = route(() => sse(HAPPY.slice(0, 3), { open: true }));
    const ctrl = new AbortController();
    const p = run(ctrl.signal);
    await new Promise((r) => setTimeout(r, 10));
    ctrl.abort();
    await assert.rejects(p, { name: "AbortError" });
    assert.equal(calls[1].signal?.aborted, true, "stream isteğinin sinyali iptal edilmeli");
  });

  it("belirli süre hiç veri gelmezse (keep-alive dahil) TIMEOUT", async () => {
    mock.timers.enable({ apis: ["setTimeout"] });
    route(() => sse(HAPPY.slice(0, 3), { open: true }));
    const p = assert.rejects(run(), (e: unknown) => e instanceof ApiRequestError && e.code === "TIMEOUT");
    for (let i = 0; i < 5; i++) await new Promise<void>((r) => setImmediate(r));
    mock.timers.tick(STREAM_IDLE_TIMEOUT_MS);
    await p;
  });

  it("boşta kalma süresi, backend'in keep-alive aralığından (15 sn) uzun ve toplam sınırdan kısa", () => {
    assert.ok(STREAM_IDLE_TIMEOUT_MS > 2 * 15_000 && STREAM_IDLE_TIMEOUT_MS < REQUEST_TIMEOUT_MS);
  });
});
