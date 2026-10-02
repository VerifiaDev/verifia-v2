# verify — Web arayüzü

"Bize güvenme, kanıtlara bak." Bir metin ya da haber bağlantısındaki iddiaları kaynaklarıyla gösteren arayüz.
**Bu klasör yalnızca frontend'dir.** Geliştirmede (`npm run dev`) adres boşsa örnek (mock) veriyle çalışır; yayın derlemesinde adres yoksa inceleme yapılmaz, uydurma sonuç gösterilmez.

## Çalıştırma
1. Node.js 20.9 veya üstü kurulu olmalı (`node -v`).
2. Bu klasörde terminal açın: `npm install`, bitince `npm run dev`.
3. Tarayıcıda http://localhost:3000

Kontrol: `npm run typecheck`, `npm run build`, `npm test` (72 test; ek paket olarak yalnızca geliştirme amaçlı `tsx` kullanır).

## Örnek veri (mock)
`NEXT_PUBLIC_API_BASE_URL` boşken yalnızca `npm run dev` sırasında mock çalışır; sayfada "Geliştirme" uyarısı görünür ve her iddia "Örnek veri" etiketi taşır. Kaynaklar uydurmadır; sonuç, yazdığınız içerikle değil yalnızca aşağıdaki anahtarlarla seçilir.
Metne şu anahtarları yazarak durumları deneyin:
`#dogru` `#yanlis` `#yetersiz` `#celiski` `#gorus` `#asamali` `#hata-zamanasimi` `#hata-sunucu` `#hata-ag`.
`#asamali`, aşama bildiren bir backend'i taklit eder (arayüzün aşama gösterimini denemek için); diğerlerinde aşama bildirilmez.
Formun altındaki örnek bağlantıları iki gruptur: sonuç türleri herkese görünür; teknik senaryolar (aşama taklidi, hata) yalnızca `npm run dev` sırasında listelenir, yayın derlemesinde gizlenir (anahtar kelimeler yine çalışır).
Örnek sonuçlar kesik çizgili çerçeve içinde gösterilir ve güven puanı örnek veride gösterilmez (uydurma yüzde gerçek sanılmasın).
Bağlantı sekmesinde adreste "bozuk" geçerse "bağlantı okunamadı" hatası döner.

## Gerçek backend'e bağlama
Mimari: **UI → `lib/api` (tek kapı) → mock ya da gerçek servis → adapter → UI**.
1. `.env.local` dosyası açın: `NEXT_PUBLIC_API_BASE_URL=https://backend-adresi` (boşsa: geliştirmede mock, yayın derlemesinde "servis bağlı değil" bilgisi). `NEXT_PUBLIC_` değişkenleri derleme sırasında koda gömülür; Vercel'de değiştirince yeniden dağıtım gerekir.
2. Backend'in cevabı beklenenden farklıysa yalnızca `lib/api/contract.ts` ve `lib/api/adapter.ts` değişir; bileşenlere dokunulmaz.
3. Sözleşmenin tamamı ve backend sahibine sorular: **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)**.

`confidence` (0-1 arası) gelirse sonuçta "Modelin güven puanı: %91" olarak, doğruluk olasılığı olmadığı notuyla gösterilir; gelmezse hiçbir şey gösterilmez. Kanıt başına `score` gösterilmez.

## Yapı
| Yer | Görev |
|---|---|
| `app/globals.css` | Tasarım sistemi (renk, yazı, boşluk, bileşen stilleri) |
| `app/layout.tsx`, `app/fonts/` | Yazı tipleri proje içinden sunulur (`next/font/local`): başlık ve alıntılar Literata, arayüz Atkinson Hyperlegible Next. Dosyalar Latin + Türkçe harflerle sınırlandırılmıştır; lisans SIL OFL (aynı klasörde) |
| `app/icon.svg`, `app/favicon.ico`, `app/apple-icon.png` | Sekme simgesi seti. `favicon.ico` (16/32/48) ve `apple-icon.png` (180) doğrudan `icon.svg`'den üretilmiştir; simge değişirse ikisi de yeniden üretilmeli |
| `public/brand/` | ALTERNATİF logo önerisi ("Logo A: Atıf", sitede kullanılmıyor): `verify-logo.svg`, `verify-logo-koyu-zemin.svg`, `verify-logo-tek-renk.svg`, `verify-isaret.svg`. Bileşen karşılığı: `components/BrandMark.tsx` |
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
