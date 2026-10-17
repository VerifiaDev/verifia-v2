import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";

/**
 * Yazım kuralları (proje sahibinin isteği): kullanıcıya görünen metinde uzun tire (—) ve emoji yok.
 * Yalnızca kod yorumları serbesttir; yorumlar silinip kalan kod (metinler dahil) taranır.
 */
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx|txt)$/.test(n) ? [p] : [];
  });
}
const sources = ["app", "components", "lib", "hooks"].flatMap(files);

/** Yorumları atar: /* … *\/, {/* … *\/} ve // satır yorumları (adres içindeki // korunur). */
function stripComments(src: string): string {
  return src
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

describe("yazım kuralları", () => {
  it("kullanıcıya görünen metinde uzun tire (—) yok", () => {
    for (const f of sources) {
      const code = f.endsWith(".txt") ? readFileSync(f, "utf8") : stripComments(readFileSync(f, "utf8"));
      assert.ok(!code.includes("—"), `${f} uzun tire içeriyor`);
    }
  });
  it("arayüz metninde emoji yok", () => {
    const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B50}]/u;
    for (const f of sources) {
      const code = f.endsWith(".txt") ? readFileSync(f, "utf8") : stripComments(readFileSync(f, "utf8"));
      assert.ok(!emoji.test(code), `${f} emoji içeriyor`);
    }
  });
});
