import { Icon } from "./Icon";
import { formatDate, hostOf, isSafeHttpUrl, sourceAnchor } from "@/lib/format";
import type { Source } from "@/lib/types";

const EXCERPT_MAX = 360;

interface Props {
  source: Source;
  number: number;
  claimId: string;
}

/**
 * Bir kanıt: kaynak, alıntı ve bağlantı.
 * Kaynağın adı ya da yayın tarihi varsa bunlar solda ayrı bir sütunda durur. İkisi de yoksa (gerçek
 * backend şu an yalnızca adres ve alıntı gönderiyor) satır tek sütundur: alan adı üstte, alıntı altında.
 * Gelmeyen bilgi için "belirtilmemiş" yazılmaz; yalnızca gelen gösterilir.
 */
export function EvidenceCard({ source, number, claimId }: Props) {
  const host = hostOf(source.url);
  const date = formatDate(source.publishedAt);
  const safe = isSafeHttpUrl(source.url);
  const hasMeta = Boolean(source.name) || Boolean(date);
  const excerpt =
    source.excerpt && source.excerpt.length > EXCERPT_MAX
      ? `${source.excerpt.slice(0, EXCERPT_MAX).trimEnd()}…`
      : source.excerpt;

  return (
    <li id={sourceAnchor(claimId, number)} className={hasMeta ? "evidence" : "evidence evidence--plain"}>
      <div className="evidence-meta">
        <p>
          <span className="evidence-num">[{number}]</span>
          <span className="source-name">{source.name ?? host}</span>
        </p>
        {date && source.publishedAt && (
          <p className="evidence-date">
            <time dateTime={source.publishedAt}>{date}</time>
          </p>
        )}
        {source.name && <p className="source-domain">{host}</p>}
      </div>

      <div className="evidence-body">
        {excerpt ? (
          <blockquote className="evidence-excerpt">“{excerpt}”</blockquote>
        ) : (
          <p className="muted t-meta">Bu kaynak için alıntı gelmedi.</p>
        )}
        <p className="evidence-link">
          {safe ? (
            <a href={source.url} target="_blank" rel="noopener noreferrer">
              Kaynağı görüntüle
              <Icon name="external" />
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
