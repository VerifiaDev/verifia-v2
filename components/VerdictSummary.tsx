import type { CSSProperties } from "react";
import { VERDICT_META, formatPercent } from "@/lib/format";
import type { Verdict } from "@/lib/types";

interface Props {
  verdict: Verdict;
  /** "block": etiket + anlamı. "inline": yalnızca simge + etiket (listeler için). */
  variant?: "block" | "inline";
  /** Modelin güven puanı (0-1). Yoksa hiçbir şey gösterilmez. */
  confidence?: number | null;
}

/** Renk bilginin parçasıdır ama tek başına taşıyıcı değildir: her sonucun farklı simgesi ve yazısı var. */
export function VerdictSummary({ verdict, variant = "block", confidence = null }: Props) {
  const m = VERDICT_META[verdict];

  if (variant === "inline") {
    return (
      <span className={`verdict-inline tone-${m.tone}`}>
        <span className="verdict-symbol" aria-hidden="true">
          {m.symbol}
        </span>
        {m.label}
      </span>
    );
  }

  return (
    <div className={`verdict tone-${m.tone}`}>
      <p className="verdict-label">
        <span className="verdict-symbol" aria-hidden="true">
          {m.symbol}
        </span>
        {m.label}
      </p>
      <p className="verdict-meaning">{m.meaning}</p>
      {confidence !== null && (
        <div className="verdict-confidence">
          <p>
            Modelin güven puanı: <strong>{formatPercent(confidence)}</strong>. Bu, sonucun doğru olma olasılığı değil,
            modelin kendi tahminidir; asıl dayanak aşağıdaki kaynaklardır.
          </p>
          <div
            className="confidence-meter"
            role="meter"
            aria-label="Modelin güven puanı"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(Math.max(0, Math.min(1, confidence)) * 100)}
            style={{ "--confidence": Math.max(0, Math.min(1, confidence)) } as CSSProperties}
          >
            <span />
          </div>
        </div>
      )}
    </div>
  );
}
