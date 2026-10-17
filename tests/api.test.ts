import assert from "node:assert/strict";
import { afterEach, before, beforeEach, describe, it, mock } from "node:test";

// API_BASE_URL modül yüklenirken okunur; import'tan ÖNCE ayarlanmalı.
process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend.test";
let checkInput: typeof import("@/lib/api").checkInput;
let warmUp: typeof import("@/lib/api").warmUp;
let ApiRequestError: typeof import("@/lib/api/errors").ApiRequestError;
before(async () => {
  ({ checkInput, warmUp } = await import("@/lib/api"));
  ({ ApiRequestError } = await import("@/lib/api/errors"));
});

const REQ = { mode: "text" as const, content: "iddia" };
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const okBody = { claims: [{ id: "c1", text: "t", verdict: "SUPPORTED", explanation: "e [k1]", sources: [{ id: "k1", url: "https://a.example", text: "m" }] }] };

/** Bekleyen promise zincirlerinin ilerlemesini sağlar (sahte zamanlayıcı ilerletilmeden önce). */
const flush = () => new Promise<void>((r) => setImmediate(r));

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
      if (url.endsWith("/health")) return json(200, { status: "ok" });
      sent = { url, body: String(init.body) };
      return json(200, okBody);
    }) as typeof fetch;
    const r = await checkInput(REQ, new AbortController().signal);
    assert.equal(r.claims[0].sources.length, 1);
    assert.equal(sent?.url, "http://backend.test/verify");
    assert.deepEqual(JSON.parse(sent!.body), { text: "iddia" });
  });

  it("bağlantı (url) modunu sunucuya göndermeden açık hata olarak reddeder", async () => {
    let called = false;
    globalThis.fetch = (async () => {
      called = true;
      return json(200, okBody);
    }) as typeof fetch;
    const code = await codeOf(checkInput({ ...REQ, mode: "url", content: "https://a.example" }, new AbortController().signal));
    // "Sayfa açılamadı" (URL_UNREADABLE) demek yanlış olurdu: sayfa hiç denenmedi, özellik desteklenmiyor.
    assert.equal(code, "URL_UNSUPPORTED");
    assert.equal(called, false);
  });

  it("backend hata kodunu korur", async () => {
    globalThis.fetch = (async () => json(422, { error: { code: "URL_UNREADABLE", message: "x" } })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "URL_UNREADABLE");
  });

  it("429 cevabını sunucu hatası yerine kullanım sınırı olarak gösterir", async () => {
    globalThis.fetch = (async () => json(429, { detail: "Too many requests" })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "RATE_LIMITED");
  });

  it("gerçek backend hata gövdesini (error düz yazı) kodlara çevirir", async () => {
    const cases: [number, string, string][] = [
      [422, "VALIDATION_ERROR", "INVALID_INPUT"],
      [400, "EMPTY_TEXT", "INVALID_INPUT"],
      [500, "VERIFY_FAILED", "INTERNAL_ERROR"],
      // docs/BACKEND_TODO.md'de önerilen kodlar
      [413, "TEXT_TOO_LONG", "INPUT_TOO_LONG"],
      [429, "RATE_LIMITED", "RATE_LIMITED"],
      [429, "BUSY", "SERVER_BUSY"],
      [429, "DAILY_QUOTA_EXCEEDED", "QUOTA_EXCEEDED"],
      [503, "UPSTREAM_UNAVAILABLE", "SERVICE_UNAVAILABLE"],
      // backend_v2 (MertBulut11/verify-v2)
      [504, "EXTRACTION_TIMEOUT", "TIMEOUT"],
      [502, "EXTRACTION_FAILED", "SERVICE_UNAVAILABLE"],
      [503, "CONFIG_ERROR", "SERVICE_UNAVAILABLE"],
    ];
    for (const [status, error, expected] of cases) {
      globalThis.fetch = (async () => json(status, { status: "error", error, message: "x" })) as typeof fetch;
      assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), expected, error);
    }
  });

  it("tanımadığı kodu ve JSON olmayan 500 cevabını INTERNAL_ERROR yapar", async () => {
    globalThis.fetch = (async () => json(500, { error: { code: "WEIRD" } })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "INTERNAL_ERROR");
    globalThis.fetch = (async () => new Response("<html>boom</html>", { status: 500 })) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "INTERNAL_ERROR");
  });

  it("hata gövdesi sözleşmeye uymuyorsa HTTP durum koduna göre anlamlı hata seçer", async () => {
    // FastAPI'nin varsayılan doğrulama hatası: 422 + { detail: [...] }. "Sorun girdinizde değil" demek yanlış olurdu.
    const cases: [number, unknown, string][] = [
      [422, { detail: [{ loc: ["body", "text"], msg: "field required" }] }, "INVALID_INPUT"],
      [400, { detail: "bad request" }, "INVALID_INPUT"],
      [413, null, "INPUT_TOO_LONG"],
      [504, null, "TIMEOUT"],
      [408, null, "TIMEOUT"],
      [503, null, "SERVICE_UNAVAILABLE"],
      [502, null, "SERVICE_UNAVAILABLE"],
      [429, { detail: "Too Many Requests" }, "RATE_LIMITED"],
      [500, null, "INTERNAL_ERROR"],
      [404, { detail: "Not Found" }, "INTERNAL_ERROR"],
    ];
    for (const [status, body, expected] of cases) {
      globalThis.fetch = (async () => json(status, body)) as typeof fetch;
      assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), expected, String(status));
    }
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
    globalThis.fetch = ((url: string, init: RequestInit) =>
      url.endsWith("/health")
        ? Promise.resolve(json(200, { status: "ok" }))
        : new Promise((_, reject) => {
            init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          })) as typeof fetch;
    const p = codeOf(checkInput(REQ, new AbortController().signal));
    await flush();
    mock.timers.tick(90_000);
    assert.equal(await p, "TIMEOUT");
  });

  it("sağlık denetimi süresinde yanıt gelmezse inceleme isteğini HİÇ göndermez (SERVER_BUSY)", async () => {
    const urls: string[] = [];
    globalThis.fetch = ((url: string, init: RequestInit) => {
      urls.push(url);
      return new Promise((_, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    }) as typeof fetch;
    const p = codeOf(checkInput(REQ, new AbortController().signal));
    await flush();
    mock.timers.tick(150_000);
    assert.equal(await p, "SERVER_BUSY");
    assert.deepEqual(urls, ["http://backend.test/health"]);
  });

  it("uyuyan sunucu 132 saniyede yanıt verirse vazgeçmez; incelemeyi gönderir (11 Ekim ölçümü)", async () => {
    const urls: string[] = [];
    globalThis.fetch = ((url: string, init: RequestInit) => {
      urls.push(url);
      if (!url.endsWith("/health")) return Promise.resolve(json(200, okBody));
      return new Promise((resolve, reject) => {
        setTimeout(() => resolve(json(200, { status: "ok" })), 132_000);
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    }) as typeof fetch;
    const p = checkInput(REQ, new AbortController().signal);
    await flush();
    mock.timers.tick(132_000);
    const r = await p;
    assert.equal(r.claims.length, 1);
    assert.deepEqual(urls, ["http://backend.test/health", "http://backend.test/verify"]);
  });

  it("sağlık yanıtı 5 saniyede gelmezse beklendiğini bildirir; yanıt gelince bildirimi kaldırır", async () => {
    const waits: boolean[] = [];
    globalThis.fetch = ((url: string, init: RequestInit) => {
      if (!url.endsWith("/health")) return Promise.resolve(json(200, okBody));
      return new Promise((resolve, reject) => {
        setTimeout(() => resolve(json(200, { status: "ok" })), 40_000);
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    }) as typeof fetch;
    const p = checkInput(REQ, new AbortController().signal, undefined, (waiting) => waits.push(waiting));
    await flush();
    mock.timers.tick(4_999);
    assert.deepEqual(waits, []);
    mock.timers.tick(1);
    assert.deepEqual(waits, [true]);
    mock.timers.tick(35_000);
    await p;
    assert.deepEqual(waits, [true, false]);
  });

  it("sağlık yanıtı hemen gelirse bekleme bildirilmez", async () => {
    const waits: boolean[] = [];
    globalThis.fetch = (async (url: string) => (url.endsWith("/health") ? json(200, { status: "ok" }) : json(200, okBody))) as typeof fetch;
    await checkInput(REQ, new AbortController().signal, undefined, (waiting) => waits.push(waiting));
    mock.timers.tick(10_000);
    assert.deepEqual(waits, []);
  });

  it("sağlık adresi hata kodu dönse de (404) incelemeyi gönderir; ağ hatasında NETWORK verir ve göndermez", async () => {
    const urls: string[] = [];
    globalThis.fetch = (async (url: string) => {
      urls.push(url);
      return url.endsWith("/health") ? json(404, { detail: "Not Found" }) : json(200, okBody);
    }) as typeof fetch;
    const r = await checkInput(REQ, new AbortController().signal);
    assert.equal(r.claims.length, 1);
    assert.deepEqual(urls, ["http://backend.test/health", "http://backend.test/verify"]);

    urls.length = 0;
    globalThis.fetch = (async (url: string) => {
      urls.push(url);
      throw new TypeError("fetch failed");
    }) as typeof fetch;
    assert.equal(await codeOf(checkInput(REQ, new AbortController().signal)), "NETWORK");
    assert.deepEqual(urls, ["http://backend.test/health"]);
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

describe("ön ısıtma (sayfa açılınca uyuyan sunucuyu uyandırır)", () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = realFetch;
  });

  it("yalnızca GET /health gönderir; inceleme isteği göndermez", async () => {
    const calls: { url: string; method?: string }[] = [];
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method });
      return json(200, { status: "ok" });
    }) as typeof fetch;
    warmUp();
    await flush();
    assert.deepEqual(calls, [{ url: "http://backend.test/health", method: "GET" }]);
  });

  it("sunucuya ulaşılamasa da hata fırlatmaz (sayfa açılışı bozulmaz)", async () => {
    globalThis.fetch = (async () => {
      throw new TypeError("fetch failed");
    }) as typeof fetch;
    assert.doesNotThrow(() => warmUp());
    await flush(); // yakalanmamış bir ret burada testi düşürürdü
  });
});

describe("httpService adresi", () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = realFetch;
  });

  it("adresin sonundaki eğik çizgiyi atar (//verify oluşmaz)", async () => {
    const { httpService } = await import("@/lib/api/http");
    const urls: string[] = [];
    globalThis.fetch = (async (url: string) => {
      urls.push(url);
      return json(200, okBody);
    }) as typeof fetch;
    for (const base of ["http://backend.test/", "http://backend.test//", "http://backend.test"]) {
      await httpService(base).check({ text: "iddia", input_type: "text" }, { signal: new AbortController().signal });
    }
    assert.deepEqual(urls, [
      "http://backend.test/health",
      "http://backend.test/verify",
      "http://backend.test/health",
      "http://backend.test/verify",
      "http://backend.test/health",
      "http://backend.test/verify",
    ]);
  });
});
