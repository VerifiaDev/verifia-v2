"use client";

import { useEffect, useRef, useState } from "react";
import { ClaimItem } from "./ClaimItem";
import { ClaimList } from "./ClaimList";
import type { CheckResult } from "@/lib/types";
import { VERDICT_META, VERDICT_ORDER, CLAIM_LIST_ID, UNFINISHED_REASON, claimAnchor, sourceAnchor } from "@/lib/format";
import { Icon } from "./Icon";
import { ReportTools } from "./ReportTools";
import { formatDate } from "@/lib/format";
import { LegendDisclosure } from "./Legend";

interface Props {
  input?: string;
  result: CheckResult;
  onReset: () => void;
  /** Örnek (mock) veri modunda true: her iddiada "örnek veri" etiketi gösterilir. */
  sample?: boolean;
  /** Sabit örnek sonuç (servis bağlı değilken): başlık, not ve kapatma düğmesi buna göre değişir. */
  showcase?: boolean;
}

/**
 * Sonuç, giriş kartının dışında kendi bölümünde durur (kartın içinde uzun, dar bir sütuna sıkışmasın diye).
 * Gönderilen içerik burada yinelenmez: yukarıdaki kartta özet olarak durur.
 */
export function ResultView({ result, onReset, sample = false, showcase = false, input }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { claims, unverifiable, unreadable } = result;
  const unfinished = result.unfinished ?? [];
  const preparedDate = formatDate(result.report?.preparedAt ?? null);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(claims[0] ? [claims[0].id] : []));
  const [listOpen, setListOpen] = useState(false);
  const [target, setTarget] = useState<string | null>(null);
  function navigateTo(id: string) {
    window.history.pushState(null, "", `#${id}`);
    if (id === CLAIM_LIST_ID) setListOpen(true);
    const claim = claims.find((c) => claimAnchor(c.id) === id);
    if (claim) setExpanded((current) => new Set(current).add(claim.id));
    setTarget(id);
  }
  useEffect(() => {
    const revealHash = () => {
      const hash = window.location.hash.slice(1);
      const claim = claims.find((c) => claimAnchor(c.id) === hash || c.sources.some((_, i) => sourceAnchor(c.id, i + 1) === hash));
      if (claim) setExpanded((current) => new Set(current).add(claim.id));
      if (hash === CLAIM_LIST_ID) setListOpen(true);
      if (claim || hash === CLAIM_LIST_ID || hash === "report") setTarget(hash);
      return Boolean(claim || hash === CLAIM_LIST_ID || hash === "report");
    };
    if (!revealHash()) headingRef.current?.focus();
    window.addEventListener("hashchange", revealHash);
    return () => window.removeEventListener("hashchange", revealHash);
  }, [claims]);

  useEffect(() => {
    if (!target) return;
    const frame = requestAnimationFrame(() => {
      const element = document.getElementById(target);
      if (!element) return;
      // Kaynak, kapalı bir "Diğer kaynaklar" bölümünde de bulunabilir.
      let parent = element.parentElement;
      while (parent && parent.id !== "report") {
        if (parent instanceof HTMLDetailsElement) parent.open = true;
        parent = parent.parentElement;
      }
      const focusTarget = target === CLAIM_LIST_ID ? element.querySelector<HTMLElement>("summary") : target === "report" ? headingRef.current : element;
      if (focusTarget) {
        if (!focusTarget.hasAttribute("tabindex") && focusTarget.tagName !== "SUMMARY") focusTarget.tabIndex = -1;
        focusTarget.focus({ preventScroll: true });
      }
      element.scrollIntoView({ block: "start", behavior: "instant" });
      setTarget(null);
    });
    return () => cancelAnimationFrame(frame);
  }, [target, expanded, listOpen]);

  return (
    <section aria-labelledby="result-title" className="result" id="report">
      <div className="result-head">
        <p className="result-kicker">{showcase ? "Örnek inceleme" : "İnceleme sonucu"}</p>
        <h2 id="result-title" ref={headingRef} tabIndex={-1} className="t-h2 result-title">
          {result.report?.title ?? (claims.length === 0 ? (unfinished.length > 0 ? "İddialar incelenemedi" : "İncelenebilir iddia bulunamadı") : `${claims.length} iddia incelendi`)}
        </h2>
        {/* Tarih yalnızca kesin okunabiliyorsa gösterilir (bkz. formatDate); okunamıyorsa satır hiç çizilmez. */}
        {preparedDate && <p className="report-byline t-meta muted">{showcase ? "Hazır örnek" : "İnceleme tarihi"} · <time dateTime={result.report?.preparedAt}>{preparedDate}</time></p>}

        {showcase && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Örnek</strong>
            <span>
              Bu rapor önceden hazırlanmıştır; canlı analiz değildir. Örnek metin eğitim amaçlı oluşturulmuştur, kaynak bağlantıları gerçektir.
            </span>
          </p>
        )}
        {result.report?.summary && <details className="more report-brief"><summary>Kısa değerlendirmeyi oku <Icon name="chevron" className="chevron" /></summary><p>{result.report.summary}</p></details>}
        {(result.report?.input ?? input) && <details className="more report-input"><summary>İncelenen metni gör <Icon name="chevron" /></summary><p>{result.report?.input ?? input}</p></details>}

        {unfinished.length > 0 && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Eksik</strong>
            <span>
              {unfinished.length} iddia incelenemedi; bu iddialar aşağıda ayrıca listelenir. Bu, iddiaların doğru ya da yanlış olduğu anlamına gelmez.
            </span>
          </p>
        )}
        {/* Eksik sonuç başta söylenir: uzun bir sayfanın sonundaki liste gözden kaçabilir. */}
        {unreadable.length > 0 && (
          <p className="note note--warn" role="note">
            <strong className="note-label">Eksik</strong>
            <span>
              {unreadable.length} iddianın sonucu okunamadı; bu iddialar aşağıda ayrıca listelenir.
            </span>
          </p>
        )}

        {claims.length > 0 && <ul className="result-overview" aria-label="Sonuç özeti">
          {VERDICT_ORDER.map((verdict) => {
            const count = claims.filter((claim) => claim.verdict === verdict).length;
            const meta = VERDICT_META[verdict];
            return count > 0 ? <li key={verdict} className={`tone-${meta.tone}`}><Icon name={meta.icon} /><strong className="tnum">{count}</strong><span>{meta.label}</span></li> : null;
          })}
        </ul>}
        {claims.length > 1 && <ClaimList claims={claims} open={listOpen} onOpenChange={setListOpen} onSelect={(id) => navigateTo(claimAnchor(id))} />}
        <LegendDisclosure />
      </div>

      {claims.length === 0 ? (
        unfinished.length > 0 ? (
          <div className="state">
            <p>İddialar bulundu ama hiçbiri için sonuç üretilemedi.</p>
            <p className="muted">Biraz sonra yeniden deneyin ya da metni kısaltın.</p>
          </div>
        ) : (
          <div className="state">
            <p>Gönderdiğiniz içerikte kaynaklarla kontrol edilebilecek somut bir iddia bulunamadı.</p>
            <p className="muted">Tarih, sayı, kişi ya da olay içeren bir cümleyle yeniden deneyin.</p>
          </div>
        )
      ) : (
        <div className="claims">
          {claims.map((c, i) => (
            <ClaimItem key={c.id} claim={c} index={i} total={claims.length} sample={sample} showcase={showcase}
              onBackToList={() => navigateTo(CLAIM_LIST_ID)}
              expanded={expanded.has(c.id)} onExpandedChange={(open) => setExpanded((current) => {
                const next = new Set(current);
                if (open) next.add(c.id); else next.delete(c.id);
                return next;
              })} />
          ))}
        </div>
      )}

      {unfinished.length > 0 && (
        <section className="unverifiable" aria-labelledby="unfinished-title">
          <h3 id="unfinished-title" className="t-h4">
            İncelenemeyen iddialar ({unfinished.length})
          </h3>
          <p className="muted t-meta">
            Bu iddialar için sonuç üretilemedi. Bu, doğru ya da yanlış oldukları anlamına gelmez; yeniden deneyebilirsiniz.
          </p>
          <ul>
            {unfinished.map((u, i) => (
              <li key={i}>
                {u.text} <span className="muted">({UNFINISHED_REASON[u.reason]})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {unreadable.length > 0 && (
        <section className="unverifiable" aria-labelledby="unreadable-title">
          <h3 id="unreadable-title" className="t-h4">
            Sonucu gösterilemeyen iddialar ({unreadable.length})
          </h3>
          <p className="muted t-meta">
            Servisten gelen sonuç tanınmadı. Bu, iddiaların doğru ya da yanlış olduğu anlamına gelmez; yeniden
            deneyebilirsiniz.
          </p>
          <ul>
            {unreadable.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}

      {unverifiable.length > 0 && (
        <section className="unverifiable" aria-labelledby="unverifiable-title">
          <h3 id="unverifiable-title" className="t-h4">
            İncelenmeyen ifadeler ({unverifiable.length})
          </h3>
          <p className="muted t-meta">Bu incelemede kaynaklarla değerlendirilmeyen görüş, tahmin veya yeterince somut olmayan ifadeler.</p>
          <ul>
            {unverifiable.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}
      <section className="report-scope" aria-labelledby="scope-title"><h3 id="scope-title" className="t-h4">Kapsam ve sınırlamalar</h3><p className="muted">{result.report?.scope ?? "Bu rapor yalnızca listelenen iddia ve kaynakları gösterir; metnin tamamı için tek bir doğruluk hükmü değildir. Servis, araştırmanın kapsamını paylaşmadı."}</p></section>
      <ReportTools result={result} input={input} sample={sample} showcase={showcase} />

      <div className="result-foot">
        {!showcase && (
          <p className="muted t-meta">
            {claims.length > 0
              ? "Bu sonuç otomatik bir ön değerlendirmedir. Karar vermeden önce yukarıdaki kaynakları kendiniz de kontrol edin."
              : "Bu sonuç otomatik bir ön değerlendirmedir."}
            {" "}Sonuç otomatik kaydedilmez; sayfa yenilenmeden kopyalayabilirsiniz.
          </p>
        )}
        <button type="button" className="btn btn-quiet" onClick={onReset}>
          {showcase ? "Örneği kapat" : "Yeni bir içerik incele"}
        </button>
      </div>
    </section>
  );
}
