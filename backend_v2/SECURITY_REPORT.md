# API g?venli?i entegrasyon raporu

Tarih: 2026-10-17. ?al??ma branch'i: `fatih/verifia-api-security`.
Kaynak: `f4f863aa108e49d4cd824566c9ffd80964a49548`.
`git fetch verifia main` sonras?nda HEAD ve `verifia/main` ayn?:
`2f568005d577abb3294a85fc007ac2717e0872c8`.
Ba?lang??ta yaln?z izlenmeyen `.idea/` vard?; de?i?tirilmedi.

## Zaten bulunan ve korunan davran??lar

- `limits.py`: t?m istekler aras?nda upstream concurrency s?n?r?, ayn? anda gelen
  ayn? iddialar i?in ortak ?a?r? ve son bekleyici ayr?ld???nda iptal.
- `observability.py`: do?rulanan gelen request ID, her HTTP yan?tta ID,
  request context ve metinsiz a?ama/s?re loglar?.
- `streaming.py`: SSE olay s?ras?, keepalive, ba?lant? kopmas?n? izleme ve pipeline iptali.
- Pipeline zaman a??m?, k?smi sonu?lar, s?n?rl? TTL cache, bo? metin ve validation yan?tlar?.
- Hata ayr?nt?lar? varsay?lan olarak kapal?; deep health yaln?z debug modunda a??k.
- Belirli origin listesi, credentials kapal? CORS ve taray?c?ya a??k request ID.
- Hafif Docker image ve repo i?indeki mevcut engine/retrieval dosyalar?n?n kullan?lmas?.

## Eklenenler

- Her iki verification endpoint'ine ortak, IP ba??na dakika/saat/g?n ve global g?n
  kotas?; dolan kotada JSON `RATE_LIMITED` ve `Retry-After`.
- IP tablosu i?in s?n?rl? boyut ve 24 saat kullan?lmayan kay?tlar? temizleme;
  tablo dolunca mevcut kullan?c?lar?n kotas?n? silmek yerine yeni kullan?c?y? reddetme.
- 65.536 byte g?vde s?n?r?: hem Content-Length hem ger?ekten okunan chunk'lar
  kontrol edilir; ge?ersiz uzunluk 400, a??r? g?vde 413 d?ner.
- ?stek kabul s?n?r?: varsay?lan iki aktif verification; doluyken 429 `BUSY`.
  Bu, mevcut upstream gate'in ?zerinde ayr? bir istek kabul kontrol?d?r.
- RSS varsay?lan 384 MiB; s?n?rda veya ?l??m ba?ar?s?zken 503 `LOW_MEMORY`.
- `asyncio.to_thread` ?a?r?lar? i?in takip edilen executor: istek iptal edilse de
  ?al??an senkron sa?lay?c? i?i bitmeden kabul slotu serbest b?rak?lmaz.
- Proxy adresi yaln?z a??k?a g?venilen CIDR i?indeyse X-Forwarded-For sa?dan sola
  incelenir; g?venilmeyen do?rudan istemcinin ba?l??? dikkate al?nmaz.
- Yan?t ba?lamadan yakalanan beklenmeyen hata i?in ayr?nt?s?z JSON 500;
  ba?lam?? SSE yan?t?na ikinci HTTP yan?t? yaz?lmaz.
- Provider exception/traceback redaksiyonu, SDK ??kt? filtreleri ve bilinmeyen
  URL yollar?n?n request loglar?nda sabit bir de?erle g?sterilmesi. Mevcut
  request ID ve performans loglar? korunur.
- CORS listesine `*` eklenmesi engellendi; mevcut request ID ba?l??? preflight'ta kabul edilir.
- Docker: root olmayan kullan?c?, tek worker, proxy ba?l?klar?n?n Uvicorn taraf?ndan
  d?n??t?r?lmesinin kapat?lmas?, access log kapatma, ba?lant? concurrency s?n?r?,
  keepalive ayar? ve Dockerfile'a ?zel secret/build-context ignore dosyas?.

## De?i?en ve eklenen dosyalar

De?i?enler: `.env.example`, `Dockerfile`, `app/main.py`.
Eklenenler: `Dockerfile.dockerignore`, `app/security.py`, `app/resources.py`,
`app/safe_logging.py`, `tests/test_security_integration.py`,
`tools/run_offline_tests.py`, `tools/offline_guard.py`, bu rapor.
B?t?n yollar `backend_v2/` alt?ndad?r.

`limits.py`, `observability.py`, `streaming.py`, `llm.py`, `pipeline.py`,
`retrieval.py`, b?t?n ?nceden mevcut testler, `ai-engine/`,
`retrieval_demo_lite/` ve frontend dosyalar? de?i?tirilmedi.
Eski branch topluca kopyalanmad?. Eski RequestIDMiddleware eklenmedi;
ortak reponun request ID altyap?s? kullan?ld?. Eski Render blueprint'i yanl??
repo/branch ve ayr? CORS ayar? i?erdi?inden ta??nmad?. Dependency de?i?ikli?i gerekmedi.

## Do?rulama

Repo k?k?nden:

```powershell
python backend_v2/tools/run_offline_tests.py -q
```

Sonu?: **122 passed, 0 failed, 1 xfailed**, yakla??k 20 saniye.
Mevcut contract, load, pipeline, observability, streaming ve lite adapter testleri dahildir.
Runner test s?reci i?in admission/kota/RAM s?n?rlar?n? y?kseltir: eski y?k testleri
25?30 iste?in beraber kabul edilmesini ve y?zlerce iste?in kota dolmadan ?al??mas?n?
bekler. G?venlik testleri her senaryoda ilgili k???k s?n?r? ayr?ca ayarlar.
Bu profil ?retim varsay?lanlar?n? de?i?tirmez. ??plak tam `pytest` ko?usu, ?retim
kotalar?yla eski y?k testlerinin ba?ar? beklentilerine uygun de?ildir.
?lk bu ?ekilde ba?lat?lan ko?u ba?ar?s?zl?klar g?r?l?nce durduruldu; tam sonu? say?lmad?.

Varsay?lan ortam ile ayr?ca, `backend_v2/` i?inden:

```powershell
python -m pytest -p tools.offline_guard tests/test_security_integration.py -q
```

Sonu?: **18 passed, 0 failed**. Ger?ek Windows RSS ?l??m? de test edildi.
Kapsam: header/chunk g?vde limiti, iki endpoint aras?nda kota, BUSY, RSS retleri,
proxy spoofing, kota tablosu ve d?nem yenileme, hata/log redaksiyonu, request ID/CORS,
SSE disconnect sonras? slot b?rak?lmas?, iptal edilen thread bitene kadar slotun tutulmas?.
Test plugin'i d?? host DNS ve socket ba?lant?lar?n? engeller; localhost test altyap?s?na
izin verir. Groq/Tavily ve web retrieval mock kullan?r. Ger?ek ?cretli servis ?a?r?s? yap?lmad?.

Mevcut xfail: explanation i?inde olmayan `[source_N]` at?flar?n?n temizlenmemesi
(`test_explanation_cites_only_existing_sources`); ekip ?yesinin mevcut kapsam? korundu.
Bir mevcut Starlette/httpx deprecation uyar?s? var; ba??ml?l?klar de?i?tirilmedi.
`git diff --check` temiz. Korunan dosyalara y?nelik diff bo?.

## S?n?rlar ve kalan do?rulamalar

- Docker CLI bulunmad??? i?in image build, Linux RSS ve container smoke testi yap?lmad?.
- Ger?ek sa?lay?c?lar ile canl? test ve ger?ek kapasite/RAM kalibrasyonu yap?lmad?.
- Kotalar, upstream gate, cache ve admission s?re? i?idir; yeniden ba?latmada s?f?rlan?r.
  Tek worker/tek instance i?indir. Birden fazla instance i?in ortak kota deposu gerekir.
- Fixed-window kota pencere s?n?r?nda iki pencerenin b?t?esinin k?sa aral?kta
  t?ketilmesine izin verir; rolling-window garantisi yoktur.
- RSS kontrol? yeni i?i reddeder; i?letim sistemi RAM hard limit'i de?ildir.
- Body kabul?nde production reverse proxy body/read timeout ve ba?lant? limitleri
  ayr?ca ayarlanmal?d?r; uygulama toplam body okuma timeout'u eklemez.
- Docker d??? ba?latmada da Uvicorn `--workers 1 --no-proxy-headers` kullan?n.
  `TRUSTED_PROXY_CIDRS` yaln?z ger?ek proxy a??n? i?ermelidir. Proxy bilinmiyorsa bo? b?rak?n;
  bu durumda payla??lan proxy IP'sinin kotas? ortak olur.
- `EXPOSE_ERROR_DETAIL=0` ?retimde korunmal?; debug modu mevcut ayr?nt? ve ?cretli
  `/health/deep` davran???n? bilin?li olarak a?ar. Bu endpoint testlerde ?a?r?lmad?.
- `render.yaml`, deployment ve canl? platform ayarlar? olu?turulmad?/uygulanmad?.

Commit, push, PR, merge, cherry-pick, reset veya deployment yap?lmad?.
