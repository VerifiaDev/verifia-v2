import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { ClaimItem } from "@/components/ClaimItem";
import { UNCITED_NOTE, isUncitedVerdict } from "@/lib/citations";
import { VERDICT_META } from "@/lib/format";
import { reportText } from "@/lib/report";
import type { CheckResult, Claim, Source, Verdict } from "@/lib/types";

/**
 * Atıfsız hüküm: kaynak bulunmuş, model "destekliyor/çelişiyor" demiş ama açıklama hiçbir kaynağa atıf yapmıyor.
 * Hüküm değiştirilmez (model yanlış değil, yalnızca denetlenemez); iddia satırında ve kopyalanan raporda uyarı gösterilir.
 */
const source = (n: number): Source => ({ id: `source_${n}`, url: `https://ornek${n}.example/haber`, name: `Kaynak ${n}`, publishedAt: null, excerpt: `Pasaj ${n}` });

const claim = (verdict: Verdict, explanation: string, sources = [source(1), source(2)]): Claim => ({
  id: "c1", text: "Ankara Türkiye'nin başkentidir.", verdict, explanation, sources, confidence: null,
});

const render = (c: Claim) => renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />);

describe("atıfsız hüküm uyarısı", () => {
  it("yalnızca kaynağı olan, atıfsız ve kesin hükümler atıfsız sayılır", () => {
    assert.equal(isUncitedVerdict(claim("SUPPORTED", "Kaynaklar doğruluyor.")), true);
    assert.equal(isUncitedVerdict(claim("REFUTED", "Kaynaklar yalanlıyor.")), true);
    assert.equal(isUncitedVerdict(claim("CONFLICTING", "Kaynaklar çelişiyor.")), true);
    assert.equal(isUncitedVerdict(claim("SUPPORTED", "Kaynaklar doğruluyor [source_2].")), false);
    assert.equal(isUncitedVerdict(claim("NOT_ENOUGH_EVIDENCE", "Yeterli bilgi yok.")), false);
    assert.equal(isUncitedVerdict(claim("SUPPORTED", "Kaynak yok.", [])), false, "kaynaksız durumun kendi uyarısı var");
  });

  it("listede olmayan kaynağa atıf, atıf sayılmaz", () => {
    assert.equal(isUncitedVerdict(claim("SUPPORTED", "Doğru [source_9].")), true);
  });

  it("atıf olmayan köşeli parantez ([2023], [sic]) atıf sayılmaz", () => {
    assert.equal(isUncitedVerdict(claim("SUPPORTED", "2023 verisi [2023] böyle diyor [sic].")), true);
  });

  it("açıklama boşsa yalnızca 'gerekçe paylaşılmadı' uyarısı çıkar; ekran ve rapor aynı", () => {
    const empty = claim("SUPPORTED", "");
    assert.equal(isUncitedVerdict(empty), false, "boş açıklamanın kendi uyarısı var");
    const html = render(empty);
    assert.ok(html.includes("Kanıt bilgisi eksik: sonucun gerekçesi paylaşılmadı."), html);
    assert.ok(!html.includes(UNCITED_NOTE), html);
    const text = reportText({ claims: [empty], unverifiable: [], unreadable: [] });
    assert.ok(text.includes("Sonucun gerekçesi paylaşılmadı."), text);
    assert.ok(!text.includes(UNCITED_NOTE), text);
  });

  it("atıfsız hükümde hüküm korunur ve iddia satırında uyarı gösterilir", () => {
    const html = render(claim("SUPPORTED", "Kaynaklar doğruluyor."));
    assert.ok(html.includes(VERDICT_META.SUPPORTED.label), "hüküm değiştirilmez");
    assert.ok(html.includes(`Kanıt bilgisi eksik: ${UNCITED_NOTE}`), html);
  });

  it("atıflı hükümde uyarı yok", () => {
    const html = render(claim("SUPPORTED", "Kaynaklar doğruluyor [source_1]."));
    assert.ok(!html.includes("Kanıt bilgisi eksik"), html);
  });

  it("yeterli kanıt yok sonucunda atıf uyarısı yok", () => {
    const html = render(claim("NOT_ENOUGH_EVIDENCE", "Yeterli bilgi yok."));
    assert.ok(!html.includes(UNCITED_NOTE), html);
  });

  it("kopyalanan raporda da aynı uyarı var", () => {
    const result: CheckResult = { claims: [claim("REFUTED", "Kaynaklar yalanlıyor.")], unverifiable: [], unreadable: [] };
    assert.ok(reportText(result).includes(`Kanıt bilgisi eksik: ${UNCITED_NOTE}`));
  });
});
