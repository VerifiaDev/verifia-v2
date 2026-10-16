import { ApiRequestError } from "../errors";
import type { RawCheckRequest, RawCheckResponse } from "../contract";
import type { VerificationService } from "../service";
import type { AnalysisStage } from "../../types";
import { conflicting, notEnough, opinion, refuted, supported } from "./fixtures";

export { MOCK_EXAMPLES } from "./fixtures";

/**
 * Sahte servis: gerçek servisle aynı arayüzü (VerificationService) uygular.
 * Senaryoyu, girdiye yazdığınız anahtar kelime belirler (bkz. pickScenario). Veriler: fixtures.ts
 */

const DELAY_MS = 2500;

/** Beklerken kullanıcı vazgeçerse (signal) hemen durur. */
function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("aborted", "AbortError"));
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

type Scenario =
  | "mixed"
  | "supported"
  | "refuted"
  | "not_enough"
  | "conflicting"
  | "opinion"
  | "partial"
  | "unfinished"
  | "error_url"
  | "error_timeout"
  | "error_server"
  | "error_network";

function pickScenario(req: RawCheckRequest): Scenario {
  const t = req.text.toLowerCase();
  if (req.input_type === "url" && t.includes("bozuk")) return "error_url";
  if (t.includes("#hata-zamanasimi")) return "error_timeout";
  if (t.includes("#hata-sunucu")) return "error_server";
  if (t.includes("#hata-ag")) return "error_network";
  if (t.includes("#yetersiz")) return "not_enough";
  if (t.includes("#celiski")) return "conflicting";
  if (t.includes("#gorus")) return "opinion";
  if (t.includes("#incelenemedi")) return "unfinished";
  if (t.includes("#eksik")) return "partial";
  if (t.includes("#dogru")) return "supported";
  if (t.includes("#yanlis")) return "refuted";
  return "mixed";
}

function buildBody(s: Scenario): RawCheckResponse {
  switch (s) {
    case "supported":
      return { claims: [supported] };
    case "refuted":
      return { claims: [refuted] };
    case "not_enough":
      return { claims: [notEnough] };
    case "conflicting":
      return conflicting; // tek iddia biçimi
    case "opinion":
      return { claims: [opinion] };
    case "partial":
      // Kısmi sonuç: ikinci iddianın sonuç değeri arayüzün tanımadığı bir etiket.
      return { claims: [supported, { ...refuted, id: "claim_okunamayan", verdict: "TANINMAYAN_ETIKET" }] };
    case "unfinished":
      // backend_v2 biçimi: iddia başına durum. Süre aşımı ve atlanan iddiada karar yoktur.
      return {
        results: [
          supported,
          { claim_id: "claim_zaman", claim: "İkinci iddia zamanında incelenemedi.", is_verifiable: true, verdict: null, status: "timeout", explanation: "Bu iddia zamanında incelenemedi.", used_sources: [], sources: [] },
          { claim_id: "claim_atlanan", claim: "Üçüncü iddia atlandı.", is_verifiable: true, verdict: null, status: "skipped", explanation: "Metinde çok sayıda iddia olduğu için bu iddia incelenmedi.", used_sources: [], sources: [] },
        ],
        partial: true,
      };
    default:
      return { claims: [refuted, supported, notEnough, opinion] };
  }
}

/**
 * `#asamali` yazılırsa, aşama bildiren bir backend'i taklit eder (arayüzün aşama gösterimini denemek için).
 * Normal örneklerde aşama bildirilmez; çünkü gerçek backend şu an bildirmiyor.
 */
const STAGES: AnalysisStage[] = ["extracting_claims", "retrieving_evidence", "verifying"];
const STAGE_MS = 900;

/**
 * Yayındaki sitede servis bağlı değilken gösterilen SABİT örnek sonuç (kullanıcının yazdığı içerikle ilgisi yoktur).
 * Arayüz bunu baştan sona "Örnek" etiketiyle gösterir; kaynakların adında "(uydurma)" yazar.
 */
export function sampleBody(): RawCheckResponse {
  return buildBody("mixed");
}

export const mockService: VerificationService = {
  supportsUrl: true,
  async check(req, { signal, onStage }) {
    if (req.text.toLowerCase().includes("#asamali") && onStage) {
      for (const stage of STAGES) {
        onStage(stage);
        await sleep(STAGE_MS, signal);
      }
    } else {
      await sleep(DELAY_MS, signal);
    }
    const s = pickScenario(req);
    if (s === "error_url") throw new ApiRequestError("URL_UNREADABLE", "Bu bağlantı okunamadı.");
    if (s === "error_timeout") throw new ApiRequestError("TIMEOUT", "Sunucu zamanında yanıt vermedi.");
    if (s === "error_server") throw new ApiRequestError("INTERNAL_ERROR", "Sunucuda bir sorun oluştu.");
    if (s === "error_network") throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
    return buildBody(s);
  },
};
