import { VerdictSummary } from "./VerdictSummary";
import { CLAIM_LIST_ID, claimAnchor } from "@/lib/format";
import type { Claim } from "@/lib/types";

/**
 * Birden fazla iddia varken: her iddia için kısa özet. Ayrıntıya bağlantı verir.
 * Uzun iddia metni burada üç satırda kesilir (tam metin ayrıntıda durur); çok iddialı sonuçta liste ekranlarca uzamasın.
 */
export function ClaimList({ claims }: { claims: Claim[] }) {
  return (
    <nav id={CLAIM_LIST_ID} className="claim-nav" aria-label="İncelenen iddialar">
      <ol className="claim-index">
        {claims.map((c, i) => (
          <li key={c.id}>
            <span className="ci-num">{i + 1}</span>
            <div>
              <a className="ci-link" href={`#${claimAnchor(c.id)}`}>
                <span className="ci-text">{c.text}</span>
              </a>
              <p className="ci-meta">
                <VerdictSummary verdict={c.verdict} variant="inline" />
                <span>{c.sources.length === 0 ? "Kaynak yok" : `${c.sources.length} kaynak`}</span>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </nav>
  );
}
