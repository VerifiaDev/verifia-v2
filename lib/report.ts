import { UNFINISHED_REASON, VERDICT_META } from "./format";
import type { CheckResult } from "./types";
import { numberCitations } from "./citations";

/** Ekrandaki değerlendirme ve kaynaklar, çıktı alınırken de birlikte kalır. */
export function reportText(result: CheckResult, input?: string, sample = false): string {
  return [
    `verify: ${result.report?.title ?? "İddia inceleme raporu"}`,
    sample ? (result.report ? "Önceden hazırlanmış örnek rapor. Canlı analiz değildir." : "Uydurma örnek veriler. Gerçek inceleme değildir.") : "Otomatik ön değerlendirme. Kaynakları kendiniz de kontrol edin.",
    result.report?.preparedAt ? `Hazırlanma tarihi: ${result.report.preparedAt}` : "",
    (result.report?.input ?? input) ? `İncelenen içerik:\n${result.report?.input ?? input}` : "",
    result.report?.summary ?? "",
    ...result.claims.map((c, i) => [
      `${i + 1}. ${c.text}`, VERDICT_META[c.verdict].label,
      !c.sources.length ? "Bu sonuç için kaynak sunulmadı; hüküm kaynak üzerinden denetlenemiyor." : "",
      numberCitations(c.explanation, c.sources) || "Sonucun gerekçesi paylaşılmadı.",
      ...c.sources.map((s, index) => `[${index + 1}] ${s.name ?? s.url}\n${s.publishedAt ? `Yayın tarihi: ${s.publishedAt}\n` : ""}${s.kind ? `${s.kind}\n` : ""}${s.relation ? `${s.relation === "supports" ? "İddiayı destekliyor" : s.relation === "contradicts" ? "İddiayla çelişiyor" : "Bağlam sağlıyor"}\n` : ""}${s.excerptKind === "summary" ? "Türkçe özet: " : ""}${s.excerpt ?? ""}\n${s.url}`),
    ].filter(Boolean).join("\n")),
    result.unverifiable.length ? `İncelenmeyen ifadeler:\n${result.unverifiable.join("\n")}` : "",
    result.unfinished?.length ? `İncelenemeyen iddialar:\n${result.unfinished.map((u) => `${u.text} (${UNFINISHED_REASON[u.reason]})`).join("\n")}` : "",
    result.unreadable.length ? `Sonucu gösterilemeyen iddialar:\n${result.unreadable.join("\n")}` : "",
    `Kapsam ve sınırlamalar:\n${result.report?.scope ?? "Servis araştırmanın kapsamını paylaşmadı. Sonuçlar, metnin tamamı için tek bir doğruluk hükmü değildir."}`,
  ].filter(Boolean).join("\n\n");
}
