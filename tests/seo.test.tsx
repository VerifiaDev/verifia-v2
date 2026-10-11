import assert from "node:assert/strict";
import { before, describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

// Yayın adresi modül yüklenirken okunur (lib/site.ts); import'tan ÖNCE ayarlanmalı.
process.env.VERCEL_PROJECT_PRODUCTION_URL = "verify.example";
let seo: typeof import("@/lib/seo");
let robots: typeof import("@/app/robots").default;
let sitemap: typeof import("@/app/sitemap").default;
let HomePage: typeof import("@/app/page").default;
before(async () => {
  seo = await import("@/lib/seo");
  robots = (await import("@/app/robots")).default;
  sitemap = (await import("@/app/sitemap")).default;
  HomePage = (await import("@/app/page")).default;
});

describe("robots.txt ve sitemap.xml", () => {
  it("robots tüm sayfalara izin verir ve site haritasının tam adresini gösterir", () => {
    assert.deepEqual(robots(), { rules: { userAgent: "*", allow: "/" }, sitemap: "https://verify.example/sitemap.xml" });
  });
  it("site haritası yalnızca tam (mutlak) adresler içerir ve ana sayfayı listeler", () => {
    const urls = sitemap().map((e) => e.url);
    assert.ok(urls.includes("https://verify.example/"));
    for (const url of urls) assert.match(url, /^https:\/\/verify\.example\//);
  });
  it("yayın adresi bilinmiyorsa (yerel derleme) uydurma adres yazmaz", () => {
    assert.deepEqual(seo.robotsRules(null), { rules: { userAgent: "*", allow: "/" } });
    assert.deepEqual(seo.sitemapEntries(null), []);
  });
});

describe("yapılandırılmış veri (JSON-LD)", () => {
  it("ana sayfa, siteyi bir web uygulaması olarak tanımlayan geçerli JSON-LD taşır", () => {
    const html = renderToStaticMarkup(<HomePage />);
    const block = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
    assert.ok(block, "JSON-LD bloğu yok");
    const data = JSON.parse(block[1]);
    assert.equal(data["@context"], "https://schema.org");
    assert.equal(data["@type"], "WebApplication");
    assert.equal(data.name, "verify");
    assert.equal(data.url, "https://verify.example/");
    assert.equal(data.inLanguage, "tr");
  });
  it("JSON-LD metni <script> etiketini kapatabilecek karakter içermez", () => {
    const text = seo.jsonLdText({ name: "</script><img src=x onerror=alert(1)>" });
    assert.ok(!text.includes("<"));
    assert.deepEqual(JSON.parse(text), { name: "</script><img src=x onerror=alert(1)>" });
  });
});
