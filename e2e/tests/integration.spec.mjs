// Gerçek tarayıcı → gerçek frontend → gerçek backend uygulaması (sahte LLM/arama).
// Sahte servislerin davranışı: backend_v2/tests/fake_server.py ve tests/conftest.py (FakeBackend).
//   Her metin 3 iddia verir: "Ankara ..." (destekleniyor, 2 kaynak), "Bence kahve ..." (doğrulanamaz),
//   "İstanbul ..." (çelişiyor). Metinde KISMI varsa üçüncü iddianın araması hata verir;
//   HATA-AYRISTIRMA varsa iddia ayrıştırma başarısız olur (502 EXTRACTION_FAILED).
import { expect, test } from "@playwright/test";

const BACKEND_URL = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT ?? "8799"}`;

/** Sayfayı açar, backend'e giden istekleri ve konsol/CSP hatalarını toplar. */
async function open(page) {
  const calls = [];
  const problems = [];
  page.on("request", (req) => {
    if (req.url().startsWith(BACKEND_URL)) {
      calls.push({ method: req.method(), path: new URL(req.url()).pathname, body: req.postData() });
    }
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") problems.push(msg.text());
  });
  page.on("pageerror", (err) => problems.push(String(err)));
  await page.goto("/");
  return { calls, problems };
}

async function submit(page, text) {
  const field = page.getByLabel("Haber metnini yapıştır");
  await field.fill(text);
  await page.getByRole("button", { name: "İncelemeyi başlat" }).click();
}

test("metin gönderilir, sonuç backend'den gelen iddialarla gösterilir", async ({ page }) => {
  const { calls, problems } = await open(page);
  const responses = [];
  page.on("response", (res) => {
    if (res.url() === `${BACKEND_URL}/verify/stream`) responses.push(res);
  });

  await submit(page, "Ankara Türkiye'nin başkentidir. İstanbul da başkenttir. Bence kahve güzeldir.");

  const heading = page.getByRole("heading", { level: 2, name: "2 iddia incelendi" });
  await expect(heading).toBeVisible();

  // İstek: önce /health, sonra yalnızca { text } ile POST /verify/stream (akış; eski /verify kullanılmaz)
  expect(calls.filter((c) => c.path === "/verify")).toHaveLength(0);
  const verify = calls.filter((c) => c.path === "/verify/stream");
  expect(verify).toHaveLength(1);
  expect(JSON.parse(verify[0].body)).toEqual({
    text: "Ankara Türkiye'nin başkentidir. İstanbul da başkenttir. Bence kahve güzeldir.",
  });
  const firstVerify = calls.findIndex((c) => c.path === "/verify/stream");
  expect(calls.slice(0, firstVerify).some((c) => c.path === "/health")).toBe(true);

  // Yanıt gerçekten backend'den geldi: olay akışı, üç sonuç ve done (backend_v2/app/streaming.py)
  expect(responses).toHaveLength(1);
  expect(responses[0].status()).toBe(200);
  expect(responses[0].headers()["content-type"]).toContain("text/event-stream");
  expect(responses[0].headers()["x-request-id"]).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
  const events = (await responses[0].text()).split(/\n\n/).filter((b) => b.includes("data:"))
    .map((b) => JSON.parse(b.split(/\n/).find((l) => l.startsWith("data:")).slice(5)));
  expect(events.filter((e) => e.type === "result").map((e) => e.result.status)).toEqual(["ok", "ok", "ok"]);
  expect(events.at(-1)).toMatchObject({ type: "done", partial: false });

  // Arayüz: iki hüküm, doğrulanamayan ifade ayrı bölümde
  // Rapor bölgesi (sayfanın geri kalanında sonuç türlerini anlatan açıklamalar da var)
  const report = page.getByRole("region", { name: "2 iddia incelendi" });
  await expect(report.getByRole("heading", { level: 3, name: "Ankara Türkiye'nin başkentidir." })).toBeVisible();
  await expect(report.getByRole("heading", { level: 3, name: "İstanbul Türkiye'nin başkentidir." })).toBeVisible();
  await expect(report.getByText("Kanıtlar destekliyor").first()).toBeVisible();
  await expect(report.getByText("Kanıtlar iddiayla çelişiyor").first()).toBeVisible();
  await expect(report.getByRole("heading", { level: 4, name: "Dayandığımız kanıtlar (1)" }).first()).toBeVisible();
  await expect(report.getByText("İncelenmeyen ifadeler (1)")).toBeVisible();

  // Kaynaklar: backend'in verdiği adresler, güvenli bağlantı nitelikleriyle
  const link = report.locator('a[href="https://a.example.com/1"]').first();
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /noopener/);
  // [source_1] atfı numaralı bağlantıya çevrildi; uydurma source_99 (used_sources) arayüze yansımaz
  await expect(report.getByText("[source_1]")).toHaveCount(0);
  await expect(report.getByText("source_99")).toHaveCount(0);

  expect(problems, problems.join("\n")).toEqual([]);
});

test("kısmi sonuç: incelenemeyen iddia hüküm olarak değil ayrı listede gösterilir", async ({ page }) => {
  const { problems } = await open(page);
  await submit(page, "KISMI bir metin: Ankara başkenttir, bir de kaynağı bozuk iddia var.");

  await expect(page.getByRole("heading", { level: 2, name: "1 iddia incelendi" })).toBeVisible();
  const report = page.getByRole("region", { name: "1 iddia incelendi" });
  await expect(report.getByRole("heading", { level: 3, name: "Ankara Türkiye'nin başkentidir." })).toBeVisible();
  await expect(report.getByText("İncelenemeyen iddialar (1)")).toBeVisible();
  await expect(report.getByText("BOZUK kaynaklı iddia.")).toBeVisible();
  await expect(report.getByText(/1 iddia incelenemedi/)).toBeVisible();
  // Sonuç özetinde yalnızca incelenen iddianın hükmü var; hata veren iddia hüküm sayılmaz
  const summary = report.getByRole("list", { name: "Sonuç özeti" }).getByRole("listitem");
  await expect(summary).toHaveCount(1);
  await expect(summary).toContainText("Kanıtlar destekliyor");
  expect(problems, problems.join("\n")).toEqual([]);
});

test("backend hatası (EXTRACTION_FAILED olayı) kullanıcıya anlaşılır hata olarak gösterilir", async ({ page }) => {
  const { problems } = await open(page);
  const failed = page.waitForResponse((r) => r.url() === `${BACKEND_URL}/verify/stream`);
  await submit(page, "HATA-AYRISTIRMA bu metin ayrıştırılamaz.");
  const res = await failed;
  // Akışta hata HTTP durumu değil, error olayıdır
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain('"error": "EXTRACTION_FAILED"');

  await expect(page.getByRole("heading", { level: 2, name: "İnceleme servisi geçici olarak kullanılamıyor" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Yeniden dene" })).toBeVisible();
  // Sunucunun ham metni ve teknik ayrıntı gösterilmez
  await expect(page.getByText("fake extraction failure")).toHaveCount(0);
  await expect(page.getByText("İddialar ayrıştırılamadı.")).toHaveCount(0);
  // Tarayıcı 5xx yanıtını konsola yazar; bu beklenen tek hata satırıdır
  expect(problems.filter((p) => !/502/.test(p)), problems.join("\n")).toEqual([]);
});

test("CORS: backend frontend'in kökenine izin verir, başka kökene vermez", async ({ request }) => {
  const ok = await request.fetch(`${BACKEND_URL}/verify`, {
    method: "OPTIONS",
    headers: {
      Origin: "http://localhost:3000",
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "content-type",
    },
  });
  expect(ok.status()).toBe(200);
  expect(ok.headers()["access-control-allow-origin"]).toBe("http://localhost:3000");

  const bad = await request.fetch(`${BACKEND_URL}/verify`, {
    method: "OPTIONS",
    headers: { Origin: "https://kotu.example", "Access-Control-Request-Method": "POST" },
  });
  expect(bad.headers()["access-control-allow-origin"]).toBeUndefined();
});

test("tarayıcıdaki kod X-Request-ID başlığını okuyabilir (hata bildiriminde kimlik göstermek için)", async ({ page }) => {
  await page.goto("/");
  const rid = await page.evaluate(async (url) => {
    const res = await fetch(`${url}/health`, { cache: "no-store" });
    return res.headers.get("x-request-id");
  }, BACKEND_URL);
  expect(rid).toMatch(/^[A-Za-z0-9._-]{8,64}$/);
});

test("CSP: sayfa yalnızca kendi sitesine ve tanımlı backend'e bağlanabilir", async ({ page }) => {
  const res = await page.goto("/");
  const csp = res.headers()["content-security-policy"];
  const connect = csp.split(";").map((s) => s.trim()).find((s) => s.startsWith("connect-src"));
  expect(connect).toBe(`connect-src 'self' ${BACKEND_URL}`);
});
