import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { citedNumbers, numberCitations, splitIds } from "@/lib/citations";
import { isSubmitShortcut, validateInput } from "@/lib/input";
import { MAX_INPUT_LENGTH } from "@/lib/config";
import type { Source } from "@/lib/types";

const src = (id: string): Source => ({ id, url: `https://${id}.example`, name: null, publishedAt: null, excerpt: null });

describe("citations", () => {
  it("splitIds virgül ve noktalı virgülle ayırır", () => {
    assert.deepEqual(splitIds("kaynak_1, kaynak_2;kaynak_3"), ["kaynak_1", "kaynak_2", "kaynak_3"]);
  });
  it("citedNumbers yalnızca listedeki kaynakları numaralar", () => {
    const s = [src("kaynak_1"), src("kaynak_2")];
    assert.deepEqual(citedNumbers("a [kaynak_2] b [kaynak_1, kaynak_9] c [kaynak_2]", s), [2, 1]);
  });
  it("numberCitations atıf olmayan köşeli parantezleri aynen bırakır; yalnızca kimlik biçimindekileri çevirir", () => {
    const s = [src("kaynak_1"), src("kaynak_2")];
    assert.equal(
      numberCitations("TÜİK [2023] verisi [kaynak_2], alıntı [...] ve [sic]; olmayan [kaynak_9].", s),
      "TÜİK [2023] verisi [2], alıntı [...] ve [sic]; olmayan [Kaynak eşleşmesi bulunamadı].",
    );
  });
  it("kimliği alt çizgisiz olan kaynak da listede varsa atıf sayılır", () => {
    assert.equal(numberCitations("e [k1] ve [k9]", [src("k1")]), "e [1] ve [k9]");
  });
  it("atıf sayılmayan parantezdeki kimlik 'dayanılan kaynak' olarak sayılmaz (ekranla tutarlı)", () => {
    const s = [src("kaynak_1")];
    assert.deepEqual(citedNumbers("x [kaynak_1, 2023]", s), []);
    assert.equal(numberCitations("x [kaynak_1, 2023]", s), "x [kaynak_1, 2023]");
  });
});

describe("validateInput", () => {
  it("boş girdiyi reddeder", () => {
    for (const mode of ["text", "url"] as const) {
      const r = validateInput(mode, "   ");
      assert.equal(r.ok, false);
    }
  });
  it("geçersiz bağlantıyı reddeder", () => {
    for (const bad of ["abc", "ftp://x.com", "http://localhost", "javascript:alert(1)"]) {
      assert.equal(validateInput("url", bad).ok, false, bad);
    }
    assert.equal(validateInput("url", "https://ornek.com/haber").ok, true);
  });
  it("çok uzun metni sınırda reddeder", () => {
    assert.equal(validateInput("text", "a".repeat(MAX_INPUT_LENGTH)).ok, true);
    const r = validateInput("text", "a".repeat(MAX_INPUT_LENGTH + 1));
    assert.equal(r.ok, false);
    if (!r.ok) assert.equal(r.error.code, "INPUT_TOO_LONG");
  });
  it("3.000 karakteri kabul eder, 3.001 karakteri göndermeden reddeder (canlı backend iddia ve süre sınırı koymuyor)", () => {
    assert.equal(validateInput("text", "a".repeat(3000)).ok, true);
    const r = validateInput("text", "a".repeat(3001));
    assert.equal(r.ok, false);
    if (!r.ok) assert.equal(r.error.code, "INPUT_TOO_LONG");
  });
  it("girdiyi kırpıp gönderir", () => {
    const r = validateInput("text", "  merhaba  ");
    assert.ok(r.ok && r.request.content === "merhaba");
  });
});

describe("gönderim kısayolu", () => {
  it("Ctrl+Enter ve Cmd+Enter gönderir; yalın Enter metin alanında yeni satır olarak kalır", () => {
    assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: true, metaKey: false }), true);
    assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: false, metaKey: true }), true);
    assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: false, metaKey: false }), false);
    assert.equal(isSubmitShortcut({ key: "a", ctrlKey: true, metaKey: false }), false);
  });
  it("yazım yöntemi (IME) birleştirme sürerken göndermez", () => {
    assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: true, metaKey: false, isComposing: true }), false);
  });
});
