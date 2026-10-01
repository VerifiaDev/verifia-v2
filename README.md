# verify — Web arayüzü

"Bize güvenme, kanıtlara bak." Bir metin ya da haber bağlantısındaki iddiaları kaynaklarıyla gösteren arayüz.
**Bu klasör yalnızca frontend'dir.** Backend hazır olana kadar örnek (mock) veriyle çalışır.

## Çalıştırma
1. Node.js 20.9 veya üstü kurulu olmalı (`node -v`).
2. Bu klasörde terminal açın: `npm ci`, bitince `npm run dev`.
3. Tarayıcıda http://localhost:3000

Kontrol: `npm run typecheck`, `npm run build`, `npm test` (48 test; ek paket olarak yalnızca geliştirme amaçlı `tsx` kullanır).

## Örnek veri (mock)
`NEXT_PUBLIC_API_BASE_URL` boşken mock çalışır; sayfada "örnek veri" uyarısı görünür. Kaynaklar uydurmadır.
Metne şu anahtarları yazarak durumları deneyin:
`#dogru` `#yanlis` `#yetersiz` `#celiski` `#gorus` `#hata-zamanasimi` `#hata-sunucu` `#hata-ag`.
Bağlantı sekmesinde adreste "bozuk" geçerse "bağlantı okunamadı" hatası döner.

## Gerçek backend'e bağlama
1. `.env.local` dosyası açın: `NEXT_PUBLIC_API_BASE_URL=https://backend-adresi`
2. Backend'in cevabı beklenenden farklıysa yalnızca **`lib/adapter.ts`** değişir; bileşenlere dokunulmaz.

`NEXT_PUBLIC_` değişkenleri tarayıcı paketine build sırasında eklenir. Gerçek backend adresini production build almadan önce ayarlayın; build aldıktan sonra değiştirirseniz yeniden build gerekir. Bu değişkene API anahtarı veya başka bir gizli bilgi koymayın. Backend, production site adresinden gelen isteklere CORS üzerinden izin vermelidir.

## Production sunucusunda çalıştırma

Temiz bir checkout'ta Node.js 20.9+ ve npm ile:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run start -- -p 3000
```

Gerçek backend kullanılacaksa `NEXT_PUBLIC_API_BASE_URL` değerini build komutundan önce ayarlayın. Değer boşsa sayfa mock modda kalır ve örnek veriler gösterir; bu veriler gerçek doğrulama değildir. Hosting ortamında uygulamanın Node.js sunucusunu çalıştırmasına izin verilmeli, sadece statik dosya olarak yayınlanmamalıdır.

Varsayılan sözleşme (Kişi 3 ile teyit edilecek):
- İstek: `POST {BASE}/check` gövde `{ "text": "...", "input_type": "text" | "url" }`
- Cevap: `{ "claims": [{ "id", "text", "verdict", "explanation", "sources": [{ "id", "url", "source", "text", "published_at" }] }] }`
- Hata: `{ "error": { "code", "message" } }`
- `verdict`: SUPPORTED, REFUTED, CONFLICTING, NOT ENOUGH EVIDENCE
- Açıklamadaki `[kaynak_1]` atıfları kaynak listesindeki `id` ile eşleşir.
- Güven yüzdesi (confidence) bilerek **gösterilmez**.

## Yapı
| Yer | Görev |
|---|---|
| `app/globals.css` | Tasarım sistemi (renk, yazı, boşluk, bileşen stilleri) |
| `app/page.tsx` | Sayfa: navbar, hero, giriş, nasıl çalışır, güven ilkeleri, footer |
| `components/` | Analyzer (durum), VerificationInput, AnalysisProgress, ErrorState, ResultView, ClaimItem, EvidenceCard, Explanation, VerdictSummary, Navbar, HowItWorks, TrustNotes, Footer |
| `hooks/useAnalysis.ts` | idle → submitting → (extracting_claims → retrieving_evidence → verifying) → completed \| error. Parantezdeki aşamalar yalnızca backend gerçek aşama bilgisi verirse kullanılır; vermezse `submitting`'de kalınır, sahte ilerleme gösterilmez |
| `tests/` | adapter, atıflar, girdi doğrulama, state, API (hata/zaman aşımı/bozuk cevap), uç durum görünümleri |
| `lib/` | adapter, api, mock, citations, format, input, config, types |

## Tasarım ilkeleri
Sakin, editoryal, kanıt odaklı. Gradyan/gölge/parlama yok; sonuç rengi her zaman simge + yazıyla birlikte
(✓ ✕ ≠ ?). Sahte ilerleme çubuğu yok. Sonuç sırası: iddia → sonuç → kısa açıklama → öne çıkan kanıt →
diğer kaynaklar → kaynak bağlantıları. Ek bağımlılık yok.

## Açık sorular (backend sahibine)
`POST /check` şekli, URL için `input_type`, kaynakların nesne olarak dönmesi, metin sınırı (şimdilik 5000), azami süre (şimdilik 90 sn).
GitHub bağlantısı için `lib/config.ts` içindeki `REPO_URL` doldurulur.
