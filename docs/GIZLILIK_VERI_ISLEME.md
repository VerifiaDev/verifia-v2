# Gizlilik sayfası için veri işleme araştırması: Render, Groq, Tavily

> **Tarih:** 16 Ekim 2026. Kaynaklar sağlayıcıların bu tarihte yayımlı belgeleridir (aşağıda bağlantılar).
> **Amaç:** `app/gizlilik/page.tsx`'teki her cümlenin sağlayıcı belgeleriyle ve backend_v2'nin gerçek davranışıyla
> uyumlu olup olmadığını denetlemek; eksikleri ve yapılması gerekenleri listelemek.
> **Hukuki görüş değildir.** KVKK yurt dışı aktarım bölümü bir hukukçuya doğrulatılmalıdır.

## Kısa sonuç

- Gizlilik sayfası bugünkü hâliyle sağlayıcı belgeleriyle **büyük ölçüde uyumlu**. Yanlış bir cümle bulunmadı.
- **Eksik 1 (backend_v2 yayına alınınca):** 6 saatlik bellek önbelleği sayfada yok (aşağıda B1).
- **Eksik 2 (hukuki):** yurt dışına aktarımın KVKK m.9'a göre hangi dayanakla yapıldığı yazmıyor (aşağıda K1).
- **Kolay kazanç:** Groq konsolunda "Zero Data Retention" açılırsa sayfa "Groq metni saklamaz" diyebilir (G2).
- **Dikkat:** Tavily sorguları hizmetini geliştirmek (ve model eğitimi) için kullanabileceğini yazıyor; ücretsiz/
  standart planda bunu kapatan bir ayar bulunmadı (T2).

## Verinin yolu (backend_v2, `RETRIEVER=lite`)

| Adım | Nereye gider | Ne gider | Kaynak (kod) |
|---|---|---|---|
| 1 | Vercel (site) | Sayfa istekleri, IP, tarayıcı bilgisi. Metin **gitmez** (tarayıcı doğrudan backend'e gönderir) | `lib/api/http.ts` |
| 2 | Render (backend) | Metnin tamamı, IP | `backend_v2/app/main.py` |
| 3 | Groq | Metnin tamamı (iddia ayırma), her iddia + bulunan kaynakların alıntıları (değerlendirme) | `ai-engine/ai_engine.py`, `backend_v2/app/llm.py` |
| 4 | Tavily | İddialardan üretilen arama sorguları (iddia başına 3 sorgu, `LITE_QUERY_COUNT`) | `retrieval_demo_lite/search_retrieval_lite.py` |
| 5 | Kaynak siteler | Render sunucusu sayfayı indirir; metin ve kullanıcının IP'si **gitmez** | aynı dosya |

backend_v2'nin logları (`backend_v2/app/observability.py`): her satırda istek kimliği (`rid=`), yol, durum kodu,
süreler. Kullanıcı metni ve iddia metni log satırına yazılmaz; `lite` arayıcı sorguları yalnızca `debug=True` iken
yazdırır, backend bunu `False` ile çağırır. İstisna: bir dış servis hata verirse, o servisin kendi hata mesajı
(`log.exception`) kayda geçer; mesajın içeriği servise bağlıdır. Canlıdaki 1.0.0 sürümü ise arama sorgularını
sunucu çıktısına yazıyor (gizlilik sayfası bunu zaten söylüyor).

## Render

| Konu | Belge ne diyor | Kaynak |
|---|---|---|
| Rol | Müşterinin son kullanıcı verisi için **işleyen** (processor); kendi hesap/fatura verisi için sorumlu (controller) | [Render Privacy Policy](https://render.com/privacy) (son değişiklik 10 Temmuz 2026) |
| Konum | Hizmet ABD'de barındırılır; servis bölgesi seçilebilir: Oregon, Ohio, Virginia (ABD), Frankfurt (Almanya), Singapur. Bölge sonradan **değiştirilemez**, yeni servis açmak gerekir | [Render Regions](https://render.com/docs/regions) |
| Log saklama | Hobby 7 gün, Pro 14 gün, Scale/Enterprise 30 gün; süre dolan log yükseltmeyle geri gelmez | [Render Logs](https://render.com/docs/logging) |
| Aktarım dayanağı | EU-ABD Data Privacy Framework sertifikası; yedek olarak AB Standart Sözleşme Maddeleri (2021/914) | [Render DPA](https://render.com/dpa) (19 Aralık 2024) |
| DPA | Hizmet şartlarına ek; ayrıca imza gerekmiyor görünüyor | aynı |
| Alt işleyenler | Liste: render.com/trust; yeni alt işleyen en az 10 gün önce bildirilir | aynı |
| Sözleşme bitince | Müşteri iade ya da silme seçer; süre belirtilmemiş | aynı |

**Sayfayla karşılaştırma:** "Render sunucu kayıtları, barındırma planına göre 7 ile 30 gün arasında saklanır"
doğru. "Sunucu kayıtlarında ... metninizden üretilen web araması sorguları yer alabilir" 1.0.0 için doğru, backend_v2'de
artık yazılmıyor (B2).

**Yapılacak (backend sahibi):** Render panelinde servisin bölgesini ve planını not edin. Frankfurt seçiliyse veri
yine yurt dışındadır (Almanya), ama sayfaya "sunucu Almanya'da" yazılabilir. Bölge sonradan değişmez.

## Groq

| Konu | Belge ne diyor | Kaynak |
|---|---|---|
| Varsayılan saklama | Çıkarım (inference) girdi ve çıktıları varsayılan olarak saklanmaz | [Groq: Your Data](https://console.groq.com/docs/your-data) |
| İstisna | Arıza giderme ve kötüye kullanım incelemesi için 30 güne kadar loglanabilir (yasal zorunluluk varsa daha uzun) | aynı |
| Zero Data Retention | Konsolda Data Controls ayarından açılır; açıkken bu istisna da kalkar. Kaybedilen: batch ve fine-tuning (verify ikisini de kullanmıyor) | aynı; [Data Controls](https://console.groq.com/settings/data-controls) |
| Eğitim | Girdi/çıktı müşteri izni olmadan eğitim ya da fine-tuning için **kullanılamaz** (Services Agreement m.4.2) | [Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement) (22 Haziran 2026) |
| Konum | Müşteri verisi ABD'deki Google Cloud depolarında; ABD'ye aktarım için SCC'ye dayanılabilir | Your Data |
| DPA | Sözleşmeye dahil (m.3.4, m.17.11) | Services Agreement |
| Sözleşme bitince | 30 gün içinde silinir (m.11.5) | aynı |

**Sayfayla karşılaştırma:** "Groq bu içerikleri varsayılan olarak saklamadığını, ancak arıza ve kötüye kullanım
incelemesi için 30 güne kadar saklayabileceğini belirtir" doğru. Eklenebilir: "Groq gönderilen içerikleri model
eğitiminde kullanmaz" (G1).

## Tavily

| Konu | Belge ne diyor | Kaynak |
|---|---|---|
| Toplanan | Sorgu verisi ("query data") ve yüklenen belgeler | [Tavily Privacy Policy](https://tavily.com/privacy) (24 Kasım 2025) |
| Saklama süresi | Hesap açık kaldıkça ya da amaç için gerektikçe; sabit süre yok | aynı |
| Kullanım | Sözleşmede aksi yoksa sorgu verisinin bir kısmı yanıtları geliştirmek için kullanılabilir; itiraz hakları bölümünde model eğitimi de geçer | aynı |
| Paylaşım | Kendi dizini yetmezse üçüncü taraf arama dizinlerine (ör. Google) | aynı |
| Konum ve aktarım | ABD merkezli (New York). Kurumsal müşteriler için SCC; bireysel kullanıcı için "veri doğrudan ABD'de toplandığı için sınır ötesi aktarım yok" deniyor | aynı |
| "Zero data retention" | SSS'de pazarlama cümlesi olarak geçiyor ("SOC 2 certified, zero data retention"), gizlilik politikasıyla çelişiyor; hangi planda geçerli olduğu belirtilmemiş | [Tavily FAQ](https://docs.tavily.com/faq) |
| Başvuru | support@tavily.com | Privacy Policy |

**Sayfayla karşılaştırma:** "Tavily, sorguları hizmetini geliştirmek için saklayabileceğini ve sınırlı durumlarda başka
arama sağlayıcılarıyla (ör. Google) paylaşabileceğini belirtir" doğru.

## KVKK: yurt dışına aktarım

Sayfa "gönderdiğiniz metin yurt dışına aktarılır" diyor ama **hangi dayanakla** aktarıldığını söylemiyor.
2024 değişikliğinden sonra KVKK m.9'a göre (yeterlilik kararı olmayan ülkeye) aktarım; uygun güvencelerden biriyle
(ör. Kurul'un yayımladığı **standart sözleşme**, imzadan sonra 5 iş günü içinde Kurum'a bildirilir) ya da sınırlı
istisnalarla (arızi aktarım ve m.9/6) yapılabilir. Kurum standart sözleşme bildirimi için ayrıca bir modül açtı
([KVKK duyurusu](https://www.kvkk.gov.tr/Icerik/8043/Standart-Sozlesme-Bildirim-Modulu-Hakkinda-Kamuoyu-Duyurusu)).
Render, Groq ve Tavily'nin belgeleri AB SCC'lerine ve DPF'ye dayanıyor; bunlar **KVKK standart sözleşmesi değildir**.

**Yapılacak (proje sahibi + hukukçu):** hangi dayanağın kullanılacağına karar verin ve gizlilik sayfasına tek cümleyle
ekleyin (K1). Bu karar verilmeden siteye "her şey hazır" denmemeli (`lib/legal.ts`, `LEGAL_COMPLETE`).

## Sayfa için önerilen değişiklikler (henüz uygulanmadı)

Yasal metin bu işte değiştirilmedi; onay sizde. Öneriler, hangi koşulda yapılacağıyla:

| Kod | Ne zaman | Öneri |
|---|---|---|
| B1 | backend_v2 yayına alınınca | "Ne kadar saklanır?" bölümüne: "Aynı iddia tekrar incelendiğinde hızlı yanıt vermek için iddia ve sonuç, sunucunun belleğinde en fazla 6 saat tutulur; diske ya da veritabanına yazılmaz ve sunucu yeniden başlayınca silinir." (`CACHE_TTL_SECONDS=21600`, `backend_v2/app/pipeline.py`, `TTLCache`) |
| B2 | backend_v2 yayına alınınca | Render maddesinden "metninizden üretilen web araması sorguları yer alabilir" kısmı çıkarılır; yerine "Sunucu kayıtlarında IP adresiniz ve isteğin zamanı yer alır; metniniz kayıtlara yazılmaz." |
| G1 | şimdi | Groq maddesine: "Groq bu içerikleri model eğitiminde kullanmaz." |
| G2 | Groq'ta ZDR açılınca | Groq maddesi: "Groq bu içerikleri saklamaz ve model eğitiminde kullanmaz." (30 gün cümlesi kalkar) |
| R1 | Render bölgesi öğrenilince | "Sunucumuz ...'da (bölge) çalışır." |
| K1 | hukuki karar verilince | Yurt dışı aktarımın dayanağı (ör. standart sözleşme). |
| T1 | şimdi (isteğe bağlı) | Tavily maddesine "sorgular model eğitiminde de kullanılabilir" eklenerek açıklık artırılır. |

## Teknik öneriler (backend)

- **G2:** Groq konsolunda Zero Data Retention'ı açmak (kod değişikliği gerekmez; batch/fine-tuning kullanılmıyor).
- **T2:** Tavily'ye support@tavily.com üzerinden ücretsiz/standart planda sorguların eğitimde kullanılmaması için
  itiraz ya da sözleşme seçeneği sorulmalı; SSS'deki "zero data retention" cümlesinin hangi planda geçerli olduğu yazılı
  olarak öğrenilmeli.
- **Sorgu küçültme:** Tavily'ye metnin kendisi değil iddialardan türetilen sorgular gidiyor; yine de metinde kişi adı
  varsa sorguya geçebilir. Sayfadaki "Göndermemeniz gerekenler" bölümü bu yüzden önemli.
- **Hata mesajları:** dış servis hata mesajları log'a yazılıyor (`log.exception`). Yayında `EXPOSE_ERROR_DETAIL=0`
  ayarlanmalı (yanıta da gitmesin) ve Render log planı kısa tutulmalı (Hobby: 7 gün).
