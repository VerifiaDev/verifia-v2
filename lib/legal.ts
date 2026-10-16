/**
 * Yasal sayfaların (gizlilik politikası, kullanım koşulları, çerez politikası) ve alt bilgideki "hizmeti sunan"
 * satırının tek kaynağı. Bilgiler proje sahibinden gelir; uydurulmaz.
 *
 * E-posta boşken:
 * - yayındaki sitede (Vercel production) yasal sayfalar 404 döner ve hiçbir yerden bağlantı verilmez;
 * - önizlemede ve yerelde sayfalar "Taslak" uyarısıyla, arama motorlarına kapalı (noindex) olarak açılır.
 * E-posta yazılınca üç sayfa, alt bilgi bağlantıları ve site haritası kayıtları aynı derlemede yayına girer.
 * Hukuki metin değildir; yayından önce bir hukukçuya okutulması önerilir.
 */
export const LEGAL = {
  /** Hizmeti sunan ve KVKK'daki "veri sorumlusu". 16 Ekim 2026'da proje sahibi bildirdi. */
  owner: "verify ekibi",
  members: ["Osman Efe Yıldız", "Mert Bulut", "Mehmet Fatih Çelebi", "Ali Arda Sarı"],
  /** Gizlilik ve yasal başvurular için e-posta adresi (16 Ekim 2026, proje sahibi bildirdi). */
  email: "verifiadev@gmail.com",
  /** Son güncelleme tarihi (ISO). */
  updated: "2026-10-16",
};

/** "Ali, Veli ve Ayşe" biçiminde ad listesi. */
export function joinNames(names: string[]): string {
  return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} ve ${names[names.length - 1]}`;
}

export const LEGAL_MISSING: string[] = [
  ...(LEGAL.owner.trim() ? [] : ["owner"]),
  ...(LEGAL.members.length ? [] : ["members"]),
  ...(LEGAL.email.trim() ? [] : ["email"]),
];
/** Bütün bilgiler tamam: yasal sayfalar yayındadır ve sitenin her yerinden bağlantı verilir. */
export const LEGAL_COMPLETE = LEGAL_MISSING.length === 0;

/** Yalnızca sunucu tarafında doğru çalışır (VERCEL_ENV istemciye açık değildir). */
export function legalPagesHidden(): boolean {
  return !LEGAL_COMPLETE && process.env.VERCEL_ENV === "production";
}

export const PRIVACY_PATH = "/gizlilik";
export const TERMS_PATH = "/kullanim-kosullari";
export const COOKIES_PATH = "/cerez-politikasi";

export const LEGAL_PAGES = [
  { path: PRIVACY_PATH, label: "Gizlilik politikası" },
  { path: TERMS_PATH, label: "Kullanım koşulları" },
  { path: COOKIES_PATH, label: "Çerez politikası" },
] as const;

/** Sitenin kullandığı dış hizmetler ve kendi gizlilik metinleri (gizlilik ve çerez sayfalarında listelenir). */
export const PROVIDERS = {
  vercel: { name: "Vercel", policy: "https://vercel.com/legal/privacy-notice" },
  render: { name: "Render", policy: "https://render.com/privacy" },
  groq: { name: "Groq", policy: "https://console.groq.com/docs/your-data" },
  tavily: { name: "Tavily", policy: "https://tavily.com/privacy" },
} as const;
