import assert from "node:assert/strict";
import { before, describe, it } from "node:test";

// Backend adresi yapılandırma yüklenirken okunur; import'tan ÖNCE ayarlanmalı.
process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.backend.test/v1/";
let csp = "";
let names: string[] = [];
before(async () => {
  const config = (await import("../next.config")).default;
  const rules = await config.headers!();
  const headers = rules[0].headers;
  names = headers.map((h) => h.key);
  csp = headers.find((h) => h.key === "Content-Security-Policy")?.value ?? "";
});

const directive = (name: string) => csp.split("; ").find((d) => d.startsWith(`${name} `)) ?? "";

describe("güvenlik başlıkları", () => {
  it("içerik güvenlik politikası ve diğer başlıklar tüm yollara uygulanır", () => {
    for (const key of ["Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options"]) {
      assert.ok(names.includes(key), key);
    }
  });
  it("sayfa yalnızca siteye ve tanımlı backend'in köküne istek gönderebilir", () => {
    const sources = directive("connect-src").split(" ").slice(1).filter((s) => s !== "ws:");
    assert.deepEqual(sources, ["'self'", "https://api.backend.test"]);
  });
  it("dış kaynaklı betik, eklenti ve gömme yok", () => {
    assert.ok(!/https?:/.test(directive("script-src")));
    assert.equal(directive("object-src"), "object-src 'none'");
    assert.equal(directive("frame-ancestors"), "frame-ancestors 'none'");
    assert.equal(directive("base-uri"), "base-uri 'self'");
    assert.equal(directive("default-src"), "default-src 'self'");
  });
});

describe("adres yönlendirmesi (backend CORS yalnızca asıl adrese izin verir)", () => {
  it("izinsiz Vercel adresi asıl adrese geçici olarak yönlendirilir; asıl adres yönlendirilmez", async () => {
    const mod = await import("../next.config");
    const rules = await mod.default.redirects!();
    assert.ok(rules.length >= 1);
    for (const r of rules) {
      const host = (r.has?.[0] as { value?: string } | undefined)?.value;
      assert.notEqual(host, mod.CANONICAL_HOST);
      assert.equal(r.destination, `https://${mod.CANONICAL_HOST}/:path*`);
      assert.equal(r.permanent, false);
    }
    assert.ok(rules.some((r) => (r.has?.[0] as { value?: string } | undefined)?.value === "verify-test-efee2.vercel.app"));
  });
  it("yayın derlemesinin dal takma adı (git-main) da asıl adrese yönlendirilir", async () => {
    // 11 Ekim denetimi: bu adreste form açıktı ama backend'e giden her istek CORS'a takılıyordu.
    const mod = await import("../next.config");
    const rules = await mod.default.redirects!();
    const rule = rules.find((r) => (r.has?.[0] as { value?: string } | undefined)?.value === "verify-test-git-main-efee2.vercel.app");
    assert.ok(rule, "git-main adresi için yönlendirme kuralı yok");
    assert.equal(rule.source, "/:path*");
    assert.equal(rule.destination, "https://verify-test-swart.vercel.app/:path*");
    assert.equal((rule.has?.[0] as { type?: string }).type, "host");
  });
});
