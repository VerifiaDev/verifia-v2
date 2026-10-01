/**
 * Backend'in ham JSON cevabını arayüzün tiplerine çevirir.
 *
 * Backend henüz yazılmadığı için kabul edilen şekiller GEÇİCİDİR. İki biçim de desteklenir:
 *
 *  A) { claims: [ {
 *        id, text | claim, verdict, explanation, is_verifiable?,
 *        sources | evidence: [ { id?, url, source? | title?, text?, published_at?, score? } ]
 *     } ] }
 *
 *  B) Tek iddia (proje dokümanındaki örnek):
 *     { claim, verdict, explanation, confidence, evidence: [ {text, source, url, score, published_at} ] }
 *
 * `confidence` ve `score` bilerek okunmaz: arayüz sahte kesinlik hissi vermemek için göstermez.
 * Bu dosya bilerek başka dosyalardan YALNIZCA tip alır (kolay test için).
 */
import type { CheckResult, Claim, Source, Verdict } from "./types";

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

function parseSource(raw: unknown, index: number): Source | null {
  if (!isRecord(raw)) return null;
  const url = str(raw.url);
  if (!url) return null;
  return {
    id: str(raw.id) ?? `kaynak_${index + 1}`,
    url,
    name: str(raw.source) ?? str(raw.title) ?? str(raw.name),
    publishedAt: str(raw.published_at),
    excerpt: str(raw.text) ?? str(raw.excerpt),
  };
}

function parseClaim(raw: unknown, index: number): Claim | { unverifiableText: string } {
  if (!isRecord(raw)) throw new InvalidResponseError(`claims[${index}] nesne değil`);

  const text = str(raw.text) ?? str(raw.claim);
  if (!text) throw new InvalidResponseError(`claims[${index}] için iddia metni eksik`);

  if (raw.is_verifiable === false) return { unverifiableText: text };

  const verdict = normalizeVerdict(raw.verdict);
  if (!verdict) throw new InvalidResponseError(`claims[${index}].verdict tanınmadı: ${String(raw.verdict)}`);

  const rawSources = Array.isArray(raw.sources) ? raw.sources : Array.isArray(raw.evidence) ? raw.evidence : [];
  const sources = rawSources.map(parseSource).filter((s): s is Source => s !== null);

  return {
    id: str(raw.id) ?? `claim_${index + 1}`,
    text,
    verdict,
    explanation: str(raw.explanation) ?? "",
    sources,
  };
}

export function parseCheckResponse(body: unknown): CheckResult {
  let list: unknown[];
  if (isRecord(body) && Array.isArray(body.claims)) {
    list = body.claims;
  } else if (isRecord(body) && "verdict" in body && (body.claim !== undefined || body.text !== undefined)) {
    list = [body]; // tek iddialı biçim
  } else {
    throw new InvalidResponseError("Cevapta 'claims' listesi yok");
  }

  const claims: Claim[] = [];
  const unverifiable: string[] = [];
  list.forEach((raw, i) => {
    const parsed = parseClaim(raw, i);
    if ("unverifiableText" in parsed) unverifiable.push(parsed.unverifiableText);
    else claims.push(parsed);
  });
  return { claims, unverifiable };
}
