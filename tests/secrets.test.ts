import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

/**
 * Gizli anahtar koruması. Frontend hiçbir gizli anahtar taşımaz: tarayıcıya giden her şey herkese açıktır.
 * Groq/Tavily gibi anahtarlar yalnızca backend sunucusunun ortam değişkenlerinde durur.
 */

/** Depoya girmiş (git tarafından izlenen) metin dosyaları. */
const tracked = execFileSync("git", ["ls-files"], { encoding: "utf8" })
  .split("\n")
  .filter((f) => f && !/(^|\/)package-lock\.json$|\.(png|ico|jpg|woff2?|ttf)$/.test(f));

const SECRET_PATTERNS: [string, RegExp][] = [
  ["Groq anahtarı", /gsk_[A-Za-z0-9]{20,}/],
  ["Tavily anahtarı", /tvly-[A-Za-z0-9-]{16,}/],
  ["OpenAI tarzı anahtar", /\bsk-[A-Za-z0-9_-]{20,}/],
  ["GitHub belirteci", /\bgh[pousr]_[A-Za-z0-9]{30,}/],
  ["Google anahtarı", /AIza[0-9A-Za-z_-]{30,}/],
  ["AWS anahtarı", /AKIA[0-9A-Z]{16}/],
  ["Özel anahtar", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
];

/** Kodda okunmasına izin verilen ortam değişkenleri. Yenisi eklenecekse gizli olmadığından emin olunmalı. */
const ALLOWED_ENV = new Set(["NODE_ENV", "NEXT_PUBLIC_API_BASE_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_ENV", "TZ"]);

describe("gizli anahtar koruması", () => {
  it("depodaki hiçbir dosyada anahtar biçiminde bir değer yok", () => {
    for (const f of tracked) {
      const src = readFileSync(f, "utf8");
      for (const [name, re] of SECRET_PATTERNS) assert.ok(!re.test(src), `${f}: ${name}`);
    }
  });

  it(".env dosyaları depoya girmez; yalnızca .env.example izlenir", () => {
    const envFiles = tracked.filter((f) => /(^|\/)\.env/.test(f));
    assert.deepEqual(envFiles, [".env.example"]);
    const ignore = readFileSync(".gitignore", "utf8").split("\n");
    for (const rule of [".env", ".env.*", "!.env.example"]) assert.ok(ignore.includes(rule), rule);
  });

  it(".env.example yalnızca herkese açık değişken içerir ve değeri boştur", () => {
    const lines = readFileSync(".env.example", "utf8")
      .split("\n")
      .filter((l) => l.trim() && !l.trim().startsWith("#"));
    assert.deepEqual(lines, ["NEXT_PUBLIC_API_BASE_URL="]);
  });

  it("kod yalnızca izin verilen ortam değişkenlerini okur (tarayıcıya gömülen NEXT_PUBLIC_ dahil)", () => {
    const code = tracked.filter((f) => /\.(ts|tsx|js|mjs)$/.test(f));
    for (const f of code) {
      for (const m of readFileSync(f, "utf8").matchAll(/process\.env\.([A-Z0-9_]+)/g)) {
        assert.ok(ALLOWED_ENV.has(m[1]), `${f}: process.env.${m[1]}`);
      }
    }
  });

  it("NEXT_PUBLIC_ değişkenlerinin adı gizli bir değer çağrıştırmaz", () => {
    for (const f of tracked) {
      for (const m of readFileSync(f, "utf8").matchAll(/NEXT_PUBLIC_[A-Z0-9_]+/g)) {
        assert.ok(!/KEY|SECRET|TOKEN|PASSWORD/.test(m[0]), `${f}: ${m[0]}`);
      }
    }
  });
});
