import { EvidenceCard } from "./EvidenceCard";
import { Explanation } from "./Explanation";
import { Icon } from "./Icon";
import { VerdictSummary } from "./VerdictSummary";
import { citedNumbers } from "@/lib/citations";
import { CLAIM_LIST_ID, claimAnchor } from "@/lib/format";
import type { Claim } from "@/lib/types";

interface Props {
  claim: Claim;
  index: number;
  total: number;
  /** Örnek (mock) veri: sonuç gerçek bir inceleme değildir; her iddiada açıkça belirtilir. */
  sample?: boolean;
  /** Sabit örnek (servis bağlı değilken gösterilen): kullanıcı bir şey göndermedi; etiket metni buna göre değişir. */
  showcase?: boolean;
  expanded?: boolean;
  onExpandedChange?: (open: boolean) => void;
  onBackToList?: () => void;
}

const FALLBACK_KEY_COUNT = 2;

/**
 * Bir iddia ve sırasıyla: iddia → sonuç → açıklama → öne çıkan kanıtlar → diğer kaynaklar.
 * "Dayandığımız kanıtlar" yalnızca açıklamanın atıf yaptığı kaynaklar için söylenir. Atıf yoksa hangi
 * kaynağa dayanıldığı bilinmez: ilk ikisi yine açık gösterilir ama başlık yalnızca "Bulunan kaynaklar" der.
 */
export function ClaimItem({ claim, index, total, sample = false, showcase = false, expanded = true, onExpandedChange, onBackToList }: Props) {
  const { sources } = claim;
  const cited = citedNumbers(claim.explanation, sources);
  const hasCitations = cited.length > 0;
  const keyNumbers = hasCitations ? cited : sources.slice(0, FALLBACK_KEY_COUNT).map((_, i) => i + 1);
  const restNumbers = sources.map((_, i) => i + 1).filter((n) => !keyNumbers.includes(n));
  const titleId = `${claimAnchor(claim.id)}-title`;

  const card = (n: number) => (
    <EvidenceCard key={n} source={sources[n - 1]} number={n} claimId={claim.id} />
  );

  return (
    <article
      id={claimAnchor(claim.id)}
      className={sample ? "claim-item claim-item--sample" : "claim-item"}
      aria-labelledby={titleId}
    >
      <details className="claim-disclosure" open={expanded} onToggle={(event) => {
        if (event.currentTarget.open !== expanded) onExpandedChange?.(event.currentTarget.open);
      }}>
        <summary className="claim-summary">
          <span className="claim-summary-text">
            <span className="claim-summary-kicker">İDDİA {index + 1} / {total}{sample && <strong className="sample-badge">Örnek veri</strong>}</span>
            <span id={titleId} className="t-h3" role="heading" aria-level={3}>{claim.text}</span>
            <span className="ci-meta"><VerdictSummary verdict={claim.verdict} variant="inline" /><span>{sources.length === 0 ? "Kaynak yok" : `${sources.length} kaynak`}</span></span>
            {((claim.verdict === "SUPPORTED" || claim.verdict === "REFUTED") && !sources.length || !claim.explanation.trim()) && <span className="claim-evidence-warning">Kanıt bilgisi eksik: {sources.length === 0 ? "bu hükmü denetlemek için kaynak sunulmadı." : "sonucun gerekçesi paylaşılmadı."}</span>}
          </span>
          <Icon name="chevron" className="chevron" />
        </summary>
        <div className="claim-detail">
      {sample && (
        <p className="sample-tag">
          {showcase
            ? "Önceden hazırlanmış değerlendirme; canlı analiz değil."
            : "Gönderdiğiniz içerikle ilgisi yok; gerçek bir inceleme değil."}
        </p>
      )}
      {total > 1 && (
        <p className="claim-kicker">
          {/* Uzun sonuçta (çok iddia, çok kaynak) okuyan listeye geri dönebilsin. */}
          <a className="claim-back" href={`#${CLAIM_LIST_ID}`} onClick={(e) => { if (onBackToList) { e.preventDefault(); onBackToList(); } }}>
            İddia listesine dön
          </a>
        </p>
      )}

      {/* Örnek veride güven puanı gösterilmez: uydurma bir yüzde, ekran görüntüsünde en kolay gerçek sanılan öğedir. */}
      <VerdictSummary verdict={claim.verdict} confidence={sample ? null : claim.confidence} variant="detail" />

      <div className="block">
        <h4 className="t-h4">Neden?</h4>
        {claim.explanation ? (
          <Explanation text={claim.explanation} sources={sources} claimId={claim.id} />
        ) : (
          <p className="muted">Bu sonuç için açıklama gelmedi.</p>
        )}
      </div>

      <div className="evidence-area">
        {sources.length === 0 ? (
          <div className="notice">
            <h4 className="t-h4">Kaynak bulunamadı</h4>
            <p>Bu iddia için gösterilebilecek bir kaynak yok.</p>
            <p className="muted">
              Daha somut bir cümleyle yeniden deneyebilir ya da konuyla ilgili resmî kaynaklara doğrudan bakabilirsiniz.
            </p>
          </div>
        ) : (
          <>
            <h4 className="t-h4">
              {hasCitations ? `Dayandığımız kanıtlar (${keyNumbers.length})` : `Bulunan kaynaklar (${sources.length})`}
            </h4>
            {!hasCitations && (
              <p className="evidence-note muted t-meta">
                Açıklamanın hangi kaynaklara dayandığı belirtilmedi; aşağıdakiler bu iddia için bulunan kaynaklardır.
              </p>
            )}
            <ol className="evidence-list">{keyNumbers.map(card)}</ol>

            {restNumbers.length > 0 && (
              <details className="more">
                <summary>
                  Diğer kaynaklar ({restNumbers.length})
                  <Icon name="chevron" className="chevron" />
                </summary>
                <ol className="evidence-list">{restNumbers.map(card)}</ol>
              </details>
            )}
          </>
        )}
      </div>
        </div>
      </details>
    </article>
  );
}
