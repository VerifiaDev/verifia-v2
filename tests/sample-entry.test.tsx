import assert from "node:assert/strict";
import { before, describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

// Canlı mod: backend adresi tanımlı (yayındaki site gibi). Modül yüklenmeden ÖNCE ayarlanmalı.
process.env.NEXT_PUBLIC_API_BASE_URL = "https://backend.test";
let Analyzer: typeof import("@/components/Analyzer").Analyzer;
before(async () => {
  ({ Analyzer } = await import("@/components/Analyzer"));
});

describe("hazır örnek rapor girişi (backend bağlıyken)", () => {
  it("örnek raporu açan düğme canlı modda da görünür; ikincil görünümdedir ve metni incelemediğini söyler", () => {
    const html = renderToStaticMarkup(<Analyzer />);
    assert.match(html, /<button[^>]*class="btn btn-quiet"[^>]*>Kaynaklı örnek raporu aç/);
    assert.ok(html.includes("Hazır örnek; yazdığınız metni incelemez."));
    assert.ok(!html.includes("Demo sürümü"), "canlı modda demo uyarısı çıkmamalı");
  });
});
