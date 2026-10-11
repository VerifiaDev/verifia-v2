import assert from "node:assert/strict";
import { before, describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

// Yayın adresi modül yüklenirken okunur (lib/site.ts); import'tan ÖNCE ayarlanmalı.
process.env.VERCEL_PROJECT_PRODUCTION_URL = "verify.example";
let SamplePage: typeof import("@/app/ornek/apollo-11/page").default;
let config: typeof import("@/lib/config");
let sitemap: typeof import("@/app/sitemap").default;
before(async () => {
  SamplePage = (await import("@/app/ornek/apollo-11/page")).default;
  config = await import("@/lib/config");
  sitemap = (await import("@/app/sitemap")).default;
});

describe("örnek rapor sayfası (/ornek/apollo-11)", () => {
  it("raporu sunucuda çizer: JavaScript olmadan da başlık, üç iddia ve kaynak bağlantıları HTML'dedir", () => {
    const html = renderToStaticMarkup(<SamplePage />);
    assert.ok(html.includes("Apollo 11: bir metin, üç iddia"));
    for (const text of ["20 Temmuz 1969&#x27;da Ay&#x27;a indi", "üç astronot da Ay yüzeyinde yürüdü", "astronomiye ilgi iki katına çıktı"]) {
      assert.ok(html.includes(text), text);
    }
    assert.ok(html.includes('href="https://www.nasa.gov/history/apollo-11-mission-overview/"'));
  });
  it("gerçek bir inceleme gibi sunulmaz: örnek olduğunu söyler ve her iddia 'Örnek veri' etiketi taşır", () => {
    const html = renderToStaticMarkup(<SamplePage />);
    assert.ok(html.includes("canlı analiz değildir"));
    assert.equal((html.match(/class="sample-badge"/g) ?? []).length, 3);
  });
  it("tek bir sayfa başlığı (h1) vardır ve ana sayfaya dönüş bağlantısı içerir", () => {
    const html = renderToStaticMarkup(<SamplePage />);
    assert.equal((html.match(/<h1/g) ?? []).length, 1);
    assert.match(html, /<a[^>]*href="\/"/);
  });
  it("paylaşım bağlantısı bu sayfanın tam adresidir ve site haritasında yer alır", () => {
    assert.equal(config.sampleReportUrl("https://verify.example"), "https://verify.example/ornek/apollo-11");
    assert.ok(sitemap().some((e) => e.url === "https://verify.example/ornek/apollo-11"));
  });
});
