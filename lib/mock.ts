import { parseCheckResponse } from "./adapter";
import { ApiRequestError } from "./errors";
import type { CheckRequest, CheckResult } from "./types";

/**
 * SAHTE (mock) backend. Gerçek API hazır olana kadar arayüzü denemek içindir.
 * Buradaki kaynaklar ve alıntılar TAMAMEN UYDURMADIR; gerçek bir kuruma ait değildir.
 * Cevaplar, gerçek backend'in döneceği HAM şekilde hazırlanır ve aynı çeviriciden (adapter) geçer.
 * Bilerek iki farklı biçim kullanılır (`sources` ve `evidence`) ki çevirici her ikisiyle denensin.
 * Senaryoyu, girdiye yazdığınız anahtar kelime belirler (bkz. pickScenario).
 */

const DELAY_MS = 2500;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Scenario =
  | "mixed"
  | "supported"
  | "refuted"
  | "not_enough"
  | "conflicting"
  | "opinion"
  | "error_url"
  | "error_timeout"
  | "error_server"
  | "error_network";

function pickScenario(req: CheckRequest): Scenario {
  const t = req.content.toLowerCase();
  if (req.mode === "url" && t.includes("bozuk")) return "error_url";
  if (t.includes("#hata-zamanasimi")) return "error_timeout";
  if (t.includes("#hata-sunucu")) return "error_server";
  if (t.includes("#hata-ag")) return "error_network";
  if (t.includes("#yetersiz")) return "not_enough";
  if (t.includes("#celiski")) return "conflicting";
  if (t.includes("#gorus")) return "opinion";
  if (t.includes("#dogru")) return "supported";
  if (t.includes("#yanlis")) return "refuted";
  return "mixed";
}

const ev = (n: number, text: string, published_at: string | null, score = 0.8) => ({
  id: `kaynak_${n}`,
  url: `https://example.com/kaynak-${n}`,
  source: `Örnek Kaynak ${String.fromCharCode(64 + n)} (uydurma)`,
  text,
  published_at,
  score,
});

const refuted = {
  id: "claim_1",
  text: "Köprü 2024 yılında açıldı.",
  verdict: "REFUTED",
  explanation:
    "Köprü Mart 2023'teki törenle trafiğe açıldı [kaynak_1]. 2024'te yalnızca ek şeritler tamamlandı [kaynak_2]. Bu nedenle 2024 iddiası kanıtlarla çelişiyor.",
  confidence: 0.91,
  sources: [
    ev(1, "Köprü, Mart 2023'teki törenle trafiğe açıldı.", "2023-03-14", 0.87),
    ev(2, "Açılış 2023 baharında yapıldı; 2024'te yalnızca ek şeritler tamamlandı.", null, 0.81),
    ev(3, "Köprünün yapımı 2019'da başlamıştı.", "2019-06-02", 0.52),
  ],
};

const supported = {
  id: "claim_2",
  text: "Proje Ulaştırma Bakanlığı tarafından yürütüldü.",
  verdict: "SUPPORTED",
  explanation:
    "Projenin yürütücüsü Ulaştırma Bakanlığı'dır [kaynak_1]. İhale ve yapım denetimini de bakanlık üstlendi [kaynak_2].",
  sources: [
    ev(1, "Projenin yürütücüsü Ulaştırma Bakanlığı'dır.", "2023-03-14"),
    ev(2, "Bakanlık, ihale sürecini ve yapım denetimini üstlendi.", "2022-06-20"),
  ],
};

const notEnough = {
  id: "claim_3",
  text: "Açılış törenine 50 bin kişi katıldı.",
  verdict: "NOT ENOUGH EVIDENCE", // ai-engine'in gerçek yazımı
  explanation:
    "Katılımcı sayısına dair güvenilir bir kaynak bulunamadı. İddia bu nedenle doğrulanamadı; bu, yanlış olduğu anlamına gelmez.",
  sources: [],
};

// Tek iddialı proje dokümanı biçimi: `claim` + `evidence`
const conflicting = {
  claim: "Yeni düzenleme işsizliği azalttı.",
  verdict: "CONFLICTING_EVIDENCE",
  explanation:
    "Düzenlemeden sonraki üç ayda işsizlik oranı düştü [kaynak_1]. Yıllık bazda bakıldığında ise oran arttı [kaynak_2]. Kaynaklar farklı dönemleri ölçüyor.",
  confidence: 0.52,
  evidence: [
    ev(1, "Düzenlemeden sonraki üç ayda işsizlik oranı düştü.", "2025-09-10"),
    ev(2, "Yıllık bazda bakıldığında işsizlik oranı arttı.", "2025-11-03"),
  ],
};

const opinion = { id: "claim_5", text: "Bu proje çok harika bir karar.", is_verifiable: false };

function buildBody(s: Scenario): unknown {
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
    default:
      return { claims: [refuted, supported, notEnough, opinion] };
  }
}

export async function mockCheck(req: CheckRequest): Promise<CheckResult> {
  await sleep(DELAY_MS);
  const s = pickScenario(req);
  if (s === "error_url") throw new ApiRequestError("URL_UNREADABLE", "Bu bağlantı okunamadı.");
  if (s === "error_timeout") throw new ApiRequestError("TIMEOUT", "Sunucu zamanında yanıt vermedi.");
  if (s === "error_server") throw new ApiRequestError("INTERNAL_ERROR", "Sunucuda bir sorun oluştu.");
  if (s === "error_network") throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
  return parseCheckResponse(buildBody(s));
}
