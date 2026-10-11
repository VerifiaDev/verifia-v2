import assert from "node:assert/strict";
import { before, describe, it } from "node:test";

// Saat dilimi modül yüklenirken okunur; import'tan ÖNCE ayarlanmalı (UTC'nin batısında bir bölge).
process.env.TZ = "America/Los_Angeles";
let formatDate: typeof import("@/lib/format").formatDate;
before(async () => {
  ({ formatDate } = await import("@/lib/format"));
});

describe("formatDate", () => {
  it("yalnızca tarih içeren değeri okuyanın saat diliminden bağımsız gösterir (bir gün geri kaymaz)", () => {
    assert.equal(formatDate("2023-03-14"), "14 Mart 2023");
    assert.equal(formatDate("2024-01-01"), "1 Ocak 2024");
  });
  it("tarih yoksa ya da bozuksa null döner (uydurmaz)", () => {
    assert.equal(formatDate(null), null);
    assert.equal(formatDate("dün"), null);
    assert.equal(formatDate("2023-13-45"), null);
  });
  it("gün ve ayı belirsiz biçimleri tahmin etmez (yanlış ama inandırıcı bir tarih göstermez)", () => {
    // "05.10.2026" Türkçe yazımda 5 Ekim'dir; JavaScript bunu 10 Mayıs diye okur.
    assert.equal(formatDate("05.10.2026"), null);
    assert.equal(formatDate("05/10/2026"), null);
    assert.equal(formatDate("5 Ekim 2026"), null);
  });
  it("ISO 8601 tarih-saat ve RFC 2822 biçimlerini gösterir", () => {
    assert.equal(formatDate("2026-10-05T12:00:00Z"), "5 Ekim 2026");
    assert.equal(formatDate("2026-10-05T15:30:00+03:00"), "5 Ekim 2026");
    assert.equal(formatDate("Mon, 05 Oct 2026 12:00:00 GMT"), "5 Ekim 2026");
  });
});
