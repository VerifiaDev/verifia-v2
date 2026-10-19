import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { EvidenceCard } from "@/components/EvidenceCard";
import { parseCheckResponse } from "@/lib/api/adapter";
import { reportText } from "@/lib/report";
import type { CheckResult, Source } from "@/lib/types";

/**
 * Arama servisinin özetinden gelen pasaj (`excerpt_kind: "snippet"`) kaynaktan alıntı gibi gösterilmez:
 * tırnak ve blockquote yok, ne olduğunu söyleyen bir etiket var. Alan yoksa pasaj eskisi gibi alıntıdır.
 */
const SNIPPET_LABEL = "Arama motorunun özeti; kaynak sayfada bu sözcüklerle geçmeyebilir";

const source = (o: Partial<Source> = {}): Source => ({
  id: "source_1",
  url: "https://haber.example/a",
  name: "Haber",
  publishedAt: null,
  excerpt: "Ankara nüfusu beş milyonu aştı.",
  ...o,
});

const card = (s: Source) => renderToStaticMarkup(<EvidenceCard source={s} number={1} claimId="c1" />);

describe("excerpt_kind: snippet", () => {
  it("adapter snippet değerini okur, summary ve alan yokluğu değişmez", () => {
    const result = parseCheckResponse({ results: [{ claim: "İddia", verdict: "SUPPORTED", sources: [
      { id: "source_1", url: "https://a.example/1", text: "özet", excerpt_kind: "snippet" },
      { id: "source_2", url: "https://b.example/2", text: "özet", excerpt_kind: "summary" },
      { id: "source_3", url: "https://c.example/3", text: "sayfa metni" },
    ] }] });
    assert.deepEqual(result.claims[0].sources.map((s) => s.excerptKind), ["snippet", "summary", undefined]);
  });

  it("snippet tırnak içinde alıntı olarak çizilmez ve etiketlenir", () => {
    const html = card(source({ excerptKind: "snippet" }));
    assert.ok(!html.includes("<blockquote"), html);
    assert.ok(!html.includes("“"), html);
    assert.ok(html.includes(SNIPPET_LABEL), html);
    assert.ok(html.includes("Ankara nüfusu beş milyonu aştı."), html);
  });

  it("uzun snippet'in önizlemesi ve tamamı da alıntı olarak çizilmez", () => {
    const html = card(source({ excerptKind: "snippet", excerpt: "Uzun özet cümlesi. ".repeat(40) }));
    assert.ok(html.includes("Pasajın tamamını göster"), "uzun pasaj açılır bölümle gösterilir");
    assert.ok(!html.includes("<blockquote"), html);
  });

  it("excerpt_kind gelmeyen pasaj eskisi gibi alıntıdır", () => {
    const html = card(source());
    assert.ok(html.includes("<blockquote"), html);
    assert.ok(html.includes("“Ankara nüfusu beş milyonu aştı.”"), html);
    assert.ok(!html.includes(SNIPPET_LABEL), html);
  });

  it("kopyalanan raporda snippet etiketi korunur", () => {
    const result: CheckResult = {
      claims: [{ id: "c1", text: "İddia", verdict: "SUPPORTED", explanation: "Açıklama [source_1].", confidence: null,
        sources: [source({ excerptKind: "snippet" })] }],
      unverifiable: [],
      unreadable: [],
    };
    assert.ok(reportText(result).includes(`${SNIPPET_LABEL}: Ankara nüfusu beş milyonu aştı.`));
  });
});
