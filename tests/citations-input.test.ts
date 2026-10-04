import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { citedNumbers, splitIds } from "@/lib/citations";
import { validateInput } from "@/lib/input";
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
  it("girdiyi kırpıp gönderir", () => {
    const r = validateInput("text", "  merhaba  ");
    assert.ok(r.ok && r.request.content === "merhaba");
  });
});
