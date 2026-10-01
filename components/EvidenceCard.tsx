import { sentencesCiting } from "@/lib/citations";
import { formatDate, hostOf, isSafeHttpUrl, sourceAnchor } from "@/lib/format";
import type { Source } from "@/lib/types";

const EXCERPT_MAX = 360;

interface Props {
  source: Source;
  number: number;
  claimId: string;
  /** "Açıklamada bu kaynağa dayanılan ifade" için kullanılır. */
  explanation: string;
}

/**
 * Bir kanıt: kaynak adı, yayın tarihi, alan adı, alıntı, açıklamadaki karşılığı ve bağlantı.
 * Kaynak adı alan adına indirgenmez; ad yoksa alan adı ad yerine gösterilir.
 */
export function EvidenceCard({ source, number, claimId, explanation }: Props) {
  const host = hostOf(source.url);
  const date = formatDate(source.publishedAt);
  const safe = isSafeHttpUrl(source.url);
  const why = sentencesCiting(explanation, source.id);
  const excerpt =
    source.excerpt && source.excerpt.length > EXCERPT_MAX
      ? `${source.excerpt.slice(0, EXCERPT_MAX).trimEnd()}…`
      : source.excerpt;

  return (
    <li id={sourceAnchor(claimId, number)} className="evidence">
      <div className="evidence-meta">
        <p>
          <span className="evidence-num">[{number}]</span>
          <span className="source-name">{source.name ?? host}</span>
        </p>
        <p className="t-source muted">
          {date && source.publishedAt ? <time dateTime={source.publishedAt}>{date}</time> : "Yayın tarihi belirtilmemiş"}
        </p>
        {source.name && <p className="source-domain">{host}</p>}
      </div>

      <div className="evidence-body">
        {excerpt ? (
          <blockquote className="evidence-excerpt">“{excerpt}”</blockquote>
        ) : (
          <p className="muted t-source">Bu kaynak için alıntı gelmedi.</p>
        )}
        {why.length > 0 && (
          <p className="evidence-why">
            <strong>Açıklamada bu kaynağa dayanılan ifade:</strong> {why.join(" ")}
          </p>
        )}
        <p className="evidence-link">
          {safe ? (
            <a href={source.url} target="_blank" rel="noopener noreferrer">
              Kaynağı görüntüle <span aria-hidden="true">→</span>
              <span className="sr-only"> ({host}), yeni sekmede açılır</span>
            </a>
          ) : (
            <span className="muted">Bağlantı geçersiz, kaynak açılamıyor.</span>
          )}
        </p>
      </div>
    </li>
  );
}
