import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { AnalysisProgress } from "@/components/AnalysisProgress";
import { ClaimItem } from "@/components/ClaimItem";
import { ErrorState } from "@/components/ErrorState";
import { ResultView } from "@/components/ResultView";
import { ERROR_COPY, VERDICT_META } from "@/lib/format";
import type { Claim, ErrorCode, Source, Verdict } from "@/lib/types";

const source = (n: number, o: Partial<Source> = {}): Source => ({
  id: `kaynak_${n}`,
  url: `https://ornek${n}.example/haber`,
  name: `Kaynak ${n}`,
  publishedAt: "2025-03-14",
  excerpt: `Pasaj ${n}`,
  ...o,
});
const claim = (o: Partial<Claim> = {}): Claim => ({
  id: "c1",
  text: "İddia",
  verdict: "SUPPORTED",
  explanation: "Açıklama [kaynak_1].",
  sources: [source(1)],
  confidence: null,
  ...o,
});
const render = (c: Claim) => renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />);

describe("ClaimItem", () => {
  it("her sonuç türünü simge + yazıyla gösterir (yalnızca renk değil)", () => {
    for (const v of Object.keys(VERDICT_META) as Verdict[]) {
      const html = render(claim({ verdict: v }));
      assert.ok(html.includes(VERDICT_META[v].label), v);
      assert.ok(html.includes(VERDICT_META[v].symbol), v);
    }
  });
  it("kaynak yoksa 'kaynak bulunamadı' der ve 'yanlış' demez", () => {
    const html = render(claim({ verdict: "NOT_ENOUGH_EVIDENCE", sources: [], explanation: "" }));
    assert.ok(html.includes("Kaynak bulunamadı"));
    assert.ok(html.includes("yanlış olduğu anlamına gelmez"));
  });
  it("açıklama boşsa bunu söyler", () => {
    assert.ok(render(claim({ explanation: "" })).includes("açıklama gelmedi"));
  });
  it("listede olmayan atıfı bağlantıya çevirmez", () => {
    const html = render(claim({ explanation: "Şöyle [kaynak_9]." }));
    assert.ok(html.includes("[kaynak_9]"));
    assert.ok(!html.includes('href="#src-c1-9"'));
  });
  it("güvensiz bağlantıyı (javascript:) tıklanabilir yapmaz", () => {
    const html = render(claim({ sources: [source(1, { url: "javascript:alert(1)" })] }));
    assert.ok(!html.includes('href="javascript:'));
    assert.ok(html.includes("Bağlantı geçersiz"));
  });
  it("çok uzun iddiayı ve kaynak adını çökmeden gösterir; alıntıyı keser", () => {
    const html = render(claim({ text: "uzun ".repeat(400), sources: [source(1, { name: "A".repeat(500), excerpt: "b ".repeat(500) })] }));
    assert.ok(html.includes("A".repeat(500)));
    assert.ok(html.includes("…"));
  });
  it("tarih ve ad yoksa alan adını ve 'belirtilmemiş' metnini gösterir", () => {
    const html = render(claim({ sources: [source(1, { name: null, publishedAt: null, excerpt: null })] }));
    assert.ok(html.includes("ornek1.example"));
    assert.ok(html.includes("Yayın tarihi belirtilmemiş"));
    assert.ok(html.includes("alıntı gelmedi"));
  });
  it("güven puanı varsa yüzde olarak ve 'olasılık değildir' notuyla gösterir", () => {
    const html = render(claim({ confidence: 0.91 }));
    assert.ok(html.includes("%91"));
    assert.ok(html.includes("Modelin güven puanı"));
    assert.ok(html.includes("doğru olma olasılığı değil"));
  });
  it("güven puanı yoksa hiçbir yüzde ya da puan metni göstermez (uydurmaz)", () => {
    const html = render(claim({ confidence: null }));
    assert.ok(!/güven puanı/i.test(html.replace(/Güven puanı kesinlik/g, "")));
    assert.ok(!/%\s?\d|\d\s?%/.test(html));
  });
  it("0 puanını da doğru gösterir (yok sayılmaz)", () => {
    assert.ok(render(claim({ confidence: 0 })).includes("%0"));
  });
});

describe("ResultView", () => {
  const noop = () => {};
  it("iddia yoksa boş durumu gösterir", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [], unverifiable: [] }} input="x" onReset={noop} />);
    assert.ok(html.includes("Doğrulanabilir iddia bulunamadı"));
  });
  it("birden fazla iddiada özet listesi ve doğrulanmayan ifadeleri gösterir", () => {
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [claim({ id: "a" }), claim({ id: "b", verdict: "CONFLICTING" })], unverifiable: ["Bence harika."] }} input="x" onReset={noop} />,
    );
    assert.ok(html.includes("2 iddia incelendi"));
    assert.ok(html.includes('aria-label="İncelenen iddialar"'));
    assert.ok(html.includes("Bence harika."));
  });
  it("kullanıcı girdisini HTML olarak yorumlamaz", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [], unverifiable: [] }} input="<script>alert(1)</script>" onReset={noop} />);
    assert.ok(!html.includes("<script>alert(1)"));
  });
});

describe("ErrorState ve AnalysisProgress", () => {
  it("her hata kodu 'Ne oldu?' ve 'Şimdi ne yapabilirsiniz?' içerir", () => {
    for (const code of Object.keys(ERROR_COPY) as ErrorCode[]) {
      const html = renderToStaticMarkup(<ErrorState error={{ code, message: "m" }} onRetry={() => {}} onEdit={() => {}} />);
      assert.ok(html.includes("Ne oldu?") && html.includes("Şimdi ne yapabilirsiniz?"), code);
      assert.equal(html.includes("Yeniden dene"), ERROR_COPY[code].retry, code);
    }
  });
  it("aşama bilgisi yokken hiçbir adımı 'şu an' diye işaretlemez; yüzde göstermez", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(!html.includes('aria-current="step"'));
    assert.ok(!/\d\s?%/.test(html));
    assert.ok(html.includes("Vazgeç"));
  });
  it("backend aşama verirse yalnızca o adım işaretlenir", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="retrieving_evidence" onCancel={() => {}} />);
    assert.equal((html.match(/aria-current="step"/g) ?? []).length, 1);
  });
});
