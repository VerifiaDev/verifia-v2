import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { ProcessDemo } from "@/components/ProcessDemo";
import { curatedSample } from "@/lib/sample-report";
import { VERDICT_META } from "@/lib/format";

describe("Nasıl çalışır canlandırması", () => {
  const html = renderToStaticMarkup(<ProcessDemo />);
  it("sunucu çıktısı son hâldir (JS yokken ya da hareket azaltmada içerik görünür)", () => {
    assert.match(html, /data-phase="idle"/);
    assert.ok(!html.includes("Yeniden oynat"), "oynatma düğmesi yalnızca hareket mümkünse görünür");
  });
  it("içerik uydurma değil: iddialar ve sonuçlar kaynaklı Apollo 11 örneğiyle aynı", () => {
    const sample = curatedSample();
    for (const c of sample.claims) {
      assert.ok(html.includes(c.text.replace(/'/g, "&#x27;")), c.text);
      assert.ok(html.includes(VERDICT_META[c.verdict].label), VERDICT_META[c.verdict].label);
    }
    for (const u of sample.unverifiable) assert.ok(html.includes(u), u);
    assert.ok(html.includes('href="/ornek/apollo-11"'));
  });
});
