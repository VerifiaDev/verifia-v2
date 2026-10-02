import { EvidenceCard } from "./EvidenceCard";
import { Explanation } from "./Explanation";
import { VerdictSummary } from "./VerdictSummary";
import { citedNumbers } from "@/lib/citations";
import { claimAnchor } from "@/lib/format";
import type { Claim } from "@/lib/types";

interface Props {
  claim: Claim;
  index: number;
  total: number;
  /** Örnek (mock) veri: sonuç gerçek bir inceleme değildir; her iddiada açıkça belirtilir. */
  sample?: boolean;
}

const FALLBACK_KEY_COUNT = 2;

/**
 * Bir iddia ve sırasıyla: iddia → sonuç → açıklama → öne çıkan kanıtlar → diğer kaynaklar.
 * "Öne çıkan" kanıt, açıklamanın atıf yaptığı kaynaklardır; atıf yoksa ilk ikisi.
 */
export function ClaimItem({ claim, index, total, sample = false }: Props) {
  const { sources } = claim;
  const cited = citedNumbers(claim.explanation, sources);
  const keyNumbers = cited.length > 0 ? cited : sources.slice(0, FALLBACK_KEY_COUNT).map((_, i) => i + 1);
  const restNumbers = sources.map((_, i) => i + 1).filter((n) => !keyNumbers.includes(n));
  const titleId = `${claimAnchor(claim.id)}-title`;

  const card = (n: number) => (
    <EvidenceCard key={n} source={sources[n - 1]} number={n} claimId={claim.id} explanation={claim.explanation} />
  );

  return (
    <article
      id={claimAnchor(claim.id)}
      className={sample ? "claim-item claim-item--sample" : "claim-item"}
      aria-labelledby={titleId}
    >
      {sample && (
        <p className="sample-tag">
          <strong>Örnek veri.</strong> Gönderdiğiniz içerikle ilgisi yok; gerçek bir inceleme değil.
        </p>
      )}
      {total > 1 && (
        <p className="claim-kicker">
          İddia {index + 1} / {total}
        </p>
      )}
      <h3 id={titleId} className="t-h3">
        {claim.text}
      </h3>

      {/* Örnek veride güven puanı gösterilmez: uydurma bir yüzde, ekran görüntüsünde en kolay gerçek sanılan öğedir. */}
      <VerdictSummary verdict={claim.verdict} confidence={sample ? null : claim.confidence} />

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
            <p>
              Bu iddia için gösterilebilecek bir kaynak yok. Bu, iddianın yanlış olduğu anlamına gelmez; doğrulayacak ya
              da çürütecek güvenilir kaynak bulunamadı.
            </p>
            <p className="muted">
              Daha somut bir cümleyle yeniden deneyebilir ya da konuyla ilgili resmî kaynaklara doğrudan bakabilirsiniz.
            </p>
          </div>
        ) : (
          <>
            <h4 className="t-h4">Dayandığımız kanıtlar ({keyNumbers.length})</h4>
            <ol className="evidence-list">{keyNumbers.map(card)}</ol>

            {restNumbers.length > 0 && (
              <details className="more">
                <summary>Diğer kaynaklar ({restNumbers.length})</summary>
                <ol className="evidence-list">{restNumbers.map(card)}</ol>
              </details>
            )}
          </>
        )}
      </div>
    </article>
  );
}
