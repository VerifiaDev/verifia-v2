import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { InvalidResponseError, normalizeVerdict, parseCheckResponse } from "@/lib/adapter";

describe("normalizeVerdict", () => {
  it("farklı yazımları tek biçime çevirir", () => {
    assert.equal(normalizeVerdict("NOT ENOUGH EVIDENCE"), "NOT_ENOUGH_EVIDENCE");
    assert.equal(normalizeVerdict("NOT_ENOUGH_EVIDENCE"), "NOT_ENOUGH_EVIDENCE");
    assert.equal(normalizeVerdict("CONFLICTING_EVIDENCE"), "CONFLICTING");
    assert.equal(normalizeVerdict(" refuted "), "REFUTED");
    assert.equal(normalizeVerdict("supported"), "SUPPORTED");
  });
  it("tanımadığı değeri null yapar (uydurmaz)", () => {
    assert.equal(normalizeVerdict("MAYBE"), null);
    assert.equal(normalizeVerdict(undefined), null);
    assert.equal(normalizeVerdict(42), null);
  });
});

describe("parseCheckResponse", () => {
  it("claims[] şeklini çevirir; kaynak adı, tarih ve alıntıyı taşır", () => {
    const r = parseCheckResponse({
      claims: [
        {
          id: "c1",
          text: "A",
          verdict: "REFUTED",
          explanation: "x [kaynak_1]",
          sources: [{ id: "kaynak_1", url: "https://a.example", source: "Ajans A", published_at: "2024-01-02", text: "pasaj" }],
        },
      ],
    });
    assert.equal(r.claims.length, 1);
    const s = r.claims[0].sources[0];
    assert.equal(s.name, "Ajans A");
    assert.equal(s.publishedAt, "2024-01-02");
    assert.equal(s.excerpt, "pasaj");
  });

  it("güven/skor alanlarını bilerek yok sayar", () => {
    const r = parseCheckResponse({ claim: "T", verdict: "SUPPORTED", explanation: "e", confidence: 0.99, evidence: [{ id: "k", url: "https://b.example", text: "m", score: 0.9 }] });
    assert.equal("confidence" in r.claims[0], false);
    assert.equal("score" in r.claims[0].sources[0], false);
  });

  it("tek iddia + evidence anahtarını kabul eder", () => {
    const r = parseCheckResponse({ claim: "T", verdict: "SUPPORTED", explanation: "e", evidence: [{ id: "k1", url: "https://b.example", text: "m" }] });
    assert.equal(r.claims.length, 1);
    assert.equal(r.claims[0].sources.length, 1);
  });

  it("doğrulanamaz ifadeleri ayırır", () => {
    const r = parseCheckResponse({ claims: [{ id: "c2", text: "Bence harika.", is_verifiable: false }] });
    assert.deepEqual(r.claims, []);
    assert.deepEqual(r.unverifiable, ["Bence harika."]);
  });

  it("kaynağı bozuk girdileri atar, çökmez", () => {
    const r = parseCheckResponse({ claims: [{ text: "x", verdict: "NOT ENOUGH EVIDENCE", sources: [{ id: "k" }, 5, null] }] });
    assert.equal(r.claims[0].sources.length, 0);
    assert.equal(r.claims[0].id, "claim_1");
    assert.equal(r.claims[0].explanation, "");
  });

  it("boş claims listesi geçerlidir", () => {
    const r = parseCheckResponse({ claims: [] });
    assert.deepEqual(r, { claims: [], unverifiable: [] });
  });

  for (const bad of [null, "x", [], {}, { claims: "a" }, { claims: [null] }, { claims: [{ verdict: "SUPPORTED" }] }, { claims: [{ text: "t", verdict: "??" }] }]) {
    it(`geçersiz cevapta InvalidResponseError fırlatır: ${JSON.stringify(bad)}`, () => {
      assert.throws(() => parseCheckResponse(bad), InvalidResponseError);
    });
  }
});
