import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { EvidenceCard } from "@/components/EvidenceCard";
import { curatedSample } from "@/lib/sample-report";
import type { Source } from "@/lib/types";

/**
 * Pasajın alınma yöntemi satırı yalnızca bir şey söylediğinde gösterilir. Editörün Türkçe özeti
 * ("Kaynağın Türkçe özeti") zaten ne olduğunu söyler; pasaj hiç yoksa yöntemi de yoktur.
 */
const UNKNOWN = "Pasajın alınma yöntemi belirtilmedi";
const source = (o: Partial<Source> = {}): Source => ({ id: "s1", url: "https://ornek.example/a", name: "Kaynak", publishedAt: null, excerpt: "Pasaj.", ...o });
const card = (s: Source) => renderToStaticMarkup(<EvidenceCard source={s} number={1} claimId="c1" />);

describe("pasaj yöntemi etiketi", () => {
  it("editör özetinde (excerptKind summary, yöntem yok) yöntem satırı gösterilmez", () => {
    const html = card(source({ excerptKind: "summary" }));
    assert.ok(html.includes("Kaynağın Türkçe özeti"), html);
    assert.ok(!html.includes(UNKNOWN), html);
  });

  it("Apollo 11 örnek raporunda yöntem satırı çıkmaz", () => {
    for (const c of curatedSample().claims) for (const s of c.sources) assert.ok(!card(s).includes(UNKNOWN), s.id);
  });

  it("pasaj yoksa yöntem satırı gösterilmez", () => {
    const html = card(source({ excerpt: null }));
    assert.ok(html.includes("Bu kaynak için alıntı gelmedi."), html);
    assert.ok(!html.includes(UNKNOWN), html);
  });

  it("yöntemi bilinmeyen gerçek pasajda satır gösterilmeye devam eder", () => {
    assert.ok(card(source()).includes(UNKNOWN));
  });

  it("bilinen yöntemler değişmez", () => {
    assert.ok(card(source({ fetchMethod: "tavily_snippet" })).includes("Arama özeti; sayfanın tamamı incelenmedi"));
    assert.ok(card(source({ fetchMethod: "requests" })).includes("Sayfadan seçilen pasaj"));
  });
});
