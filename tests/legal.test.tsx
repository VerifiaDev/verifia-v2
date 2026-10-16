import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import PrivacyPage, { metadata as privacyMeta } from "@/app/gizlilik/page";
import TermsPage, { metadata as termsMeta } from "@/app/kullanim-kosullari/page";
import CookiesPage, { metadata as cookiesMeta } from "@/app/cerez-politikasi/page";
import { Footer } from "@/components/Footer";
import { VerificationInput } from "@/components/VerificationInput";
import { COOKIES_PATH, LEGAL, LEGAL_COMPLETE, LEGAL_MISSING, LEGAL_PAGES, PRIVACY_PATH, TERMS_PATH, joinNames, legalPagesHidden } from "@/lib/legal";
import { sitemapEntries } from "@/lib/seo";

const pages = [
  { name: "gizlilik", render: () => renderToStaticMarkup(<PrivacyPage />), meta: privacyMeta },
  { name: "koşullar", render: () => renderToStaticMarkup(<TermsPage />), meta: termsMeta },
  { name: "çerez", render: () => renderToStaticMarkup(<CookiesPage />), meta: cookiesMeta },
];

describe("yasal sayfalar", () => {
  it("gizlilik politikası KVKK m.10 başlıklarını ve koddan bilinen veri akışını içerir", () => {
    const html = renderToStaticMarkup(<PrivacyPage />);
    for (const s of ["Veri sorumlusu", "hukuki sebep", "m.5/2-c", "m.5/2-f", "Render", "Groq", "Tavily", "Vercel", "yurt dışına aktarılır", "7 ile 30 gün", "11. maddesine", "30 gün içinde", "Kişisel Verileri Koruma Kurulu"]) {
      assert.ok(html.includes(s), s);
    }
  });
  it("hizmeti sunan ekip ve üyeleri her sayfada yazılıdır", () => {
    assert.equal(joinNames(["A", "B", "C"]), "A, B ve C");
    for (const p of pages) {
      const html = p.render();
      if (p.name !== "çerez") assert.ok(html.includes(`Bu site, ${LEGAL.owner}nin (${joinNames(LEGAL.members)}) ticari olmayan bir projesidir.`), p.name);
    }
    assert.ok(renderToStaticMarkup(<Footer />).includes(joinNames(LEGAL.members)));
  });
  it("kullanım koşulları: kesin hüküm değil, ücretsiz ve iade yok, Türk hukuku", () => {
    const html = renderToStaticMarkup(<TermsPage />);
    for (const s of ["Sonuçlar kesin hüküm değildir", "Ücret ve iade", "verify ücretsizdir", "iade politikası yoktur", "Türkiye Cumhuriyeti hukuku"]) assert.ok(html.includes(s), s);
  });
  it("çerez politikası: çerez yok, tek kayıt tema tercihi, onay penceresinin neden olmadığı", () => {
    const html = renderToStaticMarkup(<CookiesPage />);
    for (const s of ["verify çerez kullanmaz", "verify-theme", "Yalnızca siz düğmeye bastığınızda", "Neden çerez onayı istemiyoruz?"]) assert.ok(html.includes(s), s);
  });
  it("her sayfa diğer iki yasal sayfaya ve ana sayfaya bağlanır; dış bağlantılar yeni sekmede açıldığını söyler", () => {
    for (const p of pages) {
      const html = p.render();
      const others = LEGAL_PAGES.filter((l) => !html.includes(`<h1 class="t-display">${l.label}</h1>`));
      assert.equal(others.length, 2, p.name);
      for (const l of others) assert.ok(html.includes(`href="${l.path}"`), `${p.name} → ${l.path}`);
      for (const ext of html.match(/<a [^>]*target="_blank"[^>]*>[\s\S]*?<\/a>/g) ?? []) {
        assert.ok(ext.includes('rel="noopener noreferrer"') && ext.includes("yeni sekmede açılır"), ext);
      }
    }
  });
  it("eksik bilgi uydurulmaz: açıkça işaretlenir, taslak uyarısı taşır, dizine kapalıdır ve hiçbir yerden bağlantı verilmez", () => {
    if (LEGAL_COMPLETE) {
      for (const p of pages) {
        const html = p.render();
        assert.ok(!html.includes("[doldurulacak") && !html.includes("Taslak"), p.name);
        assert.equal(p.meta.robots, undefined);
      }
      return;
    }
    assert.deepEqual(LEGAL_MISSING, ["email"]);
    for (const p of pages) {
      const html = p.render();
      assert.ok(html.includes("[doldurulacak: iletişim e-postası]") && html.includes("Taslak"), p.name);
      assert.deepEqual(p.meta.robots, { index: false, follow: false }, p.name);
    }
    const footer = renderToStaticMarkup(<Footer />);
    const form = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />);
    for (const path of [PRIVACY_PATH, TERMS_PATH, COOKIES_PATH]) {
      assert.ok(!footer.includes(`href="${path}"`) && !form.includes(`href="${path}"`), path);
      assert.ok(!sitemapEntries("https://ornek.test").some((e) => e.url.endsWith(path)), path);
    }
    assert.ok(footer.includes('href="#gizlilik"'));
  });
  it("bilgiler eksikken yalnızca yayındaki sitede gizlenir (önizleme ve yerelde taslak görünür)", () => {
    const old = process.env.VERCEL_ENV;
    try {
      process.env.VERCEL_ENV = "production";
      assert.equal(legalPagesHidden(), !LEGAL_COMPLETE);
      process.env.VERCEL_ENV = "preview";
      assert.equal(legalPagesHidden(), false);
    } finally {
      if (old === undefined) delete process.env.VERCEL_ENV;
      else process.env.VERCEL_ENV = old;
    }
  });
});
