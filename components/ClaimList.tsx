import { VerdictSummary } from "./VerdictSummary";
import { claimAnchor } from "@/lib/format";
import type { Claim } from "@/lib/types";

/** Birden fazla iddia varken: her iddia için tek satır özet. Ayrıntıya bağlantı verir. */
export function ClaimList({ claims }: { claims: Claim[] }) {
  return (
    <nav aria-label="İncelenen iddialar">
      <ol className="claim-index">
        {claims.map((c, i) => (
          <li key={c.id}>
            <span className="ci-num">{i + 1}</span>
            <div>
              <a className="ci-link" href={`#${claimAnchor(c.id)}`}>
                {c.text}
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
