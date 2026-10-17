import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { apiInfo, sampleResult } from "@/lib/api";
import { httpService } from "@/lib/api/http";
import { mockService } from "@/lib/api/mock";

describe("sabit örnek sonuç", () => {
  const r = sampleResult();
  it("arayüzün bütün parçalarını gösterecek kadar çeşitlidir", () => {
    assert.ok(r.claims.length >= 3);
    assert.ok(r.claims.some((c) => c.sources.length === 0), "kaynaksız iddia");
    assert.ok(r.unverifiable.length >= 1, "incelenmeyen ifade");
    assert.ok(new Set(r.claims.map((c) => c.verdict)).size >= 3, "en az üç sonuç türü");
  });
  it("hazır raporun kapsamı ve metni vardır; kanıtları NASA kaynaklarına ve Türkçe özetlere bağlanır", () => {
    assert.ok(r.report?.input);
    assert.ok(r.report?.scope?.includes("kapsamlı bir arama yapılmadı"));
    for (const s of r.claims.flatMap((c) => c.sources)) {
      assert.equal(new URL(s.url).hostname, "www.nasa.gov");
      assert.equal(s.excerptKind, "summary");
      assert.ok(s.relation);
    }
  });
});

describe("bağlantı desteği", () => {
  it("örnek servis destekler, gerçek servis (henüz) desteklemez; arayüz bilgisi buna göre gelir", () => {
    assert.equal(mockService.supportsUrl, true);
    assert.equal(httpService("http://backend.test").supportsUrl, false);
    assert.equal(typeof apiInfo.urlSupported, "boolean");
  });
});
