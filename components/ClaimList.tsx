import { VerdictSummary } from "./VerdictSummary";
import { CLAIM_LIST_ID, claimAnchor } from "@/lib/format";
import type { Claim } from "@/lib/types";
import { Icon } from "./Icon";

/**
 * Birden fazla iddia varken: her iddia için kısa özet. Ayrıntıya bağlantı verir.
 * Uzun iddia metni burada üç satırda kesilir (tam metin ayrıntıda durur); çok iddialı sonuçta liste ekranlarca uzamasın.
 */
export function ClaimList({ claims, onSelect, open = false, onOpenChange }: { claims: Claim[]; onSelect?: (id: string) => void; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  return (
    <nav id={CLAIM_LIST_ID} className="claim-nav" aria-label="İncelenen iddialar">
      <details className="more claim-jump" open={open} onToggle={(e) => { if (e.currentTarget.open !== open) onOpenChange?.(e.currentTarget.open); }}>
        <summary>İddialara hızlı erişim <Icon name="chevron" className="chevron" /></summary>
      <ol className="claim-index">
        {claims.map((c, i) => (
          <li key={c.id}>
            <span className="ci-num">{i + 1}</span>
            <div>
              <a className="ci-link" href={`#${claimAnchor(c.id)}`} onClick={(e) => { if (onSelect) { e.preventDefault(); onSelect(c.id); } }}>
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
      </details>
    </nav>
  );
}
