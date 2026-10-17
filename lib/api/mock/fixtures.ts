import type { RawClaim, RawEvidence } from "../contract";

/**
 * SAHTE (mock) veri. Kaynaklar ve alıntılar TAMAMEN UYDURMADIR; gerçek bir kuruma ait değildir.
 * Veriler gerçek backend'in döneceği HAM şekilde (contract.ts) yazılır; bu yüzden tipleri derleyicide denetlenir.
 * Bilerek iki farklı biçim kullanılır (`sources` ve `evidence`) ki adapter her ikisiyle denensin.
 */

/**
 * Formun altındaki "Örnek deneyin" bağlantıları. Anahtar kelimeler pickScenario ile eşleşir.
 * Etiketler sonuç adlarıyla aynı dili kullanır (bkz. lib/format.ts). `dev: true` olanlar arayüzün
 * teknik durumlarını denemek içindir; yayındaki sitede gösterilmez (bkz. lib/api/index.ts).
 */
export const MOCK_EXAMPLES: { label: string; mode: "text" | "url"; content: string; dev?: boolean }[] = [
  { label: "Kanıtların desteklediği iddia", mode: "text", content: "#dogru Örnek iddia: Bir kentin nüfusu son sayımda arttı." },
  { label: "Kanıtların çeliştiği iddia", mode: "text", content: "#yanlis Örnek iddia: Bir ilaç hastalığı tamamen iyileştiriyor." },
  { label: "Kaynakların birbiriyle çeliştiği iddia", mode: "text", content: "#celiski Örnek iddia: Bir bölgede yağış rekoru kırıldı." },
  { label: "Yeterli kanıt bulunmayan iddia", mode: "text", content: "#yetersiz Örnek iddia: Bir şirket gizli bir anlaşma yaptı." },
  { label: "Aşama bildiren backend (taklit)", mode: "text", content: "#asamali Örnek iddia: Bir kentin nüfusu son sayımda arttı.", dev: true },
  { label: "Kısmi sonuç (bir iddia okunamıyor)", mode: "text", content: "#eksik Örnek iddia: Bir kentin nüfusu son sayımda arttı.", dev: true },
  { label: "Hata: zaman aşımı", mode: "text", content: "#hata-zamanasimi örnek", dev: true },
];


const ev = (n: number, text: string, published_at: string | null, score = 0.8): RawEvidence => ({
  id: `kaynak_${n}`,
  url: `https://example.com/kaynak-${n}`,
  source: `Örnek Kaynak ${String.fromCharCode(64 + n)} (uydurma)`,
  text,
  published_at,
  score,
});

export const refuted: RawClaim = {
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

export const supported: RawClaim = {
  id: "claim_2",
  text: "Proje Ulaştırma Bakanlığı tarafından yürütüldü.",
  verdict: "SUPPORTED",
  explanation:
    "Projenin yürütücüsü Ulaştırma Bakanlığı'dır [kaynak_1]. İhale ve yapım denetimini de bakanlık üstlendi [kaynak_2].",
  confidence: 0.88,
  sources: [
    ev(1, "Projenin yürütücüsü Ulaştırma Bakanlığı'dır.", "2023-03-14"),
    ev(2, "Bakanlık, ihale sürecini ve yapım denetimini üstlendi.", "2022-06-20"),
  ],
};

export const notEnough: RawClaim = {
  id: "claim_3",
  text: "Açılış törenine 50 bin kişi katıldı.",
  verdict: "NOT ENOUGH EVIDENCE", // ai-engine'in gerçek yazımı
  explanation:
    "Katılımcı sayısına dair güvenilir bir kaynak bulunamadı. İddia bu nedenle doğrulanamadı; bu, yanlış olduğu anlamına gelmez.",
  sources: [],
};

// Tek iddialı proje dokümanı biçimi: `claim` + `evidence`
export const conflicting: RawClaim = {
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

export const opinion: RawClaim = { id: "claim_5", text: "Bu proje çok harika bir karar.", is_verifiable: false };

