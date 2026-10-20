# API sözleşmesi (frontend'in anladığı hâli)

> **Durum: büyük ölçüde teyitli.** Yol, istek, cevap, hata gövdesi, metin sınırı ve CORS listesi backend koddan okundu
> (`MertBulut11/verify`, `backend/main.py`, `87ec895`, 8 Ekim). Kod okumaktır; canlı bir backend ile deneme değildir.
> "Teyit edilmemiş" diye işaretlenen her şey hâlâ frontend'in varsayımıdır.
> Kodda karşılığı: `lib/api/contract.ts` (şekiller), `lib/api/adapter.ts` (çeviri), `lib/api/http.ts` (istek).

> **11 Ekim denetimi (canlıda doğrulandı):** `https://verify-wb28.onrender.com` üzerinde çalışan backend hâlâ **1.0.0**
> (`GET /openapi.json` → `info.version: "1.0.0"`; `GET /health` → `{"status":"ok","service":"verify-backend"}`;
> `POST /verify/stream` → 404). Aşağıdaki backend_v2 notları canlıda **geçerli değildir**; v2 yayına alınınca
> `GET /openapi.json` sürümü 2.0.0 olmalıdır. Canlı hata gövdeleri sözleşmeyle aynı: boş gövde, yanlış tip, bozuk JSON ve
> 10.001 karakter `422 VALIDATION_ERROR`; yalnız boşluk `400 EMPTY_TEXT`. Uyuyan sunucunun ilk `/health` yanıtı
> yaklaşık 132 saniyede geldi (tek ölçüm). Gerçek bir inceleme isteği bu denetimde gönderilmedi.

> **10 Ekim güncellemesi — backend_v2 (`MertBulut11/verify-v2`, `backend_v2/`, `1d907e8`):** kod okundu, canlı deneme yapılmadı.
> - Yol/istek aynı: `POST /verify` `{ "text" }` (en çok 10 000 karakter). Cevap: `{ status:"ok", results:[…], partial, timings }`.
> - **Yeni:** her iddiada `status` (`ok` | `error` | `timeout` | `skipped`). `ok` dışında `verdict` **null** gelir; arayüz bunu hüküm olarak değil "İncelenemeyen iddialar" olarak gösterir (`unfinished`). Üst düzey `partial`, `timings`, iddiadaki `cached`, `timings_ms`, `error_code`, `failed_stage`, `detail` okunmaz.
> - Hata gövdesi `{ status:"error", error:"KOD", message, detail? }`; yeni kodlar: `EXTRACTION_TIMEOUT` (504), `EXTRACTION_FAILED` (502), `CONFIG_ERROR` (503), `VALIDATION_ERROR` (422), `EMPTY_TEXT` (400), `VERIFY_FAILED` (500).
> - Kaynak biçimi aynı (`id: "source_N"`, `url`, `text`); varsayılan `lite` arayıcı ayrıca `title`, `domain`, `published_date` ve `retrieval_score` verir (`retrieval_demo_lite/search_retrieval_lite.py`, kaynak sözlüğü; 11 Ekim'de koddan düzeltildi). Güven puanı yok. `published_date` arama servisinin verdiği değerdir; arayüz yalnızca ISO 8601 ve RFC 2822 biçimlerini gösterir. CORS: koddaki sabit listede `https://verify-test-swart.vercel.app` var; resmî site `https://verifia-pi.vercel.app` ise Render'daki `FRONTEND_ORIGIN` ile izinlenir (20 Ekim'de canlıda doğrulandı).
> - **Kullanılmayan fırsat:** `POST /verify/stream` (SSE) gerçek aşamaları ve iddiaları geldikçe verir; arayüz henüz tek istekle çalışıyor.
> - Backend'in yayın adresi değişirse Vercel'de `NEXT_PUBLIC_API_BASE_URL` güncellenip yeniden dağıtılmalıdır.

> **16 Ekim güncellemesi — sözleşme artık testle korunuyor (`backend_v2/` bu depoda):**
> - Bu belgedeki backend_v2 kuralları kod olarak `backend_v2/tests/contract.py` içindedir. Aynı denetimler hem çevrimdışı
>   testlerde (`backend_v2/tests/test_contract.py`, sahte LLM/arama) hem de canlı sunucuya karşı
>   (`python backend_v2/check_all.py --url ...`) uygulanır. Sözleşmeyi değiştiren her backend değişikliği CI'da kırmızı olur.
> - Gerçek tarayıcı + yayın derlemesi frontend + gerçek backend uygulaması birlikte `e2e/` testinde denenir
>   (`.github/workflows/integration.yml`): istek şekli, iki hüküm, kısmi sonuç, `502` hata ekranı, CORS ve CSP.
> - Yeni: her yanıtta `X-Request-ID`, gerçek aşamaları veren `POST /verify/stream` (aşağıda "Akış"), iddia başına hata
>   kodları (aşağıda "İddia durumu"). Canlı sunucunun sürümü bu güncellemede yeniden denetlenmedi; 11 Ekim'de 1.0.0 idi.

## İstek

`POST {NEXT_PUBLIC_API_BASE_URL}/verify` — `Content-Type: application/json`

```json
{ "text": "İncelenecek metin" }
```

- Backend: `text` zorunlu, 1–10 000 karakter (`VerifyRequest`); boşluklar kırpılınca boşsa `400 EMPTY_TEXT`.
- Arayüz **3.000 karakterle** sınırlar (`MAX_INPUT_LENGTH`). 11 Ekim: canlıdaki backend hâlâ 1.0.0 (`GET /openapi.json`); o sürüm iddia sayısını ve toplam süreyi sınırlamadığı için sınır 10.000'den geri alındı. backend_v2 (en çok 8 iddia, kalanı `skipped`) canlıya çıkınca yeniden 10.000 yapılabilir.
- Frontend yalnızca `text` gönderir. Adresin sonundaki `/` atılır.
- **Bağlantı (URL) ile inceleme backend'de yok.** Arayüzdeki "Bağlantı" sekmesi gerçek servise istek göndermez;
  kullanıcıya "bağlantıyla inceleme henüz desteklenmiyor" hatası (`URL_UNSUPPORTED`, arayüzün kendi kodu) gösterilir.
  Eski öneri `input_type: "text" | "url"` alanıydı; backend bunu kabul edene kadar gönderilmez.

### Ön denetim: `GET /health`

Frontend sayfa açılınca sunucuyu uyandırmak için bir kez `GET {BASE}/health` gönderir (ön ısıtma; yanıtı beklenmez).
Her incelemeden önce de `GET {BASE}/health` çağırır ve en fazla 150 saniye bekler (`HEALTH_TIMEOUT_MS`; 11 Ekim ölçümünde uyuyan sunucu yaklaşık 132 saniyede yanıt verdi). Yanıt 5 saniyeden uzun sürerse arayüz "Sunucunun yanıtı bekleniyor" der.
Yanıt gelmezse inceleme isteği **gönderilmez** ve kullanıcıya `SERVER_BUSY` ("Sunucu şu an yanıt vermiyor") gösterilir.
Sebep: backend bir incelemeyi işlerken başka isteklere yanıt vermeyebiliyor; kilitli sunucuya ikinci bir pahalı istek
göndermek kotayı boşa harcar (bkz. docs/SECURITY_AUDIT.md, K2). Herhangi bir HTTP yanıtı (404 dahil) gelirse inceleme gönderilir.

## Başarılı cevap (HTTP 200)

Backend'in (koddan okunan) şekli:

```json
{ "status": "ok", "results": [ {
    "claim_id": "…", "claim": "…", "is_verifiable": true, "verdict": "SUPPORTED",
    "explanation": "…", "used_sources": ["source_1"],
    "sources": [ { "id": "source_1", "title": "…", "site_name": "…", "domain": "…", "url": "https://…",
                   "published_date": null, "retrieval_score": 0.8, "text": "…" } ]
} ] }
```

Doğrulanamayan iddiada `is_verifiable: false`, `verdict: null`, `explanation: null`, `sources: []` gelir.

backend_v2 ayrıca şunları ekler (testle doğrulanır, `backend_v2/tests/contract.py`):

```json
{ "status": "ok", "partial": false, "timings": { "extract_ms": 812, "total_ms": 2310 },
  "results": [ { "...": "yukarıdaki alanlar", "status": "ok", "cached": false,
                 "timings_ms": { "retrieval_ms": 1200, "verify_ms": 900 } } ] }
```

- `partial` yalnızca en az bir iddianın `status` değeri `ok` değilse `true`dur.
- `claim_id` değerleri bir yanıt içinde tekildir. `used_sources` yalnızca `sources` içindeki kimlikleri taşır
  (modelin uydurduğu kimlikler backend'de atılır).
- `published_date` `YYYY-MM-DD` ya da `null`dur (sahte veriyle test edilir; `lite` arayıcının gerçek değerleri canlı
  denetimde biçim açısından gevşek denetlenir).
- Bilinen eksik (testte `xfail` olarak işaretli, Mert / madde 12): açıklamadaki `[source_N]` atfı `sources` içinde
  olmayan bir kimliği gösterebilir; arayüz bunu "Kaynak eşleşmesi bulunamadı" olarak gösterir.

### İddia durumu (backend_v2)

| `status` | `verdict` | `error_code` | Arayüzde |
|---|---|---|---|
| `ok` | hüküm (doğrulanabilir iddiada) ya da `null` (`is_verifiable: false`) | yok | Normal iddia |
| `timeout` | `null` | `CLAIM_TIMEOUT` (iddia süresi) ya da `DEADLINE_EXCEEDED` (toplam süre) | "İncelenemeyen iddialar" |
| `error` | `null` | `RETRIEVAL_FAILED`, `VERDICT_FAILED` ya da `INTERNAL_ERROR` | "İncelenemeyen iddialar" |
| `skipped` | `null` | yok (8'den fazla doğrulanabilir iddia) | "İncelenemeyen iddialar" |

`ok` dışındaki iddia hiçbir zaman hüküm taşımaz; arayüz de onu hüküm sayılarında göstermez (`e2e/` bunu denetler).
Güven puanı yoktur; arayüz uydurmaz. `title` yoksa backend "Kaynak" yazar; arayüz bu yedek etiketi ad olarak göstermez.
Başlık alan adıyla aynıysa da gösterilmez (alan adı zaten ayrı satırdadır). `retrieval_score` ve `used_sources` okunmaz.

Adapter ayrıca iki eski biçimi de kabul eder (mock bunları kullanır): `{ "claims": [ … ] }` ve tek iddialı
`{ "claim", "verdict", "explanation", "confidence", "evidence": [ … ] }`.

| Alan | Zorunlu | Arayüzün davranışı |
|---|---|---|
| `claim` ya da `text` | evet | İddia metni. Yoksa cevap geçersiz sayılır |
| `verdict` | evet (`is_verifiable: false` değilse) | `SUPPORTED`, `REFUTED`, `CONFLICTING` (ya da `CONFLICTING_EVIDENCE`), `NOT ENOUGH EVIDENCE` (ya da `NOT_ENOUGH_EVIDENCE`). Tanınmayan ya da eksik değerde yalnızca o iddia "Sonucu gösterilemeyen iddialar" bölümüne düşer, diğer iddialar gösterilir (kısmi sonuç). Okunabilen hiçbir iddia kalmazsa cevap geçersiz sayılır |
| `is_verifiable` | hayır | `false` ise iddia "İncelenmeyen ifadeler" bölümünde gösterilir |
| `explanation` | hayır | Köşeli parantezli atıflar (`[source_1]`) kaynak listesindeki `id` ile eşleşirse numaralı bağlantıya çevrilir. Kimlik biçiminde olup (harf + alt çizgi, ör. `source_9`, `kaynak_1`) listede bulunmayan atıf "Kaynak eşleşmesi bulunamadı" olarak gösterilir. Atıf olmayan köşeli parantezli metin (`[2023]`, `[...]`, `[1]`) olduğu gibi kalır |
| `sources` ya da `evidence` | hayır | Kaynak listesi. Boşsa "Kaynak bulunamadı" gösterilir |
| `sources[].url` | evet | Yoksa o kaynak atılır. `http`/`https` dışındaki adresler tıklanabilir yapılmaz |
| `sources[].title` (ya da `source` / `name`) | hayır | Kaynak adı olarak sayfa başlığı; yoksa alan adı gösterilir |
| `sources[].text` | hayır | Kısa alıntı (360 karakterden uzunsa kesilir) |
| `sources[].published_date` (ya da `published_at`) | hayır | Biçimi koddan belli değil; tarih olarak okunamıyorsa gösterilmez; yoksa tarih gösterilmez. Kaynak adı da yoksa satır tek sütun olur |
| `confidence` | hayır | 0 ile 1 arası sayı. "Modelin güven puanı: %91" diye, doğruluk olasılığı olmadığı notuyla gösterilir. Yoksa ya da 0-1 dışındaysa hiçbir şey gösterilmez |
| `used_sources` | hayır | **Şu an okunmuyor** (aşağıdaki soru 3) |
| `sources[].score` | hayır | Gösterilmez |

Açıklamada hiç atıf yoksa arayüz kaynaklara "dayandığımız kanıtlar" demez; "Bulunan kaynaklar" başlığıyla listeler.

## Hata cevabı (HTTP 4xx / 5xx)

Backend (koddan okundu): `{ "status": "error", "error": "<KOD>", "message": "<Türkçe metin>" }`

| HTTP | `error` | Arayüzde |
|---|---|---|
| 422 | `VALIDATION_ERROR` | `INVALID_INPUT` (boş, eksik ya da 10 000 karakterden uzun; backend bunları ayırmaz) |
| 400 | `EMPTY_TEXT` | `INVALID_INPUT` |
| 500 | `VERIFY_FAILED` | `INTERNAL_ERROR` |
| 502 | `EXTRACTION_FAILED` (backend_v2) | `SERVICE_UNAVAILABLE` |
| 503 | `CONFIG_ERROR` (backend_v2; anahtar eksik) | `SERVICE_UNAVAILABLE` |
| 504 | `EXTRACTION_TIMEOUT` (backend_v2) | `TIMEOUT` |

backend_v2 hata gövdesine isteğe bağlı `detail` ("Tür: mesaj") ekleyebilir (`EXPOSE_ERROR_DETAIL=1` iken). Arayüz bunu
göstermez. 17 Ekim 2026'dan beri varsayılan `EXPOSE_ERROR_DETAIL=0`'dır; bu ayar `CONFIG_ERROR` ve `/health` içindeki
`init_error` için de geçerlidir (eski Fatih / madde 3 kapandı).

Backend henüz göndermeyen ama `docs/BACKEND_TODO.md`'de önerilen kodlar da şimdiden tanınır:
`TEXT_TOO_LONG` → `INPUT_TOO_LONG`, `RATE_LIMITED` → `RATE_LIMITED`, `BUSY` → `SERVER_BUSY`,
`DAILY_QUOTA_EXCEEDED` → `QUOTA_EXCEEDED`, `UPSTREAM_UNAVAILABLE` → `SERVICE_UNAVAILABLE`.
Gövdede kod yoksa durum koduna bakılır: `429` → `RATE_LIMITED`, `502`/`503` → `SERVICE_UNAVAILABLE`.

Tanınmayan gövde için eski şekil (`{ "error": { "code" } }`) ve HTTP durum kodunun standart anlamı yedek olarak kalır
(`413` → `INPUT_TOO_LONG`, `408`/`504` → `TIMEOUT`, diğerleri → `INTERNAL_ERROR`).
Her kod için kullanıcıya "ne oldu / ne yapabilirsiniz" metni gösterilir (`lib/format.ts`). Sunucunun `message` metni gösterilmez.
İstek hiç ulaşmazsa (ağ, CORS) `NETWORK` gösterilir; tarayıcı bu ikisini ayırt etmeye izin vermez.
Tarayıcı çevrimdışı olduğunu bildiriyorsa `OFFLINE` gösterilir. `OFFLINE`, `URL_UNSUPPORTED` ve `SERVER_BUSY` arayüzün kendi kodlarıdır.

**Önemli (yalnızca canlıdaki 1.0.0):** backend tek iddia bile hata verirse (arama ya da model) bütün isteği
`500 VERIFY_FAILED` ile bitirir; kısmi sonuç döndürmez. İddialar sırayla işlenir, süre iddia sayısıyla artar.
backend_v2'de bu yoktur: hata veren iddia yalnızca kendisi `status: "error"` olur, iddialar eşzamanlı işlenir
(`CLAIM_CONCURRENCY`, varsayılan 4) ve yanıt her durumda `TOTAL_TIMEOUT` (varsayılan 45 sn) içinde gelir.

## CORS (koddan okundu)

İzinli kökenler: `https://verify-test-swart.vercel.app`, `http://localhost:3000`, `http://localhost:5173`, ayrıca
`FRONTEND_ORIGIN` ortam değişkeni (tek değer). Resmî site `https://verifia-pi.vercel.app`'tir ve `FRONTEND_ORIGIN` bununla
eşleşmelidir; eski `verify-test-*` adresleri frontend'de bu adrese yönlendirilir. Alınacak alan adı için de
`FRONTEND_ORIGIN` ayarlanmalıdır; yoksa tarayıcı isteği engeller ve arayüz "Sunucuya ulaşılamadı" gösterir.
İzinsiz kökene `Access-Control-Allow-Origin` dönmediği `e2e/` testinde denetlenir.

backend_v2 `Access-Control-Expose-Headers: X-Request-ID` gönderir (16 Ekim): tarayıcıdaki kod bu başlığı okuyabilir,
örneğin bir hata mesajının yanında "hata kimliği" olarak gösterebilir. `backend_v2/tests/test_observability.py` ve
`e2e/` (gerçek tarayıcıda `fetch`) bunu denetler.

## İzlenebilirlik: `X-Request-ID` (backend_v2)

Her yanıt (hata ve CORS ön denetimi dahil) bir `X-Request-ID` başlığı taşır. İstekle gelen kimlik 8-64 karakter ve
`[A-Za-z0-9._-]` ise aynen kullanılır, değilse yenisi üretilir. Backend'in her log satırında `rid=<kimlik>` vardır.
Kullanıcı metni ve iddia metni log satırlarına yazılmaz; yalnızca bir dış servis hata verdiğinde o servisin kendi hata
mesajı kayda geçer. Bir hata bildirildiğinde bu kimlikle sunucu kaydı bulunur.

## Akış: `POST /verify/stream` (backend_v2, arayüz henüz kullanmıyor)

İstek `/verify` ile aynıdır (`{ "text" }`). Yanıt `text/event-stream`; her olay `event: <tür>` ve `data: <JSON>` satırıdır,
`data.type` olay adına eşittir. Sıra (testle sabit, `backend_v2/tests/test_stream.py`):

```
started  {"type":"started","request_id":"…"}
stage    {"type":"stage","stage":"extract","status":"started"}
stage    {"type":"stage","stage":"extract","status":"finished","ms":812}
claims   {"type":"claims","claims":[{claim_id, claim, is_verifiable}],"extract_ms":812}
stage    {"type":"stage","stage":"verify","status":"started","total":3}
result   {"type":"result","result":{…/verify'daki tek iddia…}}      × total (hazır oldukça, sırası değişebilir)
stage    {"type":"stage","stage":"verify","status":"finished","ms":2310}
done     {"type":"done","partial":false,"timings":{…},"request_id":"…"}
```

- İstek bütünüyle başarısız olursa (ör. iddia ayrıştırma) `done` yerine tek bir `error` olayı gelir:
  `{"type":"error","error":"EXTRACTION_FAILED","message":"…","request_id":"…"}`.
- Boş metin akış açılmadan `400 EMPTY_TEXT` JSON, geçersiz gövde `422 VALIDATION_ERROR` JSON döner.
- 15 saniye olay yoksa `: keep-alive` yorum satırı gelir. Tanınmayan olaylar yok sayılmalıdır.
- İstemci bağlantıyı kapatırsa backend işi hemen iptal eder (kota harcamaya devam etmez).
- `EventSource` POST gönderemez; arayüz `fetch` + akış okuyucu kullanmalıdır.
- Önerilen eşleme: `extract` → `extracting_claims`, `verify` → `retrieving_evidence`/`verifying` (backend arama ve
  değerlendirmeyi iddia başına birlikte yapar; ayrı aşama olayı yoktur).

## Süre ve aşamalar

- Aşama bilgisi (`extracting_claims`, `retrieving_evidence`, `verifying`) `/verify`'da **yoktur**. backend_v2'nin
  `/verify/stream` olayları gerçek aşamaları verir (yukarıda); arayüz hazır, yalnızca `lib/api/http.ts` değişir.
  Akış kullanılmadıkça sahte ilerleme gösterilmez.
- Eşzamanlılık (backend_v2, 16 Ekim): bir istekteki iddialar `CLAIM_CONCURRENCY` (4) ile, tüm isteklerdeki arama ve
  değerlendirme çağrıları birlikte `MAX_UPSTREAM_CONCURRENCY` (8) ile sınırlıdır; aynı anda incelenen aynı iddia tek
  kez aranır. Yoğunlukta istekler sırada bekler; bekleme süre sınırına dahildir, aşılırsa iddia `timeout` döner
  (kısmi sonuç). Arayüzün 90 sn'lik `REQUEST_TIMEOUT_MS` sınırı backend'in 45 sn'lik toplam sınırından uzundur.
- Ölçüm (16 Ekim, sahte arama 0,3 sn/iddia, tek süreç, varsayılan sınır 8): 20 eşzamanlı istekte p95 yaklaşık 1,5 sn,
  30 eşzamanlıda yaklaşık 4,2 sn, hata yok, sunucu belleği yaklaşık 53 MB; ayrıntı `backend_v2/README.md`,
  "Load, memory and performance". Gerçek Groq/Tavily süreleri buna dahil değildir.

## Teyit edilmemiş varsayımlar

| Varsayım | Kodda | Yanlışsa ne olur |
|---|---|---|
| İstek en fazla 90 saniye sürer (backend süre sınırı koymuyor; iddialar sırayla işleniyor) | `lib/config.ts` → `REQUEST_TIMEOUT_MS` | Daha uzun süren incelemeler "zaman aşımı" olarak görünür |
| Atıflar `[source_1]` biçiminde (kodda istem `[kaynak_id]` der, kimlikler `source_N`) | `lib/citations.ts` | Model başka biçim yazarsa atıf bağlantıya çevrilmez; kaynaklar "Bulunan kaynaklar" olarak listelenir |
| `published_date` biçimi | `lib/format.ts` | Okunamayan tarih gösterilmez |
| Backend'in yayınlandığı adres | `NEXT_PUBLIC_API_BASE_URL` | Ayarlanmazsa yayında "servis bağlı değil" gösterilir |

Teyit edilenler (koddan): `POST /verify`, `{text}`, 10 000 karakter, URL desteği yok, `results` şekli, hata gövdesi, CORS listesi.

## Backend sahibine sorular

1. Bağlantı (URL) ile inceleme gelecek mi? Gelecekse istek şekli ne olacak?
2. En uzun yanıt süresi nedir? İddialar paralel işlenecek mi? **backend_v2'de yanıtlandı:** eşzamanlı, en fazla
   `TOTAL_TIMEOUT` (45 sn).
3. Tek iddia başarısız olursa bütün istek yerine yalnızca o iddia hata olarak dönebilir mi? **backend_v2'de
   yanıtlandı:** evet, `status: "error"` ve `partial: true`.
4. `422 VALIDATION_ERROR` boş/eksik ve aşırı uzun metni ayırt etmiyor; ayrı kodlar eklenebilir mi (`TEXT_TOO_LONG`)?
5. `published_date` hangi biçimde (ISO 8601 mi)?
6. Alan adı ve `FRONTEND_ORIGIN`: yayın adresi netleşince CORS'a eklenecek mi?
7. İstek sınırı (rate limit) olacak mı? Olacaksa `429` ile mi bildirilecek? Arayüz `429` için ayrı bir kullanım sınırı mesajı gösterir; bekleme süresi kesinleşmediği için geri sayım gösterilmez.
8. Backend'in yayın adresi nedir ve `/health` herkese açık mı?
9. `used_sources` tam olarak neyi gösterir ve değerleri `sources[].id` ile aynı mı? Anlam kesinleşmeden kaynak ilişkileri bundan tahmin edilmez.
10. Kaynak rolü (`relation`), kaynak türü ve rapor alanları (`report`) eklenecek mi? (Aşağıdaki bölüm.)

## UI/UX iyileştirmesi — 8 Ekim 2026

- `report` yanıt alanı isteğe bağlı olarak `title`, `summary`, `input`, `prepared_at`, `scope` taşıyabilir. Eksik alanlar üretilmez; geçersiz tarih gösterilmez. Otomatik servis raporu editörün hazırladığı örnek gibi etiketlenmez.
- Kaynaklarda isteğe bağlı `relation` (`supports`, `contradicts`, `context`), `excerpt_kind: "summary"` ve `kind` desteklenir. Bu alanlar mevcut backend tarafından sağlanmış kabul edilmez; backend ekibinin sözleşmeyi doğrulaması gerekir.
- Servis yokken metin alanı yazılabilir; gönderim eylemi sunulmaz ve gönderim işleyicisi istek başlatmaz. Hazır örnek yazılan metni kullanmaz.
- Gerçek gönderim açılmadan önce veri saklama, hizmet sağlayıcıları, silme ve sorumlu/iletişim bilgileri kesinleştirilmelidir.
