/**
 * Açıklama metnindeki [kaynak_1] gibi atıfları çözen saf yardımcılar.
 * Listede olmayan bir atıf hiçbir zaman kaynağa çevrilmez (kaynak uydurulmaz).
 */
import type { Source } from "./types";

const CITATION = /\[([^\]]+)\]/g;

/** "kaynak_1, kaynak_2" → ["kaynak_1", "kaynak_2"] */
export function splitIds(group: string): string[] {
  return group
    .split(/[,;]\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Ekran ve düz metin çıktısı aynı kaynak numaralarını kullanır. */
export function numberCitations(text: string, sources: Source[]): string {
  return text.replace(/\[([^\]]+)\]/g, (_, group: string) => {
    const ids = splitIds(group);
    if (!ids.length) return "[Kaynak eşleşmesi bulunamadı]";
    return `[${ids.map((id) => {
      const index = sources.findIndex((source) => source.id === id);
      return index < 0 ? "Kaynak eşleşmesi bulunamadı" : String(index + 1);
    }).join(", ")}]`;
  });
}

/** Atıf yapılan kaynakların numaraları (1 tabanlı, `sources` sırasına göre), açıklamadaki ilk geçiş sırasıyla. */
export function citedNumbers(explanation: string, sources: Source[]): number[] {
  const seen: number[] = [];
  for (const m of explanation.matchAll(CITATION)) {
    for (const id of splitIds(m[1])) {
      const n = sources.findIndex((s) => s.id === id) + 1;
      if (n > 0 && !seen.includes(n)) seen.push(n);
    }
  }
  return seen;
}
