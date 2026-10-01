import assert from "node:assert/strict";
import { afterEach, before, beforeEach, describe, it, mock } from "node:test";

// API_BASE_URL modül yüklenirken okunur; import'tan ÖNCE ayarlanmalı.
process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend.test/";
let checkInput: typeof import("@/lib/api").checkInput;
let ApiRequestError: typeof import("@/lib/errors").ApiRequestError;
before(async () => {
  ({ checkInput } = await import("@/lib/api"));
  ({ ApiRequestError } = await import("@/lib/errors"));
});

const REQ = { mode: "text" as const, content: "iddia" };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const okBody = { claims: [{ id: "c1", text: "t", verdict: "SUPPORTED", explanation: "e [k1]", sources: [{ id: "k1", url: "https://a.example", text: "m" }] }] };

async function codeOf(p: Promise<unknown>): Promise<string> {
  try {
    await p;
  } catch (e) {
    assert.ok(e instanceof ApiRequestError, "ApiRequestError bekleniyordu");
    return e.code;
  }
  return "NO_ERROR";
}

describe("checkInput (gerçek API yolu)", () => {
  const realFetch = globalThis.fetch;
  beforeEach(() => mock.timers.enable({ apis: ["setTimeout"] }));
  afterEach(() => {
    globalThis.fetch = realFetch;
    mock.timers.reset();
  });

  it("başarılı cevabı çevirir ve doğru gövdeyi gönderir", async () => {
    let sent: { url: string; body: string } | undefined;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      sent = { url, body: String(init.body) };
      return json(200, okBody);
    }) as typeof fetch;
    const r = await checkInput(REQ, new AbortController().signal);
    assert.equal(r.claims[0].sources.length, 1);
    assert.equal(sent?.url, "http://backend.test/check");
    assert.deepEqual(JSON.parse(sent!.body), { text: "iddia", input_type: "text" });
  });

  it("backend hata kodunu korur", async () => {
    globalThis.fetch = (async () => json(422, { error: { code: "URL_UNREADABLE", message: "x" } })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "URL_UNREADABLE");
  });

  it("tanımadığı kodu ve JSON olmayan 500 cevabını INTERNAL_ERROR yapar", async () => {
    globalThis.fetch = (async () => json(500, { error: { code: "WEIRD" } })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "INTERNAL_ERROR");
    globalThis.fetch = (async () => new Response("<html>boom</html>", { status: 500 })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "INTERNAL_ERROR");
  });

  it("bozuk 200 cevabında çökmez, INTERNAL_ERROR verir", async () => {
    globalThis.fetch = (async () => json(200, { claims: [{}] })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "INTERNAL_ERROR");
  });

  it("ağ hatasını NETWORK yapar", async () => {
    globalThis.fetch = (async () => {
      throw new TypeError("fetch failed");
    }) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "NETWORK");
  });

  it("zaman aşımında TIMEOUT verir", async () => {
    globalThis.fetch = ((_: string, init: RequestInit) =>
      new Promise((_, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      })) as typeof fetch;
    const p = codeOf(checkInput(REQ, new AbortController().signal));
    mock.timers.tick(90_000);
    assert.equal(await p, "TIMEOUT");
  });

  it("kullanıcı vazgeçince TIMEOUT/NETWORK diye yanlış hata üretmez", async () => {
    globalThis.fetch = ((_: string, init: RequestInit) =>
      new Promise((_, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      })) as typeof fetch;
    const user = new AbortController();
    const p = checkInput(REQ, user.signal);
    user.abort();
    await assert.rejects(p, (e: unknown) => !(e instanceof ApiRequestError));
  });
});
