import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { AnalysisProgress, longWaitNote, maxWaitLabel } from "@/components/AnalysisProgress";
import { Brand } from "@/components/Brand";
import { ClaimItem } from "@/components/ClaimItem";
import { ErrorState } from "@/components/ErrorState";
import { ResultView } from "@/components/ResultView";
import { VerificationInput } from "@/components/VerificationInput";
import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";
import { CLAIM_LIST_ID, ERROR_COPY, VERDICT_META } from "@/lib/format";
import type { Claim, ErrorCode, Source, Verdict } from "@/lib/types";

const source = (n: number, o: Partial<Source> = {}): Source => ({
  id: `kaynak_${n}`,
  url: `https://ornek${n}.example/haber`,
  name: `Kaynak ${n}`,
  publishedAt: "2025-03-14",
  excerpt: `Pasaj ${n}`,
  ...o,
});
const claim = (o: Partial<Claim> = {}): Claim => ({
  id: "c1",
  text: "İddia",
  verdict: "SUPPORTED",
  explanation: "Açıklama [kaynak_1].",
  sources: [source(1)],
  confidence: null,
  ...o,
});
const render = (c: Claim) => renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />);

describe("ClaimItem", () => {
  it("her sonuç türünü simge + yazıyla gösterir (yalnızca renk değil)", () => {
    for (const v of Object.keys(VERDICT_META) as Verdict[]) {
      const html = render(claim({ verdict: v }));
      assert.ok(html.includes(VERDICT_META[v].label), v);
      assert.ok(html.includes(`data-icon="${VERDICT_META[v].icon}"`), v);
    }
  });
  it("kaynak yoksa 'kaynak bulunamadı' der ve 'yanlış' demez", () => {
    const html = render(claim({ verdict: "NOT_ENOUGH_EVIDENCE", sources: [], explanation: "" }));
    assert.ok(html.includes("Kaynak bulunamadı"));
    assert.ok(html.includes("yanlış olduğu anlamına gelmez"));
  });
  it("açıklama boşsa bunu söyler", () => {
    assert.ok(render(claim({ explanation: "" })).includes("açıklama gelmedi"));
  });
  it("listede olmayan atıfı bağlantıya çevirmez", () => {
    const html = render(claim({ explanation: "Şöyle [kaynak_9]." }));
    assert.ok(html.includes("Kaynak eşleşmesi bulunamadı"));
    assert.ok(!html.includes("[kaynak_9]"));
    assert.ok(!html.includes('href="#src-c1-9"'));
  });
  it("atıf olmayan köşeli parantezli metni silmez; 'kaynak eşleşmesi bulunamadı' demez", () => {
    const html = render(claim({ explanation: "TÜİK [2023] verisi ve alıntı [...] ile [sic] [kaynak_1]." }));
    assert.ok(html.includes("TÜİK [2023] verisi ve alıntı [...] ile [sic] "));
    assert.ok(!html.includes("Kaynak eşleşmesi bulunamadı"));
    assert.ok(html.includes('href="#src-c1-1"'));
  });
  it("güvensiz bağlantıyı (javascript:) tıklanabilir yapmaz", () => {
    const html = render(claim({ sources: [source(1, { url: "javascript:alert(1)" })] }));
    assert.ok(!html.includes('href="javascript:'));
    assert.ok(html.includes("Bağlantı geçersiz"));
  });
  it("çok uzun iddiayı ve kaynak adını çökmeden gösterir; alıntıyı keser", () => {
    const html = render(claim({ text: "uzun ".repeat(400), sources: [source(1, { name: "A".repeat(500), excerpt: "b ".repeat(500) })] }));
    assert.ok(html.includes("A".repeat(500)));
    assert.ok(html.includes("…"));
  });
  it("ad ve tarih yoksa kaynak tek sütundur: alan adı gösterilir, 'belirtilmemiş' yazılmaz", () => {
    const html = render(claim({ sources: [source(1, { name: null, publishedAt: null, excerpt: null })] }));
    assert.ok(html.includes("ornek1.example"));
    assert.ok(html.includes("evidence--plain"));
    assert.ok(!html.includes("belirtilmemiş"));
    assert.ok(html.includes("alıntı gelmedi"));
  });
  it("ad ya da tarih varsa iki sütunlu satır kullanılır; yalnızca gelen bilgi gösterilir", () => {
    const withName = render(claim({ sources: [source(1, { publishedAt: null })] }));
    assert.ok(!withName.includes("evidence--plain"));
    assert.ok(!withName.includes("<time"));
    assert.ok(render(claim()).includes('<time dateTime="2025-03-14">14 Mart 2025</time>'));
  });
  it("sonuç kutusu etiketi yinelemez; yalnızca 'yeterli kanıt yok' sonucunda uyarı gösterir", () => {
    const ok = render(claim({ verdict: "SUPPORTED" }));
    assert.ok(!ok.includes(VERDICT_META.SUPPORTED.meaning));
    assert.ok(!ok.includes("verdict-caveat"));
    const nee = render(claim({ verdict: "NOT_ENOUGH_EVIDENCE" }));
    assert.equal((nee.match(/yanlış olduğu anlamına gelmez/g) ?? []).length, 1);
  });
  it("kaynak satırı açıklamadaki cümleyi yinelemez", () => {
    assert.ok(!render(claim()).includes("dayanılan ifade"));
  });
  it("güven puanı varsa yüzde olarak ve 'olasılık değildir' notuyla gösterir", () => {
    const html = render(claim({ confidence: 0.91 }));
    assert.ok(html.includes("%91"));
    assert.ok(html.includes("Modelin güven puanı"));
    assert.ok(html.includes("doğru olma olasılığı değil"));
  });
  it("güven puanı yoksa hiçbir yüzde ya da puan metni göstermez (uydurmaz)", () => {
    const html = render(claim({ confidence: null }));
    assert.ok(!/güven puanı/i.test(html.replace(/Güven puanı kesinlik/g, "")));
    assert.ok(!/%\s?\d|\d\s?%/.test(html));
  });
  it("0 puanını da doğru gösterir (yok sayılmaz)", () => {
    assert.ok(render(claim({ confidence: 0 })).includes("%0"));
  });
  it("örnek veri modunda her iddiada 'Örnek veri' etiketi gösterir; gerçek modda göstermez", () => {
    const sample = renderToStaticMarkup(<ClaimItem claim={claim()} index={0} total={1} sample />);
    assert.ok(sample.includes("Örnek veri"));
    assert.ok(sample.includes("gerçek bir inceleme değil"));
    assert.ok(!render(claim()).includes("Örnek veri"));
  });
  it("örnek veri modunda güven puanını göstermez (uydurma yüzde gerçek sanılmasın)", () => {
    const sample = renderToStaticMarkup(<ClaimItem claim={claim({ confidence: 0.91 })} index={0} total={1} sample />);
    assert.ok(!sample.includes("%91"));
    assert.ok(!sample.includes("Modelin güven puanı"));
    assert.ok(sample.includes("claim-item--sample"));
  });
  it("açıklama kaynağa atıf yapıyorsa 'Dayandığımız kanıtlar' der", () => {
    const html = render(claim({ explanation: "Açıklama [kaynak_1].", sources: [source(1), source(2)] }));
    assert.ok(html.includes("Dayandığımız kanıtlar (1)"));
    assert.ok(html.includes("Diğer kaynaklar (1)"));
  });
  it("atıf yoksa kaynaklara 'dayandık' demez; yalnızca bulunan kaynakları listeler", () => {
    const html = render(claim({ explanation: "Atıfsız açıklama.", sources: [source(1), source(2), source(3)] }));
    assert.ok(!html.includes("Dayandığımız kanıtlar"));
    assert.ok(html.includes("Bulunan kaynaklar (3)"));
    assert.ok(html.includes("hangi kaynaklara dayandığı belirtilmedi"));
  });
  it("sonuç etiketleri birbirinden ayırt edilebilir (çürütülen ≠ kaynaklar birbiriyle çelişiyor)", () => {
    const labels = Object.values(VERDICT_META).map((m) => m.label);
    assert.equal(new Set(labels).size, labels.length);
    assert.ok(VERDICT_META.REFUTED.label.includes("iddiayla"));
  });
});

describe("ResultView", () => {
  const noop = () => {};
  it("iddia yoksa boş durumu gösterir", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [], unverifiable: [], unreadable: [] }} onReset={noop} />);
    assert.ok(html.includes("İncelenebilir iddia bulunamadı"));
  });
  it("birden fazla iddiada özet listesi ve doğrulanmayan ifadeleri gösterir", () => {
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [claim({ id: "a" }), claim({ id: "b", verdict: "CONFLICTING" })], unverifiable: ["Bence harika."], unreadable: [] }} onReset={noop} />,
    );
    assert.ok(html.includes("2 iddia incelendi"));
    assert.ok(html.includes('aria-label="İncelenen iddialar"'));
    assert.ok(html.includes("Bence harika."));
  });
  it("backend'den gelen metni HTML olarak yorumlamaz", () => {
    const evil = "<script>alert(1)</script>";
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [claim({ text: evil, explanation: evil })], unverifiable: [evil], unreadable: [] }} onReset={noop} />,
    );
    assert.ok(!html.includes("<script>alert(1)"));
  });
  it("gönderilen içeriği yinelemez (içerik yukarıdaki salt okunur alanda zaten görünür)", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={noop} />);
    assert.ok(!html.includes("Gönderdiğiniz içerik"));
  });
  it("sabit örnek sonuç baştan sona örnek olarak etiketlenir ve 'kapat' ile biter", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={noop} sample showcase />);
    assert.ok(html.includes("Örnek inceleme"));
    assert.ok(html.includes("önceden hazırlanmıştır; canlı analiz değildir"));
    assert.ok(html.includes("Örnek veri"));
    assert.ok(html.includes("Örneği kapat"));
    assert.ok(!html.includes("Yeni bir içerik incele"));
    assert.ok(!html.includes("otomatik bir ön değerlendirmedir"));
  });
  it("gerçek sonuçta örnek etiketi yoktur", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={noop} />);
    assert.ok(!html.includes("Örnek"));
    assert.ok(html.includes("Yeni bir içerik incele"));
  });
  it("örnek veri bayrağını iddialara iletir", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={noop} sample />);
    assert.ok(html.includes("Örnek veri"));
  });
});

describe("kısmi sonuç", () => {
  it("incelenemeyen iddiaları nedeniyle listeler ve hüküm yazmaz", () => {
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [], unfinished: [{ text: "Geç kalan iddia", reason: "timeout" }, { text: "Atlanan iddia", reason: "skipped" }] }} onReset={() => {}} />,
    );
    assert.ok(html.includes("2 iddia incelenemedi"));
    assert.ok(html.includes("İncelenemeyen iddialar (2)"));
    assert.ok(html.includes("Geç kalan iddia"));
    assert.ok(html.includes("süre sınırı içinde incelenemedi"));
    assert.ok(html.includes("metinde çok iddia olduğu için incelenmedi"));
  });
  it("hiçbir iddia incelenemediyse 'iddia bulunamadı' demez", () => {
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [], unverifiable: [], unreadable: [], unfinished: [{ text: "A", reason: "error" }] }} onReset={() => {}} />,
    );
    assert.ok(html.includes("İddialar incelenemedi"));
    assert.ok(!html.includes("somut bir iddia bulunamadı"));
  });
  it("sonucu okunamayan iddiaları başta uyarıyla, sonda ayrı listeyle gösterir; hüküm yazmaz", () => {
    const html = renderToStaticMarkup(
      <ResultView result={{ claims: [claim()], unverifiable: [], unreadable: ["Okunamayan iddia"] }} onReset={() => {}} />,
    );
    assert.ok(html.includes("1 iddia incelendi"));
    assert.ok(html.includes("1 iddianın sonucu okunamadı"));
    assert.ok(html.includes("Sonucu gösterilemeyen iddialar (1)"));
    assert.ok(html.includes("Okunamayan iddia"));
    assert.ok(html.includes("doğru ya da yanlış olduğu anlamına gelmez"));
  });
  it("okunamayan iddia yoksa uyarı da bölüm de yoktur", () => {
    const html = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={() => {}} />);
    assert.ok(!html.includes("okunamadı"));
    assert.ok(!html.includes("Sonucu gösterilemeyen"));
  });
});

describe("uzun sonuçta gezinme ve marka", () => {
  it("birden fazla iddiada her iddia listeye geri bağlanır; tek iddiada bağlantı yoktur", () => {
    const many = renderToStaticMarkup(
      <ResultView result={{ claims: [claim({ id: "a" }), claim({ id: "b" })], unverifiable: [], unreadable: [] }} onReset={() => {}} />,
    );
    assert.ok(many.includes(`id="${CLAIM_LIST_ID}"`));
    assert.equal(many.split(`href="#${CLAIM_LIST_ID}"`).length - 1, 2);
    const one = renderToStaticMarkup(<ResultView result={{ claims: [claim()], unverifiable: [], unreadable: [] }} onReset={() => {}} />);
    assert.ok(!one.includes(`#${CLAIM_LIST_ID}`));
  });
  it("marka adı ve slogan tek kaynaktan gelir; alt bilgide bağlantı değildir", () => {
    const top = renderToStaticMarkup(<Brand href="#main" tagline />);
    assert.ok(top.includes(`<a class="brand" href="#main">${SITE_NAME}</a>`));
    assert.ok(top.includes(SITE_TAGLINE));
    const foot = renderToStaticMarkup(<Brand small />);
    assert.equal(foot, `<span class="brand brand--small">${SITE_NAME}</span>`);
  });
});

describe("VerificationInput örnekleri", () => {
  it("bekleme sırasında gönder düğmesi durumu bildirir ve ikinci gönderimi engeller", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} busy disabled />);
    assert.ok(html.includes('aria-busy="true"'));
    assert.match(html, /<button[^>]*type="submit"[^>]*disabled/);
    assert.ok(html.includes("İnceleniyor…"));
  });
  it("sonuç gelince form tek satırlık özete iner ve yeni gönderim yerine düzenleme sunar", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} readOnly onEdit={() => {}} />);
    assert.ok(html.includes("input-summary"));
    assert.ok(html.includes("İncelenen metin"));
    assert.ok(html.includes("İçeriği düzenle"));
    assert.ok(!html.includes("<textarea"));
    assert.ok(!html.includes('type="submit"'));
  });
  it("servis bağlantıyı desteklemiyorsa 'Metin / Bağlantı' seçimi hiç gösterilmez", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} urlSupported={false} />);
    assert.ok(!html.includes("Girdi türü"));
    assert.ok(!html.includes('type="radio"'));
    assert.ok(html.includes("<textarea"));
  });
  it("hata gösterilirken gönder düğmesi ikincil görünür (tek birincil eylem hata panelinde)", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} demoteSubmit />);
    assert.match(html, /<button[^>]*type="submit"[^>]*class="btn btn-quiet"/);
    assert.match(renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />), /<button[^>]*type="submit"[^>]*class="btn"/);
  });
  it("sayaç sınırı görünür biçimde taşır; düğme metninde ok işareti yoktur", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />);
    assert.match(html, /class="field-count tnum" data-state="ok"[^>]*>0 \/ 3\.000</);
    assert.ok(html.includes("En fazla 3.000 karakter."));
    assert.ok(!html.includes("→"));
  });
  it("içeriğin dış servislere gittiğini söyler ve kişisel bilgi yapıştırılmamasını ister (alanın açıklamasına bağlı)", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />);
    const note = html.match(/<p id="([^"]+)" class="form-privacy[^"]*">([\s\S]*?)<\/p>/);
    assert.ok(note, "gizlilik notu bulunamadı");
    assert.ok(note[2].includes("yurt dışındaki yapay zekâ (Groq) ve web araması (Tavily) servislerine gönderilir"));
    assert.ok(note[2].includes("kişisel bilgileri eklemeyin"));
    const described = html.match(/<textarea[^>]*aria-describedby="([^"]+)"/)?.[1].split(" ") ?? [];
    assert.ok(described.includes(note[1]), "not, metin alanının açıklamasına bağlı değil");
    // Gönderimden hemen önce de duyurulsun: düğme de nota bağlı (formdaki bilgilendirme).
    const button = html.match(/<button[^>]*type="submit"[^>]*aria-describedby="([^"]+)"/)?.[1].split(" ") ?? [];
    assert.ok(button.includes(note[1]), "not, gönder düğmesine bağlı değil");
  });
  it("girdi türü grubunu tek kez adlandırır (fieldset + legend; ikinci bir radiogroup etiketi yok)", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />);
    assert.equal((html.match(/Girdi türü/g) ?? []).length, 1);
    assert.ok(/<legend[^>]*>Girdi türü<\/legend>/.test(html));
    assert.ok(!html.includes('role="radiogroup"'));
  });
  it("servis bağlı değilken devre dışı alan ve düğme, nedenini anlatan nota bağlanır", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} disabled noticeId="not" />);
    assert.match(html, /<textarea[^>]*aria-describedby="[^"]*\bnot\b[^"]*"/);
    assert.match(html, /<button[^>]*type="submit"[^>]*aria-describedby="not [^"]*-privacy"/);
    const plain = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} />);
    assert.match(plain, /<button[^>]*type="submit"[^>]*aria-describedby="[^" ]*-privacy"/);
  });
  const ex = (label: string, dev?: boolean) => ({ label, mode: "text" as const, content: label, dev });
  it("geliştirici senaryolarını ayrı ve etiketli bir grupta gösterir", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} examples={[ex("Sonuç örneği"), ex("Hata denemesi", true)]} />);
    assert.ok(html.includes("Geliştirici senaryoları"));
    assert.ok(html.indexOf("Sonuç örneği") < html.indexOf("Geliştirici senaryoları"));
    assert.ok(html.indexOf("Hata denemesi") > html.indexOf("Geliştirici senaryoları"));
  });
  it("geliştirici senaryosu yoksa o grubu hiç göstermez; alan etiketi 'incele' dilini kullanır", () => {
    const html = renderToStaticMarkup(<VerificationInput onSubmit={() => {}} examples={[ex("Sonuç örneği")]} />);
    assert.ok(!html.includes("Geliştirici senaryoları"));
    assert.ok(html.includes("Haber metnini yapıştır"));
  });
});

describe("ErrorState ve AnalysisProgress", () => {
  it("her hata kodu 'Ne oldu?' ve 'Şimdi ne yapabilirsiniz?' içerir", () => {
    for (const code of Object.keys(ERROR_COPY) as ErrorCode[]) {
      const html = renderToStaticMarkup(<ErrorState error={{ code, message: "m" }} onRetry={() => {}} onEdit={() => {}} />);
      assert.ok(html.includes("Ne oldu?") && html.includes("Şimdi ne yapabilirsiniz?"), code);
      assert.equal(html.includes("Yeniden dene"), ERROR_COPY[code].retry, code);
    }
  });
  it("desteklenmeyen bağlantı hatası 'sayfa açılamadı' demez; metin sekmesine yönlendirir", () => {
    const html = renderToStaticMarkup(<ErrorState error={{ code: "URL_UNSUPPORTED", message: "m" }} onRetry={() => {}} onEdit={() => {}} />);
    assert.ok(html.includes("henüz desteklenmiyor"));
    assert.ok(!html.includes("açılamadı"));
    assert.ok(html.includes("metin giriş alanından"));
    assert.ok(!html.includes("Yeniden dene"));
  });
  it("aşama bilgisi yokken adım listesi hiç gösterilmez; yalnızca geçen süre sayılır", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(!html.includes("<ol"));
    assert.ok(!html.includes("adım bilgisi alınmıyor"));
    assert.ok(html.includes("Geçen süre:"));
    assert.ok(html.includes("0:00"));
    const staged = renderToStaticMarkup(<AnalysisProgress phase="verifying" onCancel={() => {}} />);
    assert.ok(staged.includes("<ol"));
  });
  it("aşama bilgisi yokken hiçbir adımı 'şu an' diye işaretlemez; yüzde göstermez", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(!html.includes('aria-current="step"'));
    assert.ok(!/\d\s?%/.test(html));
    assert.ok(html.includes("Vazgeç"));
  });
  it("backend aşama verirse yalnızca o adım işaretlenir", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="retrieving_evidence" onCancel={() => {}} />);
    assert.equal((html.match(/aria-current="step"/g) ?? []).length, 1);
  });
  it("hata ve bekleme başlıkları odaklanabilir (odak sayfa başına düşmesin)", () => {
    const err = renderToStaticMarkup(<ErrorState error={{ code: "TIMEOUT", message: "m" }} onRetry={() => {}} onEdit={() => {}} />);
    assert.ok(/<h2[^>]*tabindex="-1"/.test(err));
    const busy = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(/<h2[^>]*tabindex="-1"/.test(busy));
  });
  it("odak başlığa taşındığı için panelin tamamı ayrıca canlı bölge olarak okunmaz (çift duyuru yok)", () => {
    const err = renderToStaticMarkup(<ErrorState error={{ code: "TIMEOUT", message: "m" }} onRetry={() => {}} onEdit={() => {}} />);
    assert.ok(!err.includes('role="alert"'));
    const busy = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(!/class="state analysis-progress"[^>]*role=/.test(busy));
    assert.ok(!busy.includes("aria-live"));
  });
  it("aşama değişimi yalnızca kısa bir durum satırıyla duyurulur; aşama yokken satır boştur", () => {
    const idle = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.equal((idle.match(/role="status"/g) ?? []).length, 1);
    assert.match(idle, /<p class="sr-only" role="status"><\/p>/);
    const staged = renderToStaticMarkup(<AnalysisProgress phase="retrieving_evidence" onCancel={() => {}} />);
    assert.match(staged, /<p class="sr-only" role="status">Kaynaklar aranıyor \(adım 2 \/ 3\)<\/p>/);
  });
  it("sunucu beklenirken 'inceleniyor' demez; yanıtın beklendiğini söyler ve bunu ekran okuyucuya duyurur", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="waiting_server" onCancel={() => {}} />);
    assert.match(html, /<h2[^>]*>Sunucunun yanıtı bekleniyor<\/h2>/);
    assert.ok(!html.includes("İçerik inceleniyor"));
    assert.match(html, /<p class="sr-only" role="status">Sunucunun yanıtı bekleniyor\.<\/p>/);
    assert.ok(!html.includes("<ol"));
    assert.ok(html.includes("Geçen süre:") && html.includes("Vazgeç"));
  });
  it("uzun bekleme notu 30. saniyede çıkar; sunucu beklenirken 'inceleme sürüyor' denmez", () => {
    assert.equal(longWaitNote("submitting", 29), null);
    assert.ok(longWaitNote("submitting", 30)?.startsWith("İnceleme sürüyor."));
    assert.ok(longWaitNote("verifying", 75)?.startsWith("İnceleme sürüyor."));
    assert.equal(longWaitNote("waiting_server", 75), null);
  });
  it("bekleme metni belirsiz bir süre vaat etmez; yalnızca arayüzün kesin üst sınırını söyler", () => {
    const html = renderToStaticMarkup(<AnalysisProgress phase="submitting" onCancel={() => {}} />);
    assert.ok(!/birkaç|yaklaşık|genellikle|saniye/.test(html));
    assert.equal((html.match(/dakika/g) ?? []).length, 1);
    assert.ok(html.includes("en geç 4 dakika sonra"));
    assert.equal(maxWaitLabel(150_000), "2,5 dakika");
    assert.equal(maxWaitLabel(60_000), "1 dakika");
  });
});

it("eşleşmeyen atıf geçerli komşu atfın bağlantısını engellemez", () => {
  const html = render(claim({ explanation: "Kanıt [kaynak_1, olmayan_kaynak]." }));
  assert.ok(html.includes('href="#src-c1-1"'));
  assert.ok(html.includes("Kaynak eşleşmesi bulunamadı"));
  assert.ok(!html.includes("olmayan_kaynak"));
});

it("kapalı örnek iddiada örnek etiketi ve eksik kanıt uyarısı başlıkta kalır", () => {
  const html = renderToStaticMarkup(<ClaimItem claim={claim({ sources: [] })} index={0} total={1} expanded={false} sample />);
  const summary = html.match(/<summary[\s\S]*?<\/summary>/)?.[0] ?? "";
  assert.ok(summary.includes("Örnek veri"));
  assert.ok(summary.includes("Kanıt bilgisi eksik"));
  assert.ok(!html.includes('<details class="claim-disclosure" open'));
});

it("servis yokken metin yazılabilir ama gönderim eylemi sunulmaz", () => {
  const html = renderToStaticMarkup(<VerificationInput unavailable urlSupported={false} onSubmit={() => { throw new Error("Gönderilmemeli"); }} />);
  assert.ok(html.includes("<textarea"));
  assert.ok(!/<textarea[^>]*disabled/.test(html));
  assert.ok(!html.includes('type="submit"'));
  assert.ok(html.includes("Metin ve sonuçlar kaydedilmez; sayfa yenilenince kaybolur"));
  assert.ok(!html.includes("servislerine gönderilir"));
});

it("okunamayan rapor tarihi için boş 'İnceleme tarihi' satırı çizilmez", () => {
  const base = { claims: [], unverifiable: [], unreadable: [] };
  const ambiguous = renderToStaticMarkup(<ResultView result={{ ...base, report: { preparedAt: "05.10.2026" } }} onReset={() => {}} />);
  assert.ok(!ambiguous.includes("İnceleme tarihi"));
  const iso = renderToStaticMarkup(<ResultView result={{ ...base, report: { preparedAt: "2026-10-05" } }} onReset={() => {}} />);
  assert.ok(iso.includes("İnceleme tarihi") && iso.includes("5 Ekim 2026"));
});
