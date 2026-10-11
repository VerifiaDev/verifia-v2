/**
 * Yasal sayfaların (gizlilik politikası, kullanım koşulları) proje sahibinden gelecek bilgileri.
 * Boş bırakılan alan sayfada "[doldurulacak: …]" olarak görünür, sayfa "Taslak" uyarısı taşır ve arama
 * motorlarına kapatılır (noindex). Bilgi uydurulmaz: hepsi doldurulmadan sayfalar yayına alınmamalıdır.
 */
export const LEGAL = {
  /** Sitenin sorumlusu (kişi, ekip ya da kurum adı). KVKK'daki "veri sorumlusu". */
  owner: "",
  /** Gizlilik ve yasal başvurular için e-posta adresi. */
  email: "",
  /** Sunucu kayıtlarının (Render) saklanma süresi, ör. "7 gün". Backend ekibinden öğrenilecek. */
  logRetention: "",
  /** Son güncelleme tarihi (ISO). */
  updated: "2026-10-11",
};

export const LEGAL_MISSING = (Object.keys(LEGAL) as (keyof typeof LEGAL)[]).filter((k) => !LEGAL[k].trim());
export const LEGAL_COMPLETE = LEGAL_MISSING.length === 0;

export const PRIVACY_PATH = "/gizlilik";
export const TERMS_PATH = "/kullanim-kosullari";
