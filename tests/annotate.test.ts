import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { annotateInput } from "@/lib/annotate";
import type { Claim, Verdict } from "@/lib/types";

const claim = (text: string, verdict: Verdict): Claim => ({ id: text, text, verdict, explanation: "", sources: [], confidence: null });
const tones = (input: string, claims: Claim[]) => annotateInput(input, claims).filter((s) => s.tone).map((s) => [s.text, s.tone]);

describe("annotateInput", () => {
  const input = "Ankara başkenttir. Ay peynirden yapılmıştır. Yarın yağmur yağabilir.";
  it("destekleneni yeşil, çelişeni kırmızı boyar; yeterli kanıt olmayan aynı kalır", () => {
    const r = annotateInput(input, [claim("Ankara başkenttir", "SUPPORTED"), claim("Ay peynirden yapılmıştır", "REFUTED"), claim("Yarın yağmur yağabilir", "NOT_ENOUGH_EVIDENCE")]);
    assert.deepEqual(r.filter((s) => s.tone).map((s) => [s.text, s.tone]), [["Ankara başkenttir.", "ok"], ["Ay peynirden yapılmıştır.", "bad"]]);
    assert.equal(r.map((s) => s.text).join(""), input);
  });
  it("kaynaklar birbiriyle çelişiyorsa da kırmızı", () => {
    assert.deepEqual(tones(input, [claim("Ankara başkenttir", "CONFLICTING")]), [["Ankara başkenttir.", "bad"]]);
  });
  it("cümlenin yalnızca bir kısmı yanlışsa sadece o kısım kırmızı, diğeri yeşil", () => {
    const t = "Apollo 11 1969'da indi ve üç astronot yürüdü.";
    assert.deepEqual(tones(t, [claim("Apollo 11 1969'da indi", "SUPPORTED"), claim("üç astronot yürüdü", "REFUTED")]), [["Apollo 11 1969'da indi", "ok"], ["üç astronot yürüdü.", "bad"]]);
  });
  it("çakışmada kırmızı kazanır", () => {
    assert.deepEqual(tones("Ay küçüktür.", [claim("Ay küçüktür", "SUPPORTED"), claim("Ay küçüktür", "REFUTED")]), [["Ay küçüktür.", "bad"]]);
  });
  it("büyük/küçük harf, boşluk ve tırnak farkını tolere eder; eşleşmeyeni tahmin etmez", () => {
    assert.deepEqual(tones("Apollo   11\ninds’a", [claim("apollo 11 inds'a", "SUPPORTED")]), [["Apollo   11\ninds’a", "ok"]]);
    assert.deepEqual(tones("Bambaşka bir metin.", [claim("Ankara başkenttir", "SUPPORTED")]), []);
  });
  it("boş metin boş döner, özel karakterli iddia hata vermez", () => {
    assert.deepEqual(annotateInput("", [claim("x", "SUPPORTED")]), []);
    assert.deepEqual(tones("Fiyat (yaklaşık) 5$ [1]", [claim("Fiyat (yaklaşık) 5$ [1]", "SUPPORTED")]), [["Fiyat (yaklaşık) 5$ [1]", "ok"]]);
  });
});
