import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";

/** UI katmanı dosyaları: app/, components/, hooks/ */
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx)$/.test(n) ? [p] : [];
  });
}
const ui = ["app", "components", "hooks"].flatMap(files);

describe("katman kuralları", () => {
  it("UI dosyalarında doğrudan fetch/XMLHttpRequest yok", () => {
    for (const f of ui) assert.ok(!/\bfetch\s*\(|XMLHttpRequest/.test(readFileSync(f, "utf8")), f);
  });
  it("UI dosyaları mock'u ya da ham servisleri doğrudan içe aktarmaz", () => {
    for (const f of ui) {
      const src = readFileSync(f, "utf8");
      assert.ok(!/lib\/api\/(mock|http|service|contract|adapter)/.test(src), f);
    }
  });
  it("yalnızca hooks/ API'yi çağırır; bileşenler yalnızca bilgi (apiInfo) ve tip alır", () => {
    for (const f of ui.filter((p) => p.startsWith("components"))) {
      const src = readFileSync(f, "utf8");
      assert.ok(!/\bcheckInput\b/.test(src), f);
    }
  });
});
