import assert from "node:assert/strict";
import { it } from "node:test";
import { reportText } from "@/lib/report";
import { curatedSample } from "@/lib/sample-report";

it("kopyalanan rapor örnek etiketini, kaynakları ve sınırlamaları korur", () => {
  const result = curatedSample();
  const text = reportText(result, undefined, true);
  assert.ok(text.includes("Canlı analiz değildir"));
  assert.ok(result.report?.input);
  assert.ok(result.report?.scope);
  assert.ok(text.includes(result.report.input));
  assert.ok(text.includes(result.report.scope));
  for (const claim of result.claims) {
    assert.ok(text.includes(claim.text));
    for (const source of claim.sources) assert.ok(text.includes(source.url));
  }
  assert.ok(text.includes(result.unverifiable[0]));
});

it("dışa aktarılan atıflar kaynak numaralarıyla eşleşir, teknik kimlikler görünmez", () => {
  const text = reportText(curatedSample(), undefined, true);
  assert.ok(text.includes("[1]"));
  assert.ok(text.includes("[2]"));
  assert.ok(text.includes("[1] NASA · Apollo 11 Mission Overview"));
  assert.ok(text.includes("[2] NASA · Apollo 11"));
  assert.ok(!text.includes("nasa_overview"));
  assert.ok(!text.includes("nasa_mission"));
});

it("gerçek ve kısmi sonuç çıktısında gönderilen metin ve okunamayan iddia kaybolmaz", () => {
  const text = reportText({ claims: [], unverifiable: [], unreadable: ["Sonucu okunamayan iddia"] }, "Gönderilen metin");
  assert.ok(text.includes("Gönderilen metin"));
  assert.ok(text.includes("Sonucu okunamayan iddia"));
  assert.ok(!text.includes("Önceden hazırlanmış örnek"));
});
