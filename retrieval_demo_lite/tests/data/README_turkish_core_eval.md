# Türkçe core evaluation set

32 sentetik vaka: SUPPORTED, REFUTED, NOT_ENOUGH_EVIDENCE ve CONFLICTING için sekizer örnek. Sekiz kategori; 8 easy, 16 medium, 8 hard. Kurum isimleri ve `.example.test` kaynakları kurgusaldır; gerçek web haberi veya doğrulanmış dünya bilgisi değildir.

Her JSONL satırı bir case: `id`, `claim`, `category`, `expected_verdict`, `difficulty`, `tags`, `evidence`, `notes`. Evidence alanları: `source_id`, `url`, `title`, `text`, `domain`, `published_date`, `source_type`, `relevance_label`, `stance`, `provider_score`.

Canonical NOT_ENOUGH_EVIDENCE, mevcut AI engine'de `NOT ENOUGH EVIDENCE` olarak kullanılır. Diğer üç etiket aynıdır; CONFLICTING desteklenir. Relevance etiketleri relevant / partially_relevant / irrelevant; stance supports / refutes / neutral. Stance/verdict/relevance gold alanları retrieval veya verifier girdisine aktarılmaz.

## Çalıştırma

Repo kökünden, tamamen offline:

```sh
python3 -B retrieval_demo_lite/tests/evaluate_turkish_core.py --retrieval-only
```

Schema/stance validation, altı negatif validation testi, iki deterministik retrieval turu ve JSON raporu birlikte çalışır. Rapor varsayılan olarak `tests/benchmark_results_turkish_core.json` yoluna yazılır. Başka raporu korumak için `--output` kullanın.

Verifier modu ağ izni olmadan temizce skip eder:

```sh
python3 -B retrieval_demo_lite/tests/evaluate_turkish_core.py --verifier --output /tmp/core_skip.json
```

Mert gerçek Groq değerlendirmesi yapmak istediğinde, gerekli SDK ve ortamda GROQ_API_KEY ile açık network izni vermelidir:

```sh
python3 -B retrieval_demo_lite/tests/evaluate_turkish_core.py --verifier --allow-network --verifier-input fixture --output /tmp/core_verifier.json
```

`fixture` tüm kontrollü evidence'ı, `retrieved` gerçek Lite seçimlerini verifier'a verir. Verifier'a yalnız claim ve Source(id, url, text) gönderilir. Gerçek çağrı yapılmadıysa accuracy/F1 üretilmez. Ağ/API/model değişkenliği nedeniyle canlı verifier sonucu deterministik garanti edilmez.

## Yorumlama

Etiketler metinler okunarak elle tasarlanmıştır; CONFLICTING çiftleri aynı dönem ve ölçüm hakkında güçlü kaynaklarda açık karşıt bilgi içerir. Otomatik validation stance tutarlılığını denetler; metinsel anlamı bağımsız olarak ispatlamaz. Mert'in bağımsız label incelemesi önerilir.

Retrieval gerçek Lite query üretimi, güvenlik/fetch, chunking, ranking ve MMR kullanır; Tavily/DNS/HTTP dış sınırları mock'tur, cache kapalıdır. Kısa kaynaklarda mevcut snippet fallback çalışabilir. Her query aynı kontrollü aday havuzunu döndürür; canlı arama keşif kalitesi ölçülmez.

Macro P@5'in paydası 5'tir; NEE vakalarının relevant kaynağı yoktur. Recall bu vakaları hariç tutar; MRR sıfır sayar. Recall/P@5/MRR/nDCG için URL tekrarları elenir, diğer oranlar çıktı evidence öğeleri üzerinden hesaplanır. nDCG dereceleri 2/1/0. Aday havuzu yalnız 4–5 kaynak olduğu için Recall@5 tavan etkisi taşır. Kategori ve difficulty kırılımları rapordadır.

Core set dengeli regression/verifier değerlendirmesi içindir. Görev 8 `benchmark_retrieval_quality.py` ayrı adversarial stress set olarak korunur; iki setin sonuçları birbirinin yerine kullanılamaz. Core set bir üretim doğruluk sertifikası değildir.
