import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { ThemeToggle } from "@/components/ThemeToggle";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
// layout.tsx CSS ve yazı tipi yükleyicileri içe aktardığı için testte yüklenmez; metin olarak okunur.
const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");

/** `selector { ... }` bloğunun içindeki `--jeton: değer` çiftleri. */
function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[m[1]] = m[2].toLowerCase();
  return out;
}
function blockAfter(marker: string): string {
  const i = css.indexOf(marker);
  assert.ok(i >= 0, `${marker} bulunamadı`);
  const start = css.indexOf("{", i);
  let depth = 0;
  for (let j = start; j < css.length; j++) {
    if (css[j] === "{") depth++;
    if (css[j] === "}" && --depth === 0) return css.slice(start + 1, j);
  }
  throw new Error("blok kapanmıyor");
}

const light = tokens(blockAfter(":root {"));
const dark = tokens(blockAfter(':root[data-theme="dark"]'));
// Sistem koyuyken uygulanan kopya: @media içindeki :root:not([data-theme="light"]) bloğu.
const darkMedia = tokens(blockAfter(':root:not([data-theme="light"])'));

function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function ratio(a: string, b: string): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

describe("gece modu: renk jetonları", () => {
  it("iki koyu blok (elle seçim ve sistem tercihi) birebir aynı", () => {
    assert.deepEqual(darkMedia, dark);
  });

  it("koyu palet açık paletteki her jetonu tanımlar", () => {
    for (const k of Object.keys(dark)) assert.ok(k in light, `açık palette yok: ${k}`);
    for (const k of ["paper", "surface", "ink", "ink-2", "rule", "rule-strong", "accent", "on-accent", "ok", "bad", "unknown", "mixed", "mixed-tint"]) {
      assert.ok(k in dark, `koyu palette eksik: ${k}`);
    }
  });

  for (const [name, t] of [["açık", light], ["koyu", dark]] as const) {
    it(`${name} tema: metin kontrastı en az 4,5:1`, () => {
      const pairs: [string, string][] = [
        ["ink", "paper"], ["ink", "surface"], ["ink-2", "paper"], ["ink-2", "surface"], ["accent", "paper"], ["accent", "surface"],
        ["ok", "paper"], ["bad", "paper"], ["unknown", "paper"], ["mixed", "paper"], ["ink", "mixed-tint"], ["placeholder", "surface"],
      ];
      for (const [fg, bg] of pairs) {
        const a = t[fg] ?? light[fg];
        const b = t[bg] ?? light[bg];
        assert.ok(ratio(a, b) >= 4.5, `${name}: ${fg} (${a}) / ${bg} (${b}) = ${ratio(a, b).toFixed(2)}`);
      }
    });
    it(`${name} tema: vurgu zeminindeki yazı ve form kenarı yeterli kontrastta`, () => {
      const get = (k: string) => t[k] ?? light[k];
      assert.ok(ratio(get("on-accent"), get("accent")) >= 4.5, "düğme yazısı");
      assert.ok(ratio(get("on-accent"), get("mixed")) >= 4.5, "rozet yazısı");
      assert.ok(ratio(get("paper"), get("ink")) >= 4.5, "seçili sekme yazısı");
      assert.ok(ratio(get("rule-strong"), get("surface")) >= 3, "form kenarı (3:1)");
      assert.ok(ratio(get("rule-strong"), get("paper")) >= 3, "form kenarı (3:1)");
    });
  }
});

describe("gece modu: telefon çubuğu ve düğme", () => {
  it("tarayıcı çubuğu renkleri sayfa zeminiyle aynı", () => {
    const find = (scheme: string) => layout.match(new RegExp(`prefers-color-scheme: ${scheme}\\)", color: "(#[0-9a-fA-F]{6})"`))?.[1].toLowerCase();
    assert.equal(find("light"), light["paper"]);
    assert.equal(find("dark"), dark["paper"]);
  });

  it("ilk boyama betiği ve düğme aynı renkleri kullanır", () => {
    for (const hex of [light["paper"], dark["paper"]]) {
      assert.ok(layout.includes(hex), `layout.tsx: ${hex}`);
      assert.ok(readFileSync(new URL("../components/ThemeToggle.tsx", import.meta.url), "utf8").includes(hex), `ThemeToggle.tsx: ${hex}`);
    }
  });

  it("hareket azaltma tercihi sözde öğeleri de kapsar (::before ile çizilen bekleme halkası dönmeye devam etmez)", () => {
    const block = css.slice(css.indexOf("prefers-reduced-motion: reduce"));
    const selector = block.slice(block.indexOf("{") + 1, block.indexOf("{", block.indexOf("{") + 1));
    for (const part of ["*", "*::before", "*::after"]) {
      assert.ok(selector.split(",").map((x) => x.trim()).includes(part), part);
    }
  });

  it("düğme sabit adlı, aria-pressed'lı gerçek bir <button>", () => {
    const html = renderToStaticMarkup(<ThemeToggle />);
    assert.match(html, /^<button /);
    assert.match(html, /type="button"/);
    assert.match(html, /aria-pressed="false"/);
    assert.match(html, /Gece modu/);
  });
});
