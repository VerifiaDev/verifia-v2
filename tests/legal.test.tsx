import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import PrivacyPage, { metadata as privacyMeta } from "@/app/gizlilik/page";
import TermsPage, { metadata as termsMeta } from "@/app/kullanim-kosullari/page";
import { Footer } from "@/components/Footer";
import { LEGAL_COMPLETE, LEGAL_MISSING, PRIVACY_PATH, TERMS_PATH } from "@/lib/legal";

describe("yasal sayfalar", () => {
  it("gizlilik politikası koddan bilinen veri akışını anlatır (Render, Groq, Tavily, Vercel; çerez yok)", () => {
    const html = renderToStaticMarkup(<PrivacyPage />);
    for (const s of ["Gizlilik politikası", "Render", "Groq", "Tavily", "Vercel", "Çerez", "11. maddesi"]) assert.ok(html.includes(s), s);
    assert.ok(html.includes(`href="${TERMS_PATH}"`));
  });
  it("kullanım koşulları sonucun kesin hüküm olmadığını söyler ve gizlilik politikasına bağlanır", () => {
    const html = renderToStaticMarkup(<TermsPage />);
    assert.ok(html.includes("Sonuçlar kesin hüküm değildir"));
    assert.ok(html.includes(`href="${PRIVACY_PATH}"`));
  });
  it("eksik bilgi uydurulmaz: açıkça işaretlenir, sayfa taslak uyarısı taşır ve dizine kapatılır", () => {
    const html = renderToStaticMarkup(<PrivacyPage />);
    if (LEGAL_COMPLETE) {
      assert.ok(!html.includes("[doldurulacak"));
      assert.ok(!html.includes("Taslak"));
      assert.equal(privacyMeta.robots, undefined);
    } else {
      assert.ok(LEGAL_MISSING.length > 0);
      assert.ok(html.includes("[doldurulacak"));
      assert.ok(html.includes("Taslak"));
      assert.deepEqual(privacyMeta.robots, { index: false, follow: false });
      assert.deepEqual(termsMeta.robots, { index: false, follow: false });
    }
  });
  it("alt bilgide iki sayfanın bağlantısı vardır", () => {
    const html = renderToStaticMarkup(<Footer />);
    assert.ok(html.includes(`href="${PRIVACY_PATH}"`));
    assert.ok(html.includes(`href="${TERMS_PATH}"`));
  });
});
