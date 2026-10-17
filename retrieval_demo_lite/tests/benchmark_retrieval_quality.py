"""Offline source-level relevance benchmark; fixture statements are NOT real-world facts.
Hand-authored labels precede execution. No ranking, date or production changes.
"""
from collections import Counter, defaultdict
from datetime import date
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import socket
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'retrieval_demo_lite'))
import search_retrieval_lite as mod

# claim, direct evidence, topical context, misleading context, category, stance.
# All evidence is deliberately fictional, not attributed to real institutions.
CASES = [
('Türkiye’de elektrikli araç satışları 2026 yılında arttı.', 'Türkiye için 2026 ve 2025 elektrikli otomobil satış adetlerini karşılaştıran tabloda 2026 toplamı daha yüksektir.', 'Türkiye otomobil pazarında şarj istasyonu sayısı artmıştır.', 'Almanya elektrikli araç satışları 2026 yılında arttı.', 'ekonomi/güncel', 'support'),
('Tesla Türkiye’de fabrika kuracak.', 'Türkiye yatırımı hakkındaki şirket açıklaması yeni fabrika planının bulunmadığını açıkça belirtmektedir.', 'Tesla Türkiye’de otomobil teslimatlarını ve servis ağını genişletmiştir.', 'Tesla Almanya’da fabrika kapasitesini artıracak.', 'şirket/yanlış bağlam', 'refute'),
('Türkiye 2026’da Ay’a insan gönderecek.', 'Program takviminde 2026 uçuşu insansız araştırma olarak tanımlanmıştır; insanlı Ay görevi yoktur.', 'Türkiye uzay programı kapsamında araştırma araçları geliştiriyor.', 'Bir bilim kurgu romanında Türkiye 2026’da Ay’a insan gönderecek.', 'bilim/tarih', 'refute'),
('Ankara’da metro hafta sonu 24 saat çalışıyor.', 'Ankara metro işletme çizelgesinde cumartesi ve pazar seferleri gece sona eriyor; kesintisiz hizmet verilmiyor.', 'Ankara metro istasyonlarında bakım yapılıyor.', 'İstanbul metro hattı hafta sonu 24 saat çalışıyor.', 'kamusal bilgi', 'refute'),
('Türkiye’de yıllık enflasyon eylül ayında yüzde 20 oldu.', 'Türkiye eylül yıllık enflasyon tablosu yüzde 20 değerini gösteriyor; aylık değişim ayrı sütundadır.', 'Enflasyon sepeti farklı ürün gruplarından oluşuyor.', 'Türkiye’de aylık gıda fiyatı artışı eylül ayında yüzde 20 oldu.', 'ekonomi/sayısal', 'support'),
('Yeni batarya teknolojisi şarj süresini yarıya indirdi.', 'Aynı kapasite ve sıcaklıkta yapılan karşılaştırmada yeni batarya 20, eski batarya 40 dakikada şarj oldu.', 'Batarya üretiminde geri dönüşüm araştırmaları sürüyor.', 'Yeni telefonun ekran parlaklığı şarj süresinden bağımsız olarak yarıya indirildi.', 'teknoloji/sayısal', 'support'),
('Güneş panelleri gece elektrik üretir.', 'Deneyde güneş ışığı yokken panel çıkışı ölçüm sınırının altında kaldı; gece kullanılan elektrik aküden geldi.', 'Güneş enerjisi sistemlerinde depolama kullanılabilir.', 'Güneş panelleri gece elektrik üretir başlıklı reklamda ölçüm verisi yoktur.', 'bilim', 'refute'),
('Bir şirket 2025 yılında çalışan sayısını ikiye katladı.', 'Şirket personel raporunda 2024 sonunda 500, 2025 sonunda 1000 çalışan olduğu yazıyor.', 'Şirket yeni bir ofis açtı.', 'Şirket 2025 yılında müşteri sayısını ikiye katladı, çalışan sayısı değişmedi.', 'şirket/sayısal', 'support'),
('İstanbul’da baraj doluluk oranı yüzde 90 oldu.', 'Aynı gün ölçülen İstanbul barajlarının toplam doluluk oranı raporda yüzde 90 olarak verilmiştir.', 'İstanbul su tüketimi yaz aylarında yükselir.', 'İzmir’de bir barajın doluluk oranı yüzde 90 oldu.', 'güncel/kamusal', 'support'),
('2024 yazı Türkiye’de ölçülen en sıcak yazdı.', 'Türkiye sıcaklık serisinde 2024 yaz ortalaması karşılaştırılan bütün yazlardan yüksek çıkmıştır.', 'Türkiye yaz sıcaklıkları bölgelere göre değişir.', '2024 kışı başka bir ülkede ölçülen en sıcak kıştı.', 'bilim/tarih', 'support'),
('Yeni ilaç hastalığı tamamen tedavi ediyor.', 'Kontrollü klinik çalışmada belirtiler azalmış, fakat hiçbir grupta tam iyileşme gösterilememiştir.', 'Yeni ilaç için çalışma tasarımı yayımlandı.', 'Yeni ilaç hastalığı tamamen tedavi ediyor ifadesi yalnız ürün reklamında yer alıyor.', 'bilim/sağlık', 'refute'),
('Üniversite sınavı 15 Haziran’da yapılacak.', 'Yayımlanan sınav takviminde sınav günü 22 Haziran, başvuru son günü 15 Haziran olarak yazılmıştır.', 'Üniversite sınavı için başvurular internetten yapılıyor.', 'Geçen yıl üniversite sınavı 15 Haziran’da yapılmıştı.', 'kamusal/tarih', 'refute'),
('Türkiye’de internet kullanıcı sayısı 80 milyonu geçti.', 'Nüfus araştırmasında tekil internet kullanıcısı sayısı 81 milyon olarak raporlanmıştır.', 'Mobil internet abone sayıları düzenli raporlanıyor.', 'Türkiye’de internet abonelik sayısı 80 milyonu geçti; aynı kişinin birden fazla aboneliği olabilir.', 'teknoloji/sayısal', 'support'),
('Yeni tren hattı yolculuk süresini iki saate düşürdü.', 'Açılış sonrası tarifede iki terminal arasındaki doğrudan yolculuk süresi iki saat olarak listeleniyor.', 'Yeni tren hattında istasyonlar yenilendi.', 'Yeni tren hattının yalnız ilk bölümü iki saatte geçiliyor, toplam yolculuk beş saat.', 'güncel/ulaşım', 'support'),
('Deniz suyu sıcaklığı son on yılda düştü.', 'Aynı ölçüm noktalarının on yıllık deniz suyu sıcaklık serisi düşüş değil artış gösteriyor.', 'Deniz suyu sıcaklığı mevsimsel değişim gösterir.', 'Deniz suyu sıcaklığı son on günde düştü.', 'bilim/yanlış dönem', 'refute'),
('Bir yazılım güncellemesi pil ömrünü yüzde 30 artırdı.', 'Aynı cihazlarla yapılan testte güncelleme sonrası pil ömrü 10 saatten 13 saate çıkmıştır.', 'Yazılım güncellemesi güvenlik düzeltmeleri içeriyor.', 'Bir yazılım güncellemesi işlemci hızını yüzde 30 artırdı.', 'teknoloji/sayısal', 'support'),
('Kütüphaneler pazar günü ücretsiz hizmet veriyor.', 'İncelenen kütüphanelerin pazar tarifesinde ziyaret saatleri ve sıfır giriş ücreti açıkça belirtiliyor.', 'Kütüphanelerin kitap koleksiyonları genişliyor.', 'Müzeler pazar günü ücretsiz hizmet veriyor.', 'kamusal bilgi', 'support'),
('Bir şirket gelecek ay tüm mağazalarını kapatacak.', '', 'Şirketin yıllık raporunda mağaza sayısı listeleniyor; gelecek ay için karar bulunmuyor.', 'Bir şirket gelecek ay tüm mağazalarını kapatacak başlıklı anonim paylaşım belge sunmuyor.', 'şirket/yetersiz kanıt', 'insufficient'),
('Yeni uydu depremi bir hafta önceden tahmin ediyor.', '', 'Uydu yer kabuğu hareketlerini ölçüyor; ileri tarihli deprem tahmini doğrulaması bulunmuyor.', 'Yeni uydu depremi bir hafta önceden tahmin ediyor iddiası doğrulanmamış bir forum mesajıdır.', 'bilim/yetersiz kanıt', 'insufficient'),
('Kentte toplu taşıma ücreti bugün yüzde 10 düştü.', 'Bugün yürürlüğe giren kent tarifesinde tam bilet 20 birimden 18 birime düşmüştür.', 'Kentte yeni otobüsler hizmete girmiştir.', 'Başka kentte toplu taşıma ücreti geçen yıl yüzde 10 düştü.', 'güncel/ekonomi', 'support'),
]
AS_OF = date(2026, 10, 17)
FILL = (' Bu deneysel metin yalnız kontrollü retrieval değerlendirmesi için hazırlanmıştır. '
        'Tablo kapsamı, örneklem ve ölçüm yöntemi ayrıca incelenmelidir. ')


def make_fixture(index, case):
    claim, direct, partial, wrong, category, stance = case
    # Two explicitly relevant documents when evidence exists; no invented truth labels.
    descriptions = [direct or partial, direct or partial, partial, wrong,
                    'Yerel spor turnuvasında final karşılaşmasının biletleri satışa çıktı.', wrong]
    labels = ['relevant' if direct else 'partially_relevant'] * 2 + ['partially_relevant','irrelevant','irrelevant','irrelevant']
    types = ['primary','secondary','primary','aggregator','secondary','aggregator']
    dates = ['2026-10-15','2020-01-02',None,'not-a-date','2027-01-01','2026-02-30']
    rows, gold, pages = [], {}, {}
    for j, body in enumerate(descriptions):
        host = ['original.example','media.example','original.example','aggregate.example','news.example','aggregate.example'][j]
        url = f'https://{host}/case-{index}/document-{j}'
        # Deliberately high lexical overlap for misleading candidate titles.
        title = claim if j in (3,5) else body[:110]
        row = dict(url=url,title=title,content=body,published_date=dates[j],score=[.8,.75,.65,.98,.3,.9][j])
        rows.append(row)
        gold[url] = dict(label=labels[j],source_type=types[j],rationale=body,
                         freshness='old_relevant' if j==1 and direct else 'recent_relevant' if j==0 and direct else 'other')
        pages[url] = ('<article>'+body+FILL*5+'</article>').encode()
    return rows,gold,pages


class Response:
    status_code=200
    encoding='utf-8'
    headers={'Content-Type':'text/html'}
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def raise_for_status(self): pass
    def iter_content(self,chunk_size):
        for i in range(0,len(self.data),chunk_size): yield self.data[i:i+chunk_size]


def dcg(grades):
    return sum((2**g-1)/math.log2(i+2) for i,g in enumerate(grades))


def run_case(index, case):
    rows,gold,pages=make_fixture(index,case)
    queries=mod.generate_queries(case[0])
    groups=[[0,2,3,4,5],[0,1,3,4,5],[1,2,3,4,5]]
    query_data=[]; first_seen={}; date_values=defaultdict(set)
    class Client:
        def search(self,query,timeout=5,**kwargs):
            position=queries.index(query)
            supplied=[dict(rows[j]) for j in groups[position]]
            if position==1: supplied[0]['published_date']='2026-10-16'
            q=dict(position=position+1,unique_relevant_urls=0,unique_irrelevant_urls=0,
                   final_relevant_sources=0,final_irrelevant_sources=0)
            for row in supplied:
                url=row['url'];date_values[url].add(str(row['published_date']))
                if url not in first_seen:
                    first_seen[url]=position+1
                    if gold[url]['label']=='relevant': q['unique_relevant_urls']+=1
                    if gold[url]['label']=='irrelevant': q['unique_irrelevant_urls']+=1
            query_data.append(q)
            return {'results':supplied}
    def get(session,url,**kwargs):
        assert session.trust_env is False and kwargs['stream'] and not kwargs['allow_redirects']
        return Response(pages[url])
    cache=mod._TavilyQueryCache();cache.enabled=False
    with patch.object(mod,'_tavily_cache',cache), patch.object(mod,'_get_tavily_client',return_value=Client()), \
         patch.object(mod.socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]), \
         patch.object(mod.requests.Session,'get',get):
        start=time.monotonic();result=mod.search_detailed(case[0],max_sources=5);elapsed=time.monotonic()-start
    selected=result['sources']; grades=[]; selected_relevant=set(); dates=Counter(); scores=defaultdict(list)
    for source in selected:
        label=gold[source['url']]['label'];grade={'relevant':2,'partially_relevant':1,'irrelevant':0}[label]
        grades.append(grade);scores[label].append(source['retrieval_score'])
        if grade==2: selected_relevant.add(source['url'])
        q=query_data[first_seen[source['url']]-1]
        if grade==2:q['final_relevant_sources']+=1
        if grade==0:q['final_irrelevant_sources']+=1
        value=source.get('published_date')
        if value:
            dates['available']+=1
            try:
                parsed=date.fromisoformat(value);dates['valid']+=1
                if parsed>AS_OF:dates['future']+=1
            except (TypeError,ValueError): dates['malformed']+=1
        dates['conflicting_url']+=len(date_values[source['url']])>1
    dates['duplicate_url_date'] = sum(v-1 for v in Counter((s['url'], s.get('published_date')) for s in selected if s.get('published_date')).values())
    for key in ('available','valid','malformed','future','conflicting_url','duplicate_url_date'):
        dates[key] += 0
    relevant_total=sum(v['label']=='relevant' for v in gold.values())
    ideal=sorted([{'relevant':2,'partially_relevant':1,'irrelevant':0}[v['label']] for v in gold.values()],reverse=True)[:5]
    domains=[s['domain'] for s in selected];n=len(selected)
    pairs=[(i,j) for i in range(n) for j in range(n) if grades[i]>grades[j]]
    wins=sum(1 if selected[i]['retrieval_score']>selected[j]['retrieval_score'] else .5 if selected[i]['retrieval_score']==selected[j]['retrieval_score'] else 0 for i,j in pairs)
    return dict(claim=case[0],category=case[4],fixture_stance=case[5],gold=gold,provider_rows=rows,
                sources=selected,diagnostics=result['diagnostics'],query_contribution=query_data,
                metrics=dict(recall_at_5=len(selected_relevant)/relevant_total if relevant_total else None,
                precision_at_5=sum(g==2 for g in grades)/5,mrr=next((1/(i+1) for i,g in enumerate(grades) if g==2),0),
                ndcg_at_5=dcg(grades)/dcg(ideal) if dcg(ideal) else None,
                irrelevant_count=sum(g==0 for g in grades),relevant_source_count=len(selected_relevant),
                unique_domains=len(set(domains)),duplicate_domain_rate=(n-len(set(domains)))/n if n else 0,
                primary_count=sum(gold[s['url']]['source_type']=='primary' for s in selected),
                selected_count=n,latency_seconds=elapsed,pair_wins=wins,pair_count=len(pairs)),
                dates=dict(dates),scores=dict(scores),
                source_types=dict(Counter(gold[s['url']]['source_type'] for s in selected)),
                freshness=dict(Counter(gold[s['url']]['freshness'] for s in selected)))


def main():
    production=[ROOT/'retrieval_demo_lite/search_retrieval_lite.py',ROOT/'backend_v2/app/retrieval.py']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in production}
    runs=[run_case(i,c) for i,c in enumerate(CASES)]
    def avg(key):return statistics.mean(r['metrics'][key] for r in runs if r['metrics'][key] is not None)
    n=sum(r['metrics']['selected_count'] for r in runs)
    dates=Counter();types=Counter();fresh=Counter();query=defaultdict(Counter);scores=defaultdict(list)
    for r in runs:
        dates.update(r['dates']);types.update(r['source_types']);fresh.update(r['freshness'])
        for k,v in r['scores'].items():scores[k].extend(v)
        for q in r['query_contribution']:
            query[q['position']].update({k:v for k,v in q.items() if k!='position'})
    summary={k:avg(k) for k in ('recall_at_5','precision_at_5','mrr','ndcg_at_5','unique_domains','duplicate_domain_rate','latency_seconds')}
    summary.update(irrelevant_evidence_rate=sum(r['metrics']['irrelevant_count'] for r in runs)/n,
                   primary_source_rate=types['primary']/n,selected_count=n,
                   relevant_source_count=sum(r['metrics']['relevant_source_count'] for r in runs),
                   score_averages={k:statistics.mean(v) for k,v in scores.items()},
                   pairwise_accuracy=sum(r['metrics']['pair_wins'] for r in runs)/sum(r['metrics']['pair_count'] for r in runs),
                   date_rates={k:v/n for k,v in dates.items()},date_counts=dict(dates),source_types=dict(types),freshness=dict(fresh))
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in production}
    old_spec=importlib.util.find_spec('search_retrieval')
    output=dict(environment=dict(python=sys.version,platform=platform.platform(),as_of=str(AS_OF)),
        methodology=dict(claim_count=len(CASES),labels='Hand-authored synthetic source-level labels, not factual truth judgments; no live web.',
            project_examples='First three claims from user examples; remaining 17 authored for category coverage. Existing project tests lack a labeled Turkish relevance corpus.',
            metrics='Macro P@5 (denominator 5); macro recall excludes two no-relevant cases; MRR includes them as zero; nDCG grades 2/1/0. Recall deduplicates URLs; precision counts output evidence items. Date rates use all selected items.',
            limitations='Adversarial fixed candidate mix: misleading pages deliberately get exact-claim titles and higher provider scores. No benign control arm; not representative prevalence. Synthetic prose/domain roles; source-level labels do not certify every selected chunk. Not a live-web quality estimate. Cache disabled. No network latency simulated.',
            source_types='Fixture roles only, not domain reputation claims.',dates='Provider dates passed through; conflicting dates collected across query responses.'),
        old_retrieval=dict(available=old_spec is not None,origin=old_spec.origin if old_spec else None,
            comparison=None,reason='Repository contains ArdaRetriever adapter but no search_retrieval implementation or comparable labeled old baseline.'),
        production_sha256=before,production_unchanged=True,raw_claims=runs,summary=summary,
        query_contribution=dict(query))
    path=Path(__file__).with_name('benchmark_results_retrieval_quality.json')
    if path.exists():raise FileExistsError('Existing results preserved')
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,query=dict(query)),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
