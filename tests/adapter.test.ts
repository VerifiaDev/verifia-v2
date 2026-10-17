import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { InvalidResponseError, SOURCELESS_EXPLANATION, normalizeVerdict, parseCheckResponse } from "@/lib/api/adapter";

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

  it("gerçek backend şeklini (results, claim_id, source_N, used_sources) çevirir", () => {
    const r = parseCheckResponse({
      results: [
        {
          claim_id: "claim_1",
          claim: "A oldu.",
          is_verifiable: true,
          verdict: "NOT ENOUGH EVIDENCE",
          explanation: "Bkz. [source_1].",
          used_sources: ["source_1"],
          sources: [{ id: "source_1", url: "https://www.a.example/x", text: "pasaj" }],
        },
        { claim_id: "claim_2", claim: "Yarın yağmur yağacak.", is_verifiable: false },
      ],
    });
    assert.equal(r.claims.length, 1);
    assert.equal(r.claims[0].id, "claim_1");
    assert.equal(r.claims[0].verdict, "NOT_ENOUGH_EVIDENCE");
    assert.equal(r.claims[0].confidence, null);
    assert.equal(r.claims[0].sources[0].id, "source_1");
    assert.equal(r.claims[0].sources[0].name, null);
    assert.deepEqual(r.unverifiable, ["Yarın yağmur yağacak."]);
  });

  it("güven puanını (0-1) taşır; kanıt skorunu taşımaz", () => {
    const r = parseCheckResponse({ claim: "T", verdict: "SUPPORTED", explanation: "e", confidence: 0.99, evidence: [{ id: "k", url: "https://b.example", text: "m", score: 0.9 }] });
    assert.equal(r.claims[0].confidence, 0.99);
    assert.equal("score" in r.claims[0].sources[0], false);
  });

  it("güven puanı yoksa null; geçersiz değerleri uydurmaz", () => {
    const conf = (c: unknown) => parseCheckResponse({ claim: "T", verdict: "SUPPORTED", confidence: c }).claims[0].confidence;
    assert.equal(conf(undefined), null);
    assert.equal(conf(0), 0);
    assert.equal(conf(1), 1);
    for (const bad of [91, -0.1, 1.01, NaN, Infinity, "0.9", null, true]) assert.equal(conf(bad), null, String(bad));
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

  it("kaynak yoksa hüküm yok: kaynaksız doğru/yanlış/çelişkili sonuç 'yeterli kanıt yok' olarak gösterilir", () => {
    for (const verdict of ["SUPPORTED", "REFUTED", "CONFLICTING"]) {
      const r = parseCheckResponse({ results: [{ claim: "A", verdict, explanation: "Modelin kendi bilgisi.", sources: [] }] });
      assert.equal(r.claims[0].verdict, "NOT_ENOUGH_EVIDENCE", verdict);
      assert.equal(r.claims[0].explanation, SOURCELESS_EXPLANATION);
    }
    const kept = parseCheckResponse({ results: [{ claim: "A", verdict: "NOT ENOUGH EVIDENCE", explanation: "Kaynak yok.", sources: [] }] });
    assert.equal(kept.claims[0].explanation, "Kaynak yok.");
    const withSource = parseCheckResponse({ results: [{ claim: "A", verdict: "SUPPORTED", explanation: "e [source_1]", sources: [{ id: "source_1", url: "https://a.example", text: "m" }] }] });
    assert.equal(withSource.claims[0].verdict, "SUPPORTED");
  });

  it("sonucu tanınmayan iddia diğerlerini düşürmez; ayrı listelenir (kısmi sonuç)", () => {
    const r = parseCheckResponse({
      results: [
        { claim: "A", verdict: "SUPPORTED" },
        { claim: "B", verdict: "MOSTLY_TRUE" },
        { claim: "C" },
        { claim: "D", is_verifiable: false },
      ],
    });
    assert.deepEqual(r.claims.map((c) => c.text), ["A"]);
    assert.deepEqual(r.unreadable, ["B", "C"]);
    assert.deepEqual(r.unverifiable, ["D"]);
  });

  it("backend_v2: durumu ok olmayan iddia hüküm taşımaz, 'incelenemeyen' listesine girer", () => {
    const r = parseCheckResponse({
      status: "ok",
      partial: true,
      results: [
        { claim_id: "c1", claim: "A", is_verifiable: true, verdict: "SUPPORTED", explanation: "x", used_sources: [], sources: [], status: "ok" },
        { claim_id: "c2", claim: "B", is_verifiable: true, verdict: null, status: "timeout", explanation: "Bu iddia zamanında incelenemedi." },
        { claim_id: "c3", claim: "C", is_verifiable: true, verdict: null, status: "skipped" },
        { claim_id: "c4", claim: "D", is_verifiable: true, verdict: null, status: "error" },
      ],
    });
    assert.deepEqual(r.claims.map((c) => c.text), ["A"]);
    assert.deepEqual(r.unfinished, [
      { text: "B", reason: "timeout" },
      { text: "C", reason: "skipped" },
      { text: "D", reason: "error" },
    ]);
    assert.deepEqual(r.unreadable, []);
  });

  it("backend_v2: hiçbir iddia incelenemediyse de geçerli cevaptır (hata sayılmaz)", () => {
    const r = parseCheckResponse({ status: "ok", partial: true, results: [{ claim_id: "c1", claim: "A", is_verifiable: true, verdict: null, status: "timeout" }] });
    assert.equal(r.claims.length, 0);
    assert.equal(r.unfinished?.length, 1);
  });

  it("okunabilen hiçbir iddia yokken sonucu tanınmayan iddia varsa cevap geçersizdir ('iddia bulunamadı' denmez)", () => {
    assert.throws(() => parseCheckResponse({ results: [{ claim: "B", verdict: "MOSTLY_TRUE" }, { claim: "D", is_verifiable: false }] }), InvalidResponseError);
  });

  it("boş claims listesi geçerlidir", () => {
    const r = parseCheckResponse({ claims: [] });
    assert.deepEqual(r, { claims: [], unverifiable: [], unreadable: [] });
  });

  for (const bad of [null, "x", [], {}, { claims: "a" }, { claims: [null] }, { claims: [{ verdict: "SUPPORTED" }] }, { claims: [{ text: "t", verdict: "??" }] }]) {
    it(`geçersiz cevapta InvalidResponseError fırlatır: ${JSON.stringify(bad)}`, () => {
      assert.throws(() => parseCheckResponse(bad), InvalidResponseError);
    });
  }
});

describe("proje dokümanındaki örnek cevap", () => {
  it("aynen kabul edilir; confidence okunur, evidence.score okunmaz", () => {
    const r = parseCheckResponse({
      claim: "Örnek iddia",
      verdict: "REFUTED",
      explanation: "Kaynaklar bu iddia ile çelişiyor.",
      confidence: 0.91,
      evidence: [{ text: "Kısa kanıt pasajı", source: "Reuters", url: "https://example.com", score: 0.87, published_at: "2026-05-12" }],
    });
    assert.equal(r.claims.length, 1);
    assert.equal(r.claims[0].text, "Örnek iddia");
    assert.equal(r.claims[0].verdict, "REFUTED");
    assert.equal(r.claims[0].confidence, 0.91);
    assert.equal(r.claims[0].sources[0].name, "Reuters");
    assert.equal(r.claims[0].sources[0].publishedAt, "2026-05-12");
    assert.equal(r.claims[0].sources[0].excerpt, "Kısa kanıt pasajı");
  });
});

it("isteğe bağlı şeffaflık alanlarını taşır, geçersiz değerleri üretmez", () => {
  const result = parseCheckResponse({
    claims: [{ text: "İddia", verdict: "SUPPORTED", sources: [
      { url: "https://example.com/one", relation: "context", excerpt_kind: "summary", kind: "Görev kaydı" },
      { url: "https://example.com/two", relation: "certain", excerpt_kind: "unknown" },
    ] }],
    report: { scope: "Yalnızca iki belge", prepared_at: "geçersiz tarih" },
  });
  assert.equal(result.claims[0].sources[0].relation, "context");
  assert.equal(result.claims[0].sources[0].excerptKind, "summary");
  assert.equal(result.claims[0].sources[1].relation, undefined);
  assert.equal(result.claims[0].sources[1].excerptKind, undefined);
  assert.deepEqual(result.report, { scope: "Yalnızca iki belge" });
});

describe("parseCheckResponse: gerçek backend şekli (backend/main.py)", () => {
  const body = {
    status: "ok",
    results: [
      {
        claim_id: "claim_1",
        claim: "Dünya yuvarlaktır.",
        is_verifiable: true,
        verdict: "NOT ENOUGH EVIDENCE",
        explanation: "Kanıt yetersiz [source_1].",
        used_sources: ["source_1"],
        sources: [
          { id: "source_1", title: "Bir başlık", site_name: "ornek.com", domain: "ornek.com", url: "https://www.ornek.com/a", published_date: "2025-03-04", retrieval_score: 0.8, text: "alıntı" },
          { id: "source_2", title: "Kaynak", domain: "diger.org", url: "https://diger.org/b", published_date: null, retrieval_score: 0.5, text: "başka" },
          { id: "source_3", title: "ornek.net", domain: "ornek.net", url: "https://ornek.net/c", published_date: null, text: "üçüncü" },
        ],
      },
      { claim_id: "claim_2", claim: "Bence güzel.", is_verifiable: false, verdict: null, explanation: null, used_sources: [], sources: [] },
    ],
  };
  it("başlık, tarih ve doğrulanamayan iddiayı doğru çevirir", () => {
    const r = parseCheckResponse(body);
    assert.equal(r.claims.length, 1);
    assert.deepEqual(r.unverifiable, ["Bence güzel."]);
    assert.equal(r.claims[0].verdict, "NOT_ENOUGH_EVIDENCE");
    const [a, b, c] = r.claims[0].sources;
    assert.equal(a.name, "Bir başlık");
    assert.equal(a.publishedAt, "2025-03-04");
    assert.equal(b.name, null, "yedek 'Kaynak' etiketi ad sayılmaz");
    assert.equal(c.name, null, "alan adıyla aynı başlık ad sayılmaz");
    assert.equal(r.claims[0].confidence, null);
  });
});
