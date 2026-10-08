import type { CheckResult, Source } from "./types";

const overview: Source = {
  id: "nasa_overview",
  name: "NASA · Apollo 11 Mission Overview",
  url: "https://www.nasa.gov/history/apollo-11-mission-overview/",
  publishedAt: null,
  kind: "Birincil kaynak · görev kaydı",
  excerptKind: "summary",
  excerpt: "Eagle, 20 Temmuz 1969'da Ay'a indi. Armstrong ve Aldrin yüzeye çıktı; Collins komuta modülünde kaldı.",
};

/** Editör tarafından hazırlanmış sabit örnek; otomatik araştırma çıktısı değildir. */
export function curatedSample(): CheckResult {
  return {
    report: {
      title: "Apollo 11: bir metin, üç iddia",
      summary: "İniş tarihi NASA kayıtlarıyla destekleniyor. Üç astronotun da Ay'da yürüdüğü ifadesi kayıtlarla çelişiyor. Türkiye'deki ilginin iki katına çıktığı iddiası ise bu örnekteki kaynaklarla doğrulanamıyor.",
      input: "Apollo 11, 20 Temmuz 1969'da Ay'a indi. Görevdeki üç astronot da Ay yüzeyinde yürüdü. Görevden sonra Türkiye'de astronomiye ilgi iki katına çıktı. Bu, insanlığın en etkileyici yolculuğuydu.",
      preparedAt: "2026-10-08",
      scope: "Eğitim amacıyla oluşturulmuş metin, iki NASA sayfasıyla karşılaştırıldı. Kaynaklar aynı kuruma aittir; bağımsız iki doğrulama sayılmaz. Türkiye'deki ilgi iddiası için kapsamlı bir arama yapılmadı. Kanıt pasajları Türkçe özetlerdir.",
    },
    claims: [
      {
        id: "apollo_date", text: "Apollo 11, 20 Temmuz 1969'da Ay'a indi.", verdict: "SUPPORTED",
        explanation: "NASA'nın görev kaydı, Eagle'ın 20 Temmuz'da Ay'a inişini anlatıyor [nasa_overview]. Görev sayfası da Temmuz 1969'daki Ay yüzeyi faaliyetlerini belgeliyor [nasa_mission].",
        confidence: null,
        sources: [
          { ...overview, relation: "supports" },
          { id: "nasa_mission", name: "NASA · Apollo 11", url: "https://www.nasa.gov/mission/apollo-11/", publishedAt: null, kind: "Birincil kaynak · görev sayfası", relation: "context", excerptKind: "summary", excerpt: "Görev sayfası mürettebatı, uçuş tarihlerini ve Temmuz 1969'daki Ay yüzeyi faaliyetlerini bir arada sunuyor." },
        ],
      },
      {
        id: "apollo_crew", text: "Görevdeki üç astronot da Ay yüzeyinde yürüdü.", verdict: "REFUTED",
        explanation: "Ay yüzeyine Armstrong ve Aldrin çıktı. Collins, Ay yörüngesindeki Columbia komuta modülünde kaldı. Üç kişilik mürettebat, üç kişinin de Ay'da yürüdüğü anlamına gelmiyor [nasa_overview].",
        confidence: null,
        sources: [{ ...overview, relation: "contradicts" }],
      },
      {
        id: "apollo_interest", text: "Görevden sonra Türkiye'de astronomiye ilgi iki katına çıktı.", verdict: "NOT_ENOUGH_EVIDENCE",
        explanation: "Bu örnekte kullanılan NASA sayfaları, Türkiye'deki ilginin nasıl ölçüldüğünü veya önceki ve sonraki değerlerini vermiyor. İddiayı değerlendirmek için dönem, ölçüm yöntemi ve karşılaştırılabilir veriler gerekiyor. Bu sonuç, yalnızca örneğin kaynak kapsamını ifade eder.",
        confidence: null, sources: [],
      },
    ],
    unverifiable: ["Bu, insanlığın en etkileyici yolculuğuydu."],
    unreadable: [],
  };
}
