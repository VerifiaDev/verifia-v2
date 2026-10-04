# API sözleşmesi (frontend'in anladığı hâli)

> **GÜNCEL DURUM (2 Ekim):** Backend `backend/main.py` ile geldi. Gerçek sözleşme: `POST /verify`, gövde yalnızca `{ "text": "..." }`, cevap `{ "results": [ { claim_id, claim, is_verifiable, verdict, explanation, used_sources, sources: [ {id: "source_1", url, text} ] } ] }`. Güven puanı, kaynak adı, tarih, hata gövdesi, CORS ve bağlantı (URL) desteği henüz yok. Aşağıdaki "/check" ve `input_type` anlatımı eski öneridir; arayüz artık `/verify` kullanır.


> **Durum: geçici öneri.** Backend sahibi (Kişi 3) ile teyit edilene kadar geçerlidir.
> Kodda karşılığı: `lib/api/contract.ts` (şekiller), `lib/api/adapter.ts` (çeviri), `lib/api/http.ts` (istek).

## İstek

`POST {NEXT_PUBLIC_API_BASE_URL}/check` — `Content-Type: application/json`

```json
{ "text": "İncelenecek metin ya da bağlantı", "input_type": "text" }
```

- `input_type`: `"text"` ya da `"url"`. `"url"` ise `text` alanında bağlantı gelir.
- Backend şu an yalnızca `{ "text": ... }` tanımlıyor; **`input_type` bizim önerimiz**.
- Frontend metin sınırı: 5000 karakter (backend farklı bir sınır söylerse `lib/config.ts` değişir).

## Başarılı cevap (HTTP 200)

İki biçim de kabul edilir.

**Tek iddia** (proje dokümanındaki örnek):

```json
{
  "claim": "Örnek iddia",
  "verdict": "REFUTED",
  "explanation": "Kaynaklar bu iddia ile çelişiyor [kaynak_1].",
  "confidence": 0.91,
  "evidence": [
    { "id": "kaynak_1", "text": "Kısa kanıt pasajı", "source": "Reuters",
      "url": "https://example.com", "score": 0.87, "published_at": "2026-05-12" }
  ]
}
```

**Birden çok iddia** (önerilen; bir metinde birden çok iddia olabilir):

```json
{ "claims": [ { "id": "claim_1", "text": "...", "verdict": "SUPPORTED", "explanation": "...", "sources": [ ... ] } ] }
```

Alanlar:

| Alan | Zorunlu | Not |
|---|---|---|
| `claim` ya da `text` | evet | İddia metni |
| `verdict` | evet | `SUPPORTED`, `REFUTED`, `CONFLICTING` (ya da `CONFLICTING_EVIDENCE`), `NOT ENOUGH EVIDENCE` (ya da `NOT_ENOUGH_EVIDENCE`). Tanınmayan değer hata sayılır |
| `explanation` | hayır | Atıflar `[kaynak_1]` biçiminde; `id`'si kaynak listesindekiyle eşleşmeli. Listede olmayan atıf bağlantıya çevrilmez |
| `evidence` ya da `sources` | hayır | Kaynak listesi. Kaynağı olmayan iddia "kaynak bulunamadı" gösterilir |
| `evidence[].url` | evet | Yoksa o kaynak atılır |
| `evidence[].source` (ya da `title`) | hayır | Kaynak adı; yoksa alan adı gösterilir |
| `evidence[].text` | hayır | Kısa alıntı |
| `evidence[].published_at` | hayır | ISO tarih; yoksa "Yayın tarihi belirtilmemiş" |
| `is_verifiable` | hayır | `false` ise iddia ayrı bir "incelenmeyen ifadeler" bölümünde gösterilir |
| `confidence` | hayır | 0 ile 1 arası sayı (örn. `0.91`). Arayüz **"Modelin güven puanı: %91"** diye gösterir ve bunun doğruluk olasılığı olmadığını belirtir. Yoksa ya da 0-1 dışındaysa (örn. `91`) hiçbir şey gösterilmez, tahmin edilmez |
| `evidence[].score` | hayır | Arayüz göstermez |

## Hata cevabı (HTTP 4xx / 5xx)

```json
{ "error": { "code": "URL_UNREADABLE", "message": "..." } }
```

`code`: `INVALID_INPUT`, `INPUT_TOO_LONG`, `URL_UNREADABLE`, `IMAGE_UNREADABLE`, `INTERNAL_ERROR`.
Tanınmayan kod ya da JSON olmayan gövde `INTERNAL_ERROR` sayılır. Kullanıcıya her kod için
"ne oldu / ne yapabilirsiniz" metni gösterilir (`lib/format.ts`). `message` kullanıcıya gösterilmez.

## Süre ve aşamalar

- İstek **90 saniyeden** uzun sürerse arayüz vazgeçer ve "zaman aşımı" gösterir.
- Aşama bilgisi (`extracting_claims`, `retrieving_evidence`, `verifying`) şu an **beklenmiyor**.
  Backend gerçek aşama bilgisi verirse (durum sorgulama ya da akış) arayüz hazır; yalnızca `lib/api/http.ts` değişir.
  Aşama bilgisi yoksa arayüz sahte ilerleme **göstermez**.

## CORS

Site ile backend farklı adreslerde olacağı için backend, sitenin adresine `POST` ve `Content-Type` başlığı için izin vermelidir.

## Backend sahibine sorular

1. `POST /check` yolu ve `input_type` alanı uygun mu?
2. Cevap `claims[]` mı, tek iddia mı olacak?
3. Kaynaklar nesne olarak (`url`, `source`, `text`, `published_at`) mı dönecek?
4. Metin sınırı ve en uzun yanıt süresi nedir?
5. Hata kodları yukarıdaki listeyle uyumlu mu?
