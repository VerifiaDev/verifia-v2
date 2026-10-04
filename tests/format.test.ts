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
});
