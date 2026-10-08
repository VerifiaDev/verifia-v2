/**
 * Backend'in ham JSON cevabını arayüzün tiplerine çevirir.
 *
 * Gerçek backend şekli aşağıda; iki eski biçim mock için tutulur:
 *
 *  Gerçek backend (backend/main.py, POST /verify):
 *     { results: [ { claim_id, claim, is_verifiable, verdict, explanation, used_sources, sources: [ {id:"source_1", title, domain, url, published_date, text} ] } ] }
 *     Kaynakta ayrıca title, site_name, domain, published_date, retrieval_score bulunur (backend/main.py, 87ec895).
     Güven puanı yoktur; arayüz uydurmaz. retrieval_score ve used_sources okunmaz.
 *
 *  A) { claims: [ {
 *        id, text | claim, verdict, explanation, is_verifiable?,
 *        sources | evidence: [ { id?, url, source? | title?, text?, published_at?, score? } ]
 *     } ] }
 *
 *  B) Tek iddia (proje dokümanındaki örnek):
 *     { claim, verdict, explanation, confidence, evidence: [ {text, source, url, score, published_at} ] }
 *
 * Kısmi sonuç: bir iddianın `verdict` değeri tanınmıyorsa o iddia `unreadable` listesine girer, diğerleri gösterilir.
 * Okunabilen hiçbir iddia kalmazsa cevap geçersiz sayılır.
 *
 * `confidence` (0-1 arası sayı) okunur ve "modelin güven puanı" olarak gösterilir; geçersizse (sayı değil,
 * 0-1 dışında) yok sayılır, tahmin edilmez. `score` (kanıt başına) okunmaz.
 * Ham şekiller için bkz. contract.ts. Bu dosya bilerek başka dosyalardan YALNIZCA tip alır (kolay test için).
 */
import type { CheckResult, Claim, Source, Verdict } from "../types";

export class InvalidResponseError extends Error {}

const VERDICT_ALIASES: Record<string, Verdict> = {
  SUPPORTED: "SUPPORTED",
  REFUTED: "REFUTED",
  NOT_ENOUGH_EVIDENCE: "NOT_ENOUGH_EVIDENCE",
  CONFLICTING: "CONFLICTING",
  CONFLICTING_EVIDENCE: "CONFLICTING",
};

/** "NOT ENOUGH EVIDENCE" (ai-engine) ve "NOT_ENOUGH_EVIDENCE" (proje dokümanı) ikisini de kabul eder. */
export function normalizeVerdict(raw: unknown): Verdict | null {
  if (typeof raw !== "string") return null;
  const key = raw.trim().toUpperCase().replace(/[\s-]+/g, "_");
  return VERDICT_ALIASES[key] ?? null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.trim() !== "" ? v.trim() : null;
}

/** Yalnızca 0 ile 1 arasındaki gerçek sayılar. "91" ya da 91 gibi belirsiz değerler yüzde mi oran mı bilinmez; yok sayılır. */
function parseConfidence(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1 ? v : null;
}

function hostOnly(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

/** Backend'in "başlık yok" yedek etiketi (backend/main.py). Gerçek bir ad değildir; gösterilmez. */
const BACKEND_TITLE_PLACEHOLDER = "kaynak";

function parseSource(raw: unknown, index: number): Source | null {
  if (!isRecord(raw)) return null;
  const url = str(raw.url);
  if (!url) return null;
  // Ad: sayfa başlığı. Alan adıyla aynıysa ya da yedek etiketse atılır (alan adı zaten ayrıca gösterilir).
  const candidate = str(raw.source) ?? str(raw.title) ?? str(raw.name);
  const host = hostOnly(url);
  const lower = candidate?.toLowerCase().replace(/^www\./, "");
  const name = candidate && lower !== host && lower !== BACKEND_TITLE_PLACEHOLDER ? candidate : null;
  return {
    id: str(raw.id) ?? `kaynak_${index + 1}`,
    url,
    name,
    publishedAt: str(raw.published_at) ?? str(raw.published_date),
    excerpt: str(raw.text) ?? str(raw.excerpt),
  };
}

function parseClaim(raw: unknown, index: number): Claim | { unverifiableText: string } | { unreadableText: string } {
  if (!isRecord(raw)) throw new InvalidResponseError(`claims[${index}] nesne değil`);

  const text = str(raw.text) ?? str(raw.claim);
  if (!text) throw new InvalidResponseError(`claims[${index}] için iddia metni eksik`);

  if (raw.is_verifiable === false) return { unverifiableText: text };

  // Sonuç değeri tanınmıyorsa yalnızca bu iddia "okunamadı" sayılır; diğer iddialar yine gösterilir.
  // (Tek bozuk satır yüzünden bütün incelemeyi "sunucu hatası" diye atmak, kullanıcının beklediği sonucu boşa harcardı.)
  const verdict = normalizeVerdict(raw.verdict);
  if (!verdict) return { unreadableText: text };

  const rawSources = Array.isArray(raw.sources) ? raw.sources : Array.isArray(raw.evidence) ? raw.evidence : [];
  const sources = rawSources.map(parseSource).filter((s): s is Source => s !== null);

  return {
    id: str(raw.id) ?? str(raw.claim_id) ?? `claim_${index + 1}`,
    text,
    verdict,
    explanation: str(raw.explanation) ?? "",
    sources,
    confidence: parseConfidence(raw.confidence),
  };
}

export function parseCheckResponse(body: unknown): CheckResult {
  let list: unknown[];
  if (isRecord(body) && Array.isArray(body.claims)) {
    list = body.claims;
  } else if (isRecord(body) && Array.isArray(body.results)) {
    list = body.results; // gerçek backend (POST /verify): { results: [...] }
  } else if (isRecord(body) && "verdict" in body && (body.claim !== undefined || body.text !== undefined)) {
    list = [body]; // tek iddialı biçim
  } else {
    throw new InvalidResponseError("Cevapta 'results' ya da 'claims' listesi yok");
  }

  const claims: Claim[] = [];
  const unverifiable: string[] = [];
  const unreadable: string[] = [];
  list.forEach((raw, i) => {
    const parsed = parseClaim(raw, i);
    if ("unverifiableText" in parsed) unverifiable.push(parsed.unverifiableText);
    else if ("unreadableText" in parsed) unreadable.push(parsed.unreadableText);
    else claims.push(parsed);
  });
  // Okunabilen hiçbir sonuç yoksa cevap geçersizdir: "incelenebilir iddia bulunamadı" demek yanlış olurdu
  // (iddia bulundu, sonucu okunamadı).
  if (claims.length === 0 && unreadable.length > 0) {
    throw new InvalidResponseError("Hiçbir iddianın sonucu tanınmadı");
  }
  return { claims, unverifiable, unreadable };
}
