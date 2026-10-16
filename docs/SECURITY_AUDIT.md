# Güvenlik, gizlilik ve yayına hazırlık denetimi

**Tarih:** 8 Ekim 2026
**Kapsam:** frontend (`efeeyildiz91/verify-test`, `main`) · backend (`MertBulut11/verify`, `87ec895`, yalnızca okundu, değiştirilmedi) · canlı ortam (Vercel `verify-test-swart.vercel.app`, Render `verify-wb28.onrender.com`).

Bu belge teknik bir denetimdir, hukuki görüş değildir. KVKK maddeleri "kontrol edilmesi gerekenler" olarak listelenmiştir; uygunluk kararı için bir hukukçuya danışılmalıdır.

## Nasıl test edildi

- **Koddan okunanlar:** iki deponun tamamı ve git geçmişi (frontend 33, backend 12 commit), bağımlılıklar (`npm audit`), üretim derlemesi (`.next/static`) ve kaynak eşlemeleri (source map).
- **Canlıda denenenler:** frontend ve backend yanıt başlıkları; maliyet doğurmayan geçersiz istekler (yanlış method, eksik alan, yanlış tip, boş metin, 10.001 karakter, bozuk JSON, olmayan yol); izin verilmeyen kökenden CORS denemesi; arayüzden XSS denemesi içeren tek bir gerçek inceleme isteği.
- **Bilerek yapılmayanlar:** yük ve çok sayıda istek testi (gerçek API kotası harcar ve tek istek bile sunucuyu meşgul ediyor), büyük gövdeyle hizmet engelleme denemesi, başka adreslere SSRF denemesi. Bunlar koddan değerlendirildi.

## Mimari ve veri akışı

```
Tarayıcı ──(yalnızca metin)──▶ Render: FastAPI /verify ──▶ Groq (dil modeli: iddia çıkarma + karar)
   ▲                                             ├──▶ Tavily (web araması, iddia başına en fazla 5 sorgu)
   └── Vercel (statik sayfa)                    └──▶ arama sonucundaki sayfalar (requests + başsız Chromium)
```

- **Kimlik doğrulama, oturum, çerez, veritabanı ve dosya yükleme yok.** Kullanıcı hesabı olmadığı için IDOR/BOLA gibi "başkasının verisine erişme" riskleri bu sürümde yok.
- **Gizli anahtarlar:** `GROQ_API_KEY` ve `TAVILY_API_KEY` yalnızca backend'in ortam değişkenlerinde durur. Frontend'in tek değişkeni `NEXT_PUBLIC_API_BASE_URL`, herkese açık bir adrestir.

## Bulgular

### 🔴 KRİTİK

**K1. Backend herkese açık ve sınırsız; anahtarlarınız üzerinden maliyet çıkarılabilir** (backend, değiştirilmedi)
- **Sorun:** `/verify` için kimlik doğrulama, istek sınırı, kota ve eşzamanlılık tavanı yok. CORS yalnızca tarayıcıyı durdurur; `curl` ya da bir betik doğrudan istek gönderebilir.
- **Dosya/satır:**
  - `backend/main.py:110-206`
  - `backend/search_retrieval.py:1925`: iddia başına 5 sorgu.
  - `backend/search_retrieval.py:1940`: `search_depth="advanced"`.
- **Risk ve etkisi:**
  - Tek bir 10.000 karakterlik istek onlarca iddiaya bölünebilir. Her iddia en fazla 5 gelişmiş Tavily araması, en fazla 30 sayfa indirme ve bir Groq çağrısı demektir.
  - Bir betik Groq ve Tavily kotasını tüketebilir ya da fatura çıkarabilir. Hizmet de kullanılamaz hale gelir.
- **Önerilen çözüm (backend ekibi):**
  - IP başına istek sınırı (ör. `slowapi`) ve tek seferde bir inceleme (eşzamanlılık sınırı).
  - İstek başına en fazla iddia sayısı.
  - Günlük toplam kota.
  - Aynı iddia için önbellek.
  - Groq ve Tavily panellerinde harcama ve kullanım sınırı.
  - Gerekirse bot koruması (ör. Cloudflare Turnstile).
- **Test yöntemi:** Koddan doğrulandı. Canlıda yük testi bilerek yapılmadı.

**K2. Tek bir inceleme sunucunun tamamını kilitliyor; kısa bir iddia 10 dakikada bile bitmedi** (backend, değiştirilmedi)
- **Sorun:**
  - "Ankara 1923'ten beri Türkiye'nin başkentidir." isteği arayüzün 90 saniyelik sınırını aştı.
  - Aynı istek doğrudan gönderildiğinde 10 dakika içinde yanıt gelmedi.
  - Bu sırada `/health` 15 saniyede, 10. dakikada da 20 saniyede yanıt vermedi. Aynı durum ilk denemede de görüldü: başka bir inceleme sürerken `/` ve `/health` 40 saniyede yanıt vermedi.
- **Dosya/satır:**
  - `backend/search_retrieval.py:2045-2084`: her sayfa için `requests`, gerekirse her URL için yeni bir başsız Chromium açılıyor.
  - `sentence-transformers` modeli belleğe yükleniyor.
  - Sunucu planının (Render) işlemci ve bellek sınırları belirleyici; değerleri burada doğrulanmadı.
- **Risk ve etkisi:**
  - Tek bir kullanıcı (ya da saldırgan) hizmeti herkes için durdurabilir.
  - Arayüz 90 saniyede vazgeçse bile backend işi sürdürür, yani kota harcanır.
  - Bu hâliyle gerçek kullanıcılar sonuç alamaz.
- **Önerilen çözüm (backend ekibi):**
  - Daha güçlü sunucu planı.
  - Chromium'u kapatma ya da tek bir tarayıcıyı yeniden kullanma.
  - Sayfa başına ve istek başına toplam süre sınırı.
  - İddiaları paralel ve sınırlı işleme.
  - Kuyruk + iş kimliği (iş başlat, durumu sorgula) yaklaşımı.
- **Test yöntemi:** Yukarıdaki istek tarayıcıdan zamanlandı. Aynı anda `/health` çağrıldı.
- **Frontend'de yapılan (hafifletme, çözüm değil):** Her incelemeden önce `GET /health` en fazla 60 saniye beklenir. Yanıt gelmezse inceleme isteği hiç gönderilmez ve "Sunucu şu an yanıt vermiyor" gösterilir. Böylece arayüzden yapılan "Yeniden dene" tıklamaları kilitli sunucuya yeni pahalı istekler yığmaz. Doğrudan API'ye istek atan betikleri durdurmaz; asıl çözüm backend'dedir. Test: `tests/api.test.ts` → "sağlık denetimi süresinde yanıt gelmezse…".

### 🟠 YÜKSEK

**Y1. Kullanıcı metni üçüncü taraflara gidiyor; kullanıcı bilgilendirilmiyordu** (frontend: düzeltildi; hukuki metin: açık)
- **Sorun:** Metnin tamamı Groq'a, iddialar Tavily'ye (arama sorgusu olarak) gönderiliyor. Arayüz bunu söylemiyordu. Gizlilik ya da aydınlatma metni yok.
- **Dosya/satır:** `components/VerificationInput.tsx` (alan ipucu), `components/Footer.tsx`.
- **Risk ve etkisi:** Kullanıcı kişisel veri içeren metin yapıştırabilir. Bu veri yurt dışındaki servislere aktarılır. KVKK bakımından aydınlatma ve yurt dışına aktarım soruları doğar (aşağıdaki KVKK listesine bakın).
- **Yapılan:** Alanın açıklamasına, ekran okuyucuya da bağlı olarak şu not eklendi: "Metin, incelenmek için sunucumuza ve yapay zekâ ile web araması yapan dış servislere gönderilir; kişisel bilgi (ad, telefon, adres, kimlik numarası) içeren metin yapıştırmayın."
- **Açık:** Saklama süresi ve sorumlu kişi/iletişim bilgisi bilinmiyor; uydurulmadı. Aydınlatma metni proje sahibince yazılmalı.
- **Test yöntemi:** `tests/render.test.tsx` → "metnin dış servislere gittiğini söyler…".

**Y2. Arama sonuçlarındaki adresler sınırsız indiriliyor** (backend, değiştirilmedi)
- **Sorun:** `requests.get(..., allow_redirects=True)` ve başsız Chromium şunları denetlemiyor: özel/iç ağ adresleri (127.0.0.1, 169.254.169.254, 10.x), yanıt boyutu ve sayfa sayısı. Adresler Tavily sonuçlarından geliyor. Kullanıcı yalnızca dolaylı etkileyebilir.
- **Dosya/satır:** `backend/search_retrieval.py:2045-2084`.
- **Risk ve etkisi:** Çok büyük bir sayfa belleği doldurabilir. Yönlendirme ile iç adrese ulaşma ihtimali düşük ama sıfır değil (SSRF).
- **Önerilen çözüm:** Yalnızca `https`. Çözümlenen IP özel/yerel ise reddet. `stream=True` ile en fazla örneğin 2 MB oku. Yönlendirme sayısını sınırla. Chromium'u ağ ve kaynak kısıtlarıyla çalıştır.
- **Test yöntemi:** Koddan değerlendirildi; canlıda denenmedi.

### 🟡 ORTA

**O1. `.gitignore` yalnızca `.env*.local` dosyalarını dışlıyordu** (frontend: düzeltildi)
- **Sorun:** Bir `.env` ya da `.env.production` dosyası yanlışlıkla commit edilebilirdi.
- **Yapılan:** `.env` ve `.env.*` dışlandı (`!.env.example` hariç).
- **Test yöntemi:** `tests/secrets.test.ts`.

**O2. Gizli anahtar sızıntısına karşı kalıcı bir test yoktu** (frontend: düzeltildi)
- **Yapılan:** `tests/secrets.test.ts` şunları her test çalıştırmasında (CI dahil) denetler:
  - Depodaki her dosyada anahtar biçimli değer (Groq, Tavily, OpenAI, GitHub, Google, AWS, özel anahtar) olmaması.
  - Yalnızca `.env.example`'ın izlenmesi ve boş olması.
  - Kodun yalnızca izin verilen ortam değişkenlerini okuması.
  - `NEXT_PUBLIC_` adlarında KEY/SECRET/TOKEN geçmemesi.

**O3. Backend hata ayrıntıları yalnızca `print` ile, istek bağlamı olmadan yazılıyor** (backend)
- **Sorun:** `backend/main.py:210` istisna türünü ve mesajını yazdırıyor. Bazı kütüphane hataları iletilen metnin parçalarını içerebilir. Hangi istek ya da iddia olduğu belli değil.
- **Önerilen çözüm:** `logging` ile seviye, istek kimliği ve aşama yaz. Kullanıcı metnini loglama. Sunucu loglarının kimlerce okunabildiğini ve saklama süresini belirle.

**O4. Hata türleri ayrılmıyor** (backend)
- **Sorun:** Boş, eksik ve fazla uzun metin aynı `422 VALIDATION_ERROR` ile dönüyor. Dış servis hataları ve kota aşımı aynı `500 VERIFY_FAILED` ile dönüyor. `429` yok.
- **Etkisi:** Kullanıcıya doğru yönlendirme yapılamıyor.

**O5. İstek gövdesi boyutu için açık sınır yok** (backend)
- **Sorun:** `max_length=10000` gövde çözümlendikten sonra uygulanır (`backend/main.py:62`).
- **Önerilen çözüm:** Önündeki katmanda (ör. 64 KB) gövde sınırı.
- **Test yöntemi:** 10.001 karakter canlıda `422` döndü. Büyük gövde bilerek denenmedi.

### 🟢 DÜŞÜK

- **D1. Frontend CSP'si `'unsafe-inline'` içeriyor** (`next.config.ts:32-33`).
  - Statik sayfada nonce kullanılamadığı için bilinçli bir tercih (Next.js'in belgelenen kalıbı).
  - Diğer kısıtlar güçlü: `connect-src` yalnızca site + backend, `frame-ancestors 'none'`, `object-src 'none'`.
  - Kullanıcı ya da backend verisi hiçbir yerde HTML olarak basılmıyor. Tek `dangerouslySetInnerHTML` sabit tema betiğidir (`app/layout.tsx:68`).
- **D2. `allow_credentials=True` gereksiz** (`backend/main.py:41`). Çerez yok. Kapatılmalı.
- **D3. `/docs` ve `/openapi.json` herkese açık.** API şemasını gösterir; gizli bilgi yok. Yayında kapatılabilir: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`.
- **D4. Backend yanıtlarında `X-Content-Type-Options` ve `Strict-Transport-Security` yok.** JSON API için etkisi düşük.
- **D5. Frontend'de sabit sayfanın yanıtında `access-control-allow-origin: *` var.** Bu Vercel'in statik dosyalar için varsayılanı. Sayfa zaten herkese açık, kimlik bilgisi yok, etkisi yok.
- **D6. `app/error.tsx:12` beklenmeyen hatayı tarayıcı konsoluna yazar.** Üretimde Next.js ayrıntıyı gizler, gizli bilgi taşımaz.
- **D7. `requirements.txt` sürümleri sabitlenmemiş** (backend). Tekrarlanabilir kurulum ve tedarik zinciri riski.
- **D8. Frontend'de lint betiği yok.** Yeni bağımlılık eklememek için kurulmadı. Tip denetimi (`tsc --strict`) ve 126 test CI'da çalışıyor.
- **D9. `next` 16.4.0 yayımlanmış** (kurulu 16.3.8). `npm audit` 0 açık gösterdiği için güncelleme bu denetimde yapılmadı.
- **D10. Sonuç ekranında kaynak yokken de "yukarıdaki kaynakları kontrol edin" yazıyordu.** Düzeltildi.

## Kontrol edilip sorun bulunmayanlar

| Konu | Sonuç |
|---|---|
| Frontend kodunda, derlemede (`.next/static`) ve git geçmişinde anahtar | Yok |
| Source map | Üretimde yok (0 dosya) |
| Backend deposunda ve geçmişinde anahtar | Yok. Yalnızca `ai-engine/.env.example` (değer: `your_key_here`). `.gitignore` `.env` dosyalarını dışlıyor |
| Tarayıcıya giden istekte anahtar (başlık, gövde, URL) | Yok. İstek yalnızca `{"text": …}` |
| localStorage / sessionStorage / çerez | Yalnızca tema tercihi (`verify-theme`); çerez yok |
| XSS | React kaçışı; `<img onerror>` ve `<script>` denemesi çalışmadı (başlık değişmedi, öğe oluşmadı). Kaynak bağlantıları yalnızca `http/https` ise tıklanabilir, `rel="noopener noreferrer"` |
| Açık yönlendirme | Kodda yönlendirme yok; uygulama içi bağlantılar yalnızca `#…` |
| Frontend başlıkları (canlı) | CSP, HSTS (`max-age=63072000; includeSubDomains; preload`), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` var |
| CORS (canlı) | İzin verilmeyen kökenden istek tarayıcıda engellendi; `*` yok |
| Yanlış method / eksik alan / yanlış tip / boş / aşırı uzun / bozuk JSON (canlı) | `405` / `422` / `422` / `422` / `422` / `422`; boşluk yalnız metin `400`. Yanıtlarda yığın izi, yol ya da ortam bilgisi yok |
| `npm audit` | 0 açık |

## KVKK açısından teknik olarak kontrol edilmesi gerekenler

Hukuki görüş değildir.

1. **Aydınlatma metni:** Hangi verinin (yapıştırılan metin), hangi amaçla, hangi hukuki sebeple işlendiği; kimlere aktarıldığı; saklama süresi; başvuru yolu. Şu an yok.
2. **Yurt dışına aktarım:** Metin Groq'a, iddialar Tavily'ye ve barındırma sağlayıcılarına (Render, Cloudflare, Vercel) gidiyor. Bu servislerin veri konumu ve sözleşme koşulları kontrol edilmeli.
3. **Üçüncü taraf saklama:** Groq ve Tavily'nin gönderilen içeriği saklayıp saklamadığı, modeli eğitmek için kullanıp kullanmadığı kendi koşullarından doğrulanmalı.
4. **Loglar:** Render ve Vercel loglarında ne tutulduğu (IP adresi kişisel veri sayılabilir), ne kadar süre ve kimin erişimiyle.
5. **Veri en aza indirme:** Kullanıcı metni backend'de saklanmıyor (kodda veritabanı ya da dosya yazma yok). Bu korunmalı.
6. **Özel nitelikli veri:** Sağlık, din, siyasi görüş gibi içerikler yapıştırılabilir; aydınlatma metninde ele alınmalı.
7. **Analitik/çerez:** Şu an yok. Eklenirse çerez bildirimi ve açık rıza gerekebilir.
8. **İletişim:** Veri sorumlusunun adı ve iletişim adresi sitede yer almalı.
