# verify — Web arayüzü

"Bize güvenme, kanıtlara bak." Bir metin ya da haber bağlantısındaki iddiaları kaynaklarıyla gösteren arayüz.
**Bu klasör yalnızca frontend'dir.** Geliştirmede (`npm run dev`) adres boşsa örnek (mock) veriyle çalışır; yayın derlemesinde adres yoksa inceleme yapılmaz, uydurma sonuç gösterilmez.

## Çalıştırma
1. Node.js 20.9 veya üstü kurulu olmalı (`node -v`).
2. Bu klasörde terminal açın: `npm install`, bitince `npm run dev`.
3. Tarayıcıda http://localhost:3000

Kontrol: `npm run typecheck`, `npm run build`, `npm test` — aynı üçü her gönderimde GitHub'da da çalışır (`.github/workflows/ci.yml`) (ek paket olarak yalnızca geliştirme amaçlı `tsx` kullanır).

## Gece modu
Sistem tercihi (`prefers-color-scheme`) izlenir; üstteki "Gece modu" düğmesi tercihi elle değiştirir ve tarayıcıda (`localStorage`, anahtar `verify-theme`) saklar. Renkler `app/globals.css` başındaki jetonlardır; koyu palet iki yerde tanımlıdır (`[data-theme="dark"]` ve sistem koyuyken `:root:not([data-theme="light"])`), biri değişirse diğeri de güncellenmelidir. Telefonda tarayıcı çubuğu rengi de temayı izler (`viewport.themeColor`; elle seçimde `ThemeToggle` günceller). Renk çiftleri `tests/theme.test.tsx` ile kontrast ve iki koyu bloğun eşitliği açısından denenir. Kayıtlı tercih, `app/layout.tsx` içindeki satır içi betikle ilk boyamadan önce uygulanır (yanıp sönme olmaz).

## Örnek veri (mock)
`NEXT_PUBLIC_API_BASE_URL` boşken yalnızca `npm run dev` sırasında mock çalışır; sayfada "Geliştirme" uyarısı görünür ve her iddia "Örnek veri" etiketi taşır. Kaynaklar uydurmadır; sonuç, yazdığınız içerikle değil yalnızca aşağıdaki anahtarlarla seçilir.
Metne şu anahtarları yazarak durumları deneyin:
`#dogru` `#yanlis` `#yetersiz` `#celiski` `#gorus` `#eksik` `#asamali` `#hata-zamanasimi` `#hata-sunucu` `#hata-ag`.
`#eksik`, bir iddianın sonuç değeri tanınmadığında ne olduğunu gösterir (kısmi sonuç: okunabilen iddialar gösterilir, diğeri "Sonucu gösterilemeyen iddialar" bölümüne düşer).
`#asamali`, aşama bildiren bir backend'i taklit eder (arayüzün aşama gösterimini denemek için); diğerlerinde aşama bildirilmez.
Formun altındaki örnek bağlantıları iki gruptur: sonuç türleri herkese görünür; teknik senaryolar (aşama taklidi, hata) yalnızca `npm run dev` sırasında listelenir, yayın derlemesinde gizlenir (anahtar kelimeler yine çalışır).
Örnek sonuçlar kesik çizgili çerçeve içinde gösterilir ve güven puanı örnek veride gösterilmez (uydurma yüzde gerçek sanılmasın).
**Yayındaki sitede** servis bağlı değilken form kullanılamaz; altındaki "Örnek bir incelemeyi görüntüle" bağlantısı sabit bir örnek sonucu açar. Bu sonuç kullanıcının yazdığı içerikle ilişkilendirilmez, başlığı "Örnek inceleme"dir, üstünde açıklama notu ve her iddiada "Örnek veri" etiketi vardır; kaynak adlarında "(uydurma)" yazar (`tests/sample.test.ts` bunu denetler). Servis bağlanınca bağlantı kendiliğinden kaybolur.
Bağlantı sekmesinde adreste "bozuk" geçerse "bağlantı okunamadı" hatası döner.
Gerçek backend bağlantıyla incelemeyi henüz desteklemiyor: backend bağlıyken "Bağlantı" sekmesi istek göndermez, "bağlantıyla inceleme henüz desteklenmiyor" hatası gösterir.

## Gerçek backend'e bağlama
Mimari: **UI → `lib/api` (tek kapı) → mock ya da gerçek servis → adapter → UI**.
1. `.env.local` dosyası açın: `NEXT_PUBLIC_API_BASE_URL=https://backend-adresi` (backend'in yayın adresi; backend'de `FRONTEND_ORIGIN` sitenin adresiyle ayarlı olmalı; boşsa: geliştirmede mock, yayın derlemesinde "servis bağlı değil" bilgisi). `NEXT_PUBLIC_` değişkenleri derleme sırasında koda gömülür; Vercel'de değiştirince yeniden dağıtım gerekir.
2. Backend'in cevabı beklenenden farklıysa yalnızca `lib/api/contract.ts` ve `lib/api/adapter.ts` değişir; bileşenlere dokunulmaz.
3. Sözleşmenin tamamı ve backend sahibine sorular: **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)**.
4. Güvenlik, gizlilik ve yayına hazırlık denetimi: **[docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md)**.
5. Backend için önerilen değişiklikler (kod okumasından): **[docs/BACKEND_TODO.md](docs/BACKEND_TODO.md)**.

`confidence` (0-1 arası) gelirse sonuçta "Modelin güven puanı: %91" olarak, doğruluk olasılığı olmadığı notuyla gösterilir; gelmezse hiçbir şey gösterilmez. Kanıt başına `score` gösterilmez.

## Güvenlik başlıkları
`next.config.ts` tüm sayfalara içerik güvenlik politikası (CSP) ve temel başlıkları ekler. Sayfa yalnızca siteye ve `NEXT_PUBLIC_API_BASE_URL`'deki backend'in köküne istek gönderebilir; betik, yazı tipi ve görsel yalnızca siteden yüklenir. Backend adresi değişirse yeniden derlemek yeterlidir. Siteye dış kaynaklı bir betik (analitik vb.) eklenirse politika da güncellenmelidir; aksi hâlde tarayıcı onu engeller. Vercel'in önizleme dağıtımlarındaki yorum araç çubuğu bu yüzden yüklenmez (yayındaki siteyi etkilemez).

## Yapı
| Yer | Görev |
|---|---|
| `app/globals.css` | Tasarım sistemi. Dosyanın başındaki jetonlar tek kaynaktır: renk, 8 basamaklı tip ölçeği, satır yüksekliği, 4 piksel tabanlı boşluk, köşe ve kenar. Kurallarda jeton dışı yazı boyutu kullanılmaz. Küçük ekran ayarları ilgili bölümün hemen altındadır; üzerine gelme durumları ve hareket dosyanın sonunda toplanmıştır |
| `app/layout.tsx`, `app/fonts/` | Yazı tipleri proje içinden sunulur (`next/font/local`): başlık ve alıntılar Literata, arayüz Atkinson Hyperlegible Next. Dosyalar Latin + Türkçe harflerle sınırlandırılmıştır; lisans SIL OFL (aynı klasörde) |
| `app/icon.svg`, `app/favicon.ico`, `app/apple-icon.png` | Logo yalnızca yazıdır ("verify" sözcük işareti, `components/Brand.tsx`; ad ve slogan `lib/config.ts` içinde); ayrı bir simge yok. Marka adı değişirse bu iki sabit ile aşağıdaki görseller yeter. Sekme simgesi, aynı yazı tipindeki "v" harfidir. `favicon.ico` (16/32/48) ve `apple-icon.png` (180) doğrudan `icon.svg`'den üretilmiştir; simge değişirse ikisi de yeniden üretilmeli |
| `app/page.tsx` | Sayfa: navbar, hero, giriş, nasıl çalışır, güven ilkeleri, footer |
| `app/not-found.tsx`, `app/error.tsx` | Sitede olmayan adres ve beklenmeyen çizim hatası için Türkçe sayfalar (ortak iskelet: `components/PlainPage.tsx`) |
| `app/opengraph-image.png`, `app/twitter-image.png` | Bağlantı paylaşılınca görünen görsel (1200×630, yazı logo). Slogan ya da renk değişirse yeniden üretilmeli; `.alt.txt` dosyaları görselin metin karşılığıdır |
| `lib/site.ts` | Yayın adresi. Elle yazılmaz: Vercel'in bildirdiği üretim alan adından (`VERCEL_PROJECT_PRODUCTION_URL`) okunur; canonical ve paylaşım bağlantıları buna göre kurulur. Yerelde boştur |
| `components/` | Analyzer (durum; kart + sonuç), VerificationInput (form ve inceleme sonrası özet), AnalysisProgress, ErrorState, ResultView, ClaimItem, EvidenceCard, Explanation, VerdictSummary, Legend (sonuç türleri), Icon (tek simge seti), Navbar, ThemeToggle, HowItWorks, TrustNotes, Footer, PlainPage |
| `hooks/useAnalysis.ts` | idle → submitting → (extracting_claims → retrieving_evidence → verifying) → completed \| error. Parantezdeki aşamalar yalnızca backend gerçek aşama bilgisi verirse kullanılır; vermezse `submitting`'de kalınır, sahte ilerleme gösterilmez |
| `tests/` | adapter, atıflar, girdi doğrulama, state, API (hata/zaman aşımı/bozuk cevap), uç durum görünümleri |
| `lib/api/` | `index.ts` (tek kapı), `contract.ts` (ham şekiller), `adapter.ts`, `http.ts` (FastAPI), `mock/` (sahte servis ve veriler), `errors.ts`, `service.ts` |
| `lib/` | citations, format, input, config, types |

## Tasarım ilkeleri
Sakin, editoryal, kanıt odaklı. Yapı ince çizgilerle kurulur; gölge, gradyan ve parlama yok. Sayfada tek kutu vardır (inceleme kartı); sonuç kartın dışında, kendi bölümünde açılır ve inceleme bitince giriş tek satırlık özete iner.
- **Sonuç:** renk her zaman simge + yazıyla birlikte gelir. Sıra: iddia → sonuç → açıklama → kanıtlar → kaynak bağlantısı. Sonuç kutusunda etiketin anlamı yinelenmez (anlamlar "Sonuç türleri" listesindedir); yalnızca "yeterli kanıt yok" sonucunda "bu, iddianın yanlış olduğu anlamına gelmez" uyarısı gösterilir.
- **Kanıt:** "Dayandığımız kanıtlar" yalnızca açıklamanın atıf yaptığı kaynaklar için söylenir; atıf yoksa başlık "Bulunan kaynaklar" olur. Kaynağın adı ya da tarihi gelmediyse satır tek sütundur ve "belirtilmemiş" yazılmaz.
- **Bekleme:** sahte ilerleme yok. Backend aşama bildirmiyorsa adım listesi gösterilmez; yalnızca geçen süre sayılır (30 saniyeden sonra "sürüyor, vazgeçebilirsiniz" notu eklenir).
- **Tek birincil eylem:** hata gösterilirken formdaki düğme ikincil görünür; birincil eylem hata panelindedir.
- **Bağlantı sekmesi:** yalnızca servis destekliyorsa görünür (`apiInfo.urlSupported`); başlık altı metin de buna göre değişir.
- **Rakamlar:** düz metinde orantılıdır; eş genişlikli rakam yalnızca sayaçlarda (`.tnum`).
- **Simgeler:** tek set (`components/Icon.tsx`), yalnızca çizgi, tek kalınlık; her zaman yazıyla birlikte.
- **Hareket:** yalnızca renk geçişi ve içerik ilk göründüğünde kısa bir giriş; yükselme, gölge, kaydırma animasyonu yok. "Hareketi azalt" tercihi desteklenir.
- **Duyuru:** bekleme, hata ve sonuç odakla duyurulur (odak ilgili başlığa taşınır); panelin tamamı ayrıca canlı bölge olarak okunmaz. Yalnızca backend'in bildirdiği aşama değişimi kısa bir durum satırıyla okunur.
- **Dar ekran:** sonuç türleri kapalı bir açılır satırdadır; tablette üst bant tek satırdır.
Ek bağımlılık yok.

## Açık sorular (backend sahibine)
Backend sözleşmesi koddan okundu (`MertBulut11/verify`, `87ec895`): `POST /verify`, 10 000 karakter (arayüz backend_v2 canlıya çıkana kadar 3.000 ile sınırlar), hata gövdesi, CORS listesi. Teyitsiz kalanlar: azami süre (şimdilik 90 sn), atıf biçimi, tarih biçimi, tek iddia hatasında davranış. Tam liste ve sorular: [docs/API_CONTRACT.md](docs/API_CONTRACT.md).
GitHub bağlantısı için `lib/config.ts` içindeki `REPO_URL` doldurulur.

## Apollo 11 rapor önizlemesi (8 Ekim 2026)

Sabit ürün örneği artık `lib/sample-report.ts` içindeki, gerçek NASA kaynaklarına bağlanan editör raporudur. Geliştirme senaryolarındaki uydurma kaynaklar (`lib/api/mock/`) bundan ayrıdır. Örnekteki kaynak pasajları Türkçe özet olarak gösterilir; arama yapılmış veya API çalışmış gibi sunulmaz. `?example=apollo-11` hazır raporu ana sayfada açar; `/ornek/apollo-11` aynı raporun JavaScript olmadan da okunan, paylaşılabilir sayfasıdır ("Örnek bağlantısını kopyala" bu adresi verir).

Rapor araçları metni ve kaynakları birlikte kopyalar; yazdırma/PDF kaydetme tarayıcının yazdırma menüsünü açar. Gerçek raporlar sunucuda saklanmadığı için onlara paylaşım bağlantısı üretilmez. Geri bildirim aracı gönderim yapmayan bir taslak sunar. Gizlilik ve API ile ilgili açık kararlar: `docs/REPORT_DESIGN.md`.
