# API sözleşmesi (frontend'in anladığı hâli)

> **Durum: kısmen teyitli.** Yol ve cevabın genel şekli backend'den (`backend/main.py`, 2 Ekim) alındı.
> Aşağıda "teyit edilmemiş" diye işaretlenen her şey frontend'in varsayımıdır; backend sahibi doğrulayana kadar öyle kalır.
> Kodda karşılığı: `lib/api/contract.ts` (şekiller), `lib/api/adapter.ts` (çeviri), `lib/api/http.ts` (istek).

## İstek

`POST {NEXT_PUBLIC_API_BASE_URL}/verify` — `Content-Type: application/json`

```json
{ "text": "İncelenecek metin" }
```

- Frontend yalnızca `text` gönderir. Adresin sonundaki `/` atılır.
- **Bağlantı (URL) ile inceleme backend'de yok.** Arayüzdeki "Bağlantı" sekmesi gerçek servise istek göndermez;
  kullanıcıya "bağlantıyla inceleme henüz desteklenmiyor" hatası (`URL_UNSUPPORTED`, arayüzün kendi kodu) gösterilir.
  Eski öneri `input_type: "text" | "url"` alanıydı; backend bunu kabul edene kadar gönderilmez.

## Başarılı cevap (HTTP 200)

Backend'in bildirdiği şekil:

```json
{ "results": [ {
    "claim_id": "…", "claim": "…", "is_verifiable": true, "verdict": "SUPPORTED",
    "explanation": "…", "used_sources": [ … ],
    "sources": [ { "id": "source_1", "url": "https://…", "text": "…" } ]
} ] }
```

Güven puanı, kaynak adı ve yayın tarihi bu cevapta yoktur; arayüz bunları göstermez ve uydurmaz.

Adapter ayrıca iki eski biçimi de kabul eder (mock bunları kullanır): `{ "claims": [ … ] }` ve tek iddialı
`{ "claim", "verdict", "explanation", "confidence", "evidence": [ … ] }`.

| Alan | Zorunlu | Arayüzün davranışı |
|---|---|---|
| `claim` ya da `text` | evet | İddia metni. Yoksa cevap geçersiz sayılır |
| `verdict` | evet (`is_verifiable: false` değilse) | `SUPPORTED`, `REFUTED`, `CONFLICTING` (ya da `CONFLICTING_EVIDENCE`), `NOT ENOUGH EVIDENCE` (ya da `NOT_ENOUGH_EVIDENCE`). Tanınmayan ya da eksik değerde yalnızca o iddia "Sonucu gösterilemeyen iddialar" bölümüne düşer, diğer iddialar gösterilir (kısmi sonuç). Okunabilen hiçbir iddia kalmazsa cevap geçersiz sayılır |
| `is_verifiable` | hayır | `false` ise iddia "İncelenmeyen ifadeler" bölümünde gösterilir |
| `explanation` | hayır | Köşeli parantezli atıflar (`[source_1]`) kaynak listesindeki `id` ile eşleşirse numaralı bağlantıya çevrilir. Eşleşmeyen atıf düz metin kalır |
| `sources` ya da `evidence` | hayır | Kaynak listesi. Boşsa "Kaynak bulunamadı" gösterilir |
| `sources[].url` | evet | Yoksa o kaynak atılır. `http`/`https` dışındaki adresler tıklanabilir yapılmaz |
| `sources[].source` / `title` / `name` | hayır | Kaynak adı; yoksa alan adı gösterilir |
| `sources[].text` | hayır | Kısa alıntı (360 karakterden uzunsa kesilir) |
| `sources[].published_at` | hayır | ISO tarih; yoksa tarih gösterilmez. Kaynak adı da yoksa satır tek sütun olur |
| `confidence` | hayır | 0 ile 1 arası sayı. "Modelin güven puanı: %91" diye, doğruluk olasılığı olmadığı notuyla gösterilir. Yoksa ya da 0-1 dışındaysa hiçbir şey gösterilmez |
| `used_sources` | hayır | **Şu an okunmuyor** (aşağıdaki soru 3) |
| `sources[].score` | hayır | Gösterilmez |

Açıklamada hiç atıf yoksa arayüz kaynaklara "dayandığımız kanıtlar" demez; "Bulunan kaynaklar" başlığıyla listeler.

## Hata cevabı (HTTP 4xx / 5xx)

Backend şu an bir hata gövdesi tanımlamıyor. Arayüz iki adımda karar verir:

1. Gövde `{ "error": { "code": "…" } }` ise ve kod tanınıyorsa o kullanılır:
   `INVALID_INPUT`, `INPUT_TOO_LONG`, `URL_UNREADABLE`, `IMAGE_UNREADABLE`, `TIMEOUT`, `NETWORK`, `INTERNAL_ERROR`.
2. Değilse HTTP durum kodunun standart anlamına bakılır:
   `400`/`422` → `INVALID_INPUT`, `413` → `INPUT_TOO_LONG`, `408`/`504` → `TIMEOUT`, diğerleri → `INTERNAL_ERROR`.

Her kod için kullanıcıya "ne oldu / ne yapabilirsiniz" metni gösterilir (`lib/format.ts`). Sunucunun `message` metni gösterilmez.
İstek hiç ulaşmazsa (ağ, CORS) `NETWORK` gösterilir; tarayıcı bu ikisini ayırt etmeye izin vermez.
Tarayıcı çevrimdışı olduğunu bildiriyorsa aynı durum `OFFLINE` ("internet bağlantısı yok") olarak gösterilir. `OFFLINE` ve `URL_UNSUPPORTED` arayüzün kendi kodlarıdır; backend bunları göndermez.

## Süre ve aşamalar

- Aşama bilgisi (`extracting_claims`, `retrieving_evidence`, `verifying`) **beklenmiyor**. Backend gerçek aşama
  bilgisi verirse arayüz hazır (yalnızca `lib/api/http.ts` değişir); vermezse sahte ilerleme gösterilmez.

## Teyit edilmemiş varsayımlar

| Varsayım | Kodda | Yanlışsa ne olur |
|---|---|---|
| Metin sınırı 5.000 karakter | `lib/config.ts` → `MAX_INPUT_LENGTH` | Sınır daha yüksekse kullanıcı gereksiz engellenir; daha düşükse backend hatası gösterilir |
| İstek en fazla 90 saniye sürer | `lib/config.ts` → `REQUEST_TIMEOUT_MS` | Daha uzun süren incelemeler "zaman aşımı" olarak görünür |
| Atıflar `[source_1]` biçiminde ve `sources[].id` ile aynı | `lib/citations.ts` | Atıflar bağlantıya çevrilmez; kaynaklar "Bulunan kaynaklar" olarak listelenir |
| Doğrulama hatası `400`/`422`, aşırı uzun girdi `413` döner | `lib/api/http.ts` | Yanlış hata metni gösterilir |
| Backend, sitenin adresine CORS izni verir (`POST`, `Content-Type`) | — | Her istek "Sunucuya ulaşılamadı" olarak görünür |

## Backend sahibine sorular

1. Bağlantı (URL) ile inceleme gelecek mi? Gelecekse istek şekli ne olacak (`input_type` mı, ayrı yol mu)?
2. Metin sınırı ve en uzun yanıt süresi nedir?
3. `used_sources` tam olarak neyi gösterir (açıklamada kullanılan kaynak kimlikleri mi) ve değerleri `sources[].id` ile aynı mı?
4. Açıklamadaki atıfların biçimi nedir?
5. Hata durumunda hangi durum kodları ve gövde döner? Yukarıdaki `{ "error": { "code" } }` şekli uygun mu?
6. Kaynak adı, yayın tarihi ve güven puanı eklenecek mi?
7. Hangi adreslere CORS izni verilecek?
8. Bir iddianın incelemesi başarısız olursa backend ne döner (iddia listeden çıkar mı, ayrı bir alanla mı bildirilir)? Arayüz şu an yalnızca tanımadığı `verdict` değerini "sonucu gösterilemeyen iddia" olarak ayırır.
9. İstek sınırı (rate limit) olacak mı? Olacaksa `429` ile mi bildirilecek? Arayüz şu an `429`'u genel sunucu hatası olarak gösterir.
