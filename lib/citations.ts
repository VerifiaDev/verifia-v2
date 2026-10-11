/**
 * Açıklama metnindeki [kaynak_1] gibi atıfları çözen saf yardımcılar.
 * Listede olmayan bir atıf hiçbir zaman kaynağa çevrilmez (kaynak uydurulmaz).
 * Atıf olmayan köşeli parantezli metin ([2023], [...], [sic]) olduğu gibi kalır; silinmez.
 */
import type { Source } from "./types";

const CITATION = /\[([^\]]+)\]/g;

/** Kimlik biçimi: harfle başlar ve alt çizgi içerir (source_1, kaynak_3, nasa_overview). Yıl, "..." ya da tek sözcük değildir. */
const ID_LIKE = /^\p{L}[\p{L}\p{N}]*_[\p{L}\p{N}_]+$/u;

/** "kaynak_1, kaynak_2" → ["kaynak_1", "kaynak_2"] */
export function splitIds(group: string): string[] {
  return group
    .split(/[,;]\s*/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Köşeli parantezin içi atıf mı? Yalnızca her parçası listedeki bir kaynağın kimliği ya da kimlik biçiminde ise evet.
 * Böylece model "[2023]" ya da "[...]" yazdığında metin "kaynak eşleşmesi bulunamadı" uyarısına dönüşmez.
 */
export function isCitationGroup(group: string, sources: Source[]): boolean {
  const ids = splitIds(group);
  return ids.length > 0 && ids.every((id) => ID_LIKE.test(id) || sources.some((s) => s.id === id));
}

/** Ekran ve düz metin çıktısı aynı kaynak numaralarını kullanır. */
export function numberCitations(text: string, sources: Source[]): string {
  return text.replace(CITATION, (whole: string, group: string) => {
    if (!isCitationGroup(group, sources)) return whole;
    return `[${splitIds(group).map((id) => {
      const index = sources.findIndex((source) => source.id === id);
      return index < 0 ? "Kaynak eşleşmesi bulunamadı" : String(index + 1);
    }).join(", ")}]`;
  });
}

/** Atıf yapılan kaynakların numaraları (1 tabanlı, `sources` sırasına göre), açıklamadaki ilk geçiş sırasıyla. */
export function citedNumbers(explanation: string, sources: Source[]): number[] {
  const seen: number[] = [];
  for (const m of explanation.matchAll(CITATION)) {
    if (!isCitationGroup(m[1], sources)) continue;
    for (const id of splitIds(m[1])) {
      const n = sources.findIndex((s) => s.id === id) + 1;
      if (n > 0 && !seen.includes(n)) seen.push(n);
    }
  }
  return seen;
}
