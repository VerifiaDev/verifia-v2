import type { Claim } from "./types";

/**
 * Yapıştırılan metinde iddiaların altını sonucuna göre boyamak için metni parçalara ayırır.
 *
 * - "ok"  : kanıtlar iddiayı destekliyor (yeşil alt çizgi)
 * - "bad" : kanıtlar iddiayla çelişiyor ya da kaynaklar birbiriyle çelişiyor (kırmızı alt çizgi)
 * - null  : "yeterli kanıt yok" ve iddia olarak eşleşmeyen her şey; olduğu gibi kalır
 *
 * Sınır: servis iddiaları yeniden yazabilir (zamir açar, cümleyi böler). Bu yüzden yalnızca iddia metni,
 * yapıştırılan metinde (büyük/küçük harf ve boşluk farkı hariç) AYNEN geçiyorsa boyanır. Eşleşmeyen iddia
 * için tahmin yürütülmez; sonucu yine iddia listesinde görünür. Bir yer hem "ok" hem "bad" ile eşleşirse
 * "bad" kazanır (yanlış kısım gizlenmesin).
 */
export type Tone = "ok" | "bad";
export interface Segment {
  text: string;
  tone: Tone | null;
}

function toneOf(verdict: Claim["verdict"]): Tone | null {
  if (verdict === "SUPPORTED") return "ok";
  if (verdict === "REFUTED" || verdict === "CONFLICTING") return "bad";
  return null;
}

/** İddia metnini, boşluk ve tırnak biçimi farklarına dayanıklı bir arama kalıbına çevirir. */
function pattern(claim: string): RegExp | null {
  const words = claim
    .trim()
    .replace(/[.!?…]+$/u, "")
    .split(/\s+/u)
    .filter(Boolean);
  if (words.length === 0) return null;
  const body = words
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&").replace(/['’‘`]/gu, "['’‘`]"))
    .join("\\s+");
  // İddianın hemen ardından gelen cümle sonu işareti de çizilsin.
  return new RegExp(`${body}[.!?…]*`, "iu");
}

export function annotateInput(input: string, claims: Claim[]): Segment[] {
  const marks = new Array<number>(input.length).fill(0); // 0 yok, 1 ok, 2 bad
  for (const c of claims) {
    const tone = toneOf(c.verdict);
    if (!tone) continue;
    const re = pattern(c.text);
    if (!re) continue;
    const m = re.exec(input);
    if (!m) continue;
    const value = tone === "bad" ? 2 : 1;
    for (let i = m.index; i < m.index + m[0].length; i++) marks[i] = Math.max(marks[i], value);
  }
  const out: Segment[] = [];
  let start = 0;
  for (let i = 1; i <= input.length; i++) {
    if (i === input.length || marks[i] !== marks[start]) {
      const v = marks[start];
      out.push({ text: input.slice(start, i), tone: v === 2 ? "bad" : v === 1 ? "ok" : null });
      start = i;
    }
  }
  return input.length === 0 ? [] : out;
}
