# verify — Web arayüzü

"Bize güvenme, kanıtlara bak." Bir metin ya da haber bağlantısındaki iddiaları kaynaklarıyla gösteren arayüz.
**Bu klasör yalnızca frontend'dir.** Backend hazır olana kadar örnek (mock) veriyle çalışır.

## Çalıştırma
1. Node.js 20.9 veya üstü kurulu olmalı (`node -v`).
2. Bu klasörde terminal açın: `npm install`, bitince `npm run dev`.
3. Tarayıcıda http://localhost:3000

Kontrol: `npm run typecheck`, `npm run build`, `npm test` (62 test; ek paket olarak yalnızca geliştirme amaçlı `tsx` kullanır).

## Örnek veri (mock)
`NEXT_PUBLIC_API_BASE_URL` boşken mock çalışır; sayfada "örnek veri" uyarısı görünür. Kaynaklar uydurmadır.
Metne şu anahtarları yazarak durumları deneyin:
`#dogru` `#yanlis` `#yetersiz` `#celiski` `#gorus` `#asamali` `#hata-zamanasimi` `#hata-sunucu` `#hata-ag`.
`#asamali`, aşama bildiren bir backend'i taklit eder (arayüzün aşama gösterimini denemek için); diğerlerinde aşama bildirilmez.
Bağlantı sekmesinde adreste "bozuk" geçerse "bağlantı okunamadı" hatası döner.

## Gerçek backend'e bağlama
Mimari: **UI → `lib/api` (tek kapı) → mock ya da gerçek servis → adapter → UI**.
1. `.env.local` dosyası açın: `NEXT_PUBLIC_API_BASE_URL=https://backend-adresi` (boşsa mock çalışır).
2. Backend'in cevabı beklenenden farklıysa yalnızca `lib/api/contract.ts` ve `lib/api/adapter.ts` değişir; bileşenlere dokunulmaz.
3. Sözleşmenin tamamı ve backend sahibine sorular: **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)**.

`confidence` (0-1 arası) gelirse sonuçta "Modelin güven puanı: %91" olarak, doğruluk olasılığı olmadığı notuyla gösterilir; gelmezse hiçbir şey gösterilmez. Kanıt başına `score` gösterilmez.

## Yapı
| Yer | Görev |
|---|---|
| `app/globals.css` | Tasarım sistemi (renk, yazı, boşluk, bileşen stilleri) |
| `app/page.tsx` | Sayfa: navbar, hero, giriş, nasıl çalışır, güven ilkeleri, footer |
| `components/` | Analyzer (durum), VerificationInput, AnalysisProgress, ErrorState, ResultView, ClaimItem, EvidenceCard, Explanation, VerdictSummary, Navbar, HowItWorks, TrustNotes, Footer |
| `hooks/useAnalysis.ts` | idle → submitting → (extracting_claims → retrieving_evidence → verifying) → completed \| error. Parantezdeki aşamalar yalnızca backend gerçek aşama bilgisi verirse kullanılır; vermezse `submitting`'de kalınır, sahte ilerleme gösterilmez |
| `tests/` | adapter, atıflar, girdi doğrulama, state, API (hata/zaman aşımı/bozuk cevap), uç durum görünümleri |
| `lib/api/` | `index.ts` (tek kapı), `contract.ts` (ham şekiller), `adapter.ts`, `http.ts` (FastAPI), `mock/` (sahte servis ve veriler), `errors.ts`, `service.ts` |
| `lib/` | citations, format, input, config, types |

## Tasarım ilkeleri
Sakin, editoryal, kanıt odaklı. Gradyan/gölge/parlama yok; sonuç rengi her zaman simge + yazıyla birlikte
(✓ ✕ ≠ ?). Sahte ilerleme çubuğu yok. Sonuç sırası: iddia → sonuç → kısa açıklama → öne çıkan kanıt →
diğer kaynaklar → kaynak bağlantıları. Ek bağımlılık yok.

## Açık sorular (backend sahibine)
`POST /verify` şekli (backend ile geldi), URL için `input_type`, kaynakların nesne olarak dönmesi, metin sınırı (şimdilik 5000), azami süre (şimdilik 90 sn).
GitHub bağlantısı için `lib/config.ts` içindeki `REPO_URL` doldurulur.
