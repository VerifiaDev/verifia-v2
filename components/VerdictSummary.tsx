import { Icon } from "./Icon";
import { VERDICT_META, formatPercent } from "@/lib/format";
import type { Verdict } from "@/lib/types";

interface Props {
  verdict: Verdict;
  /** "block": sonuç kutusu (etiket + varsa uyarı). "inline": yalnızca simge + etiket (listeler için). */
  variant?: "block" | "inline" | "detail";
  /** Modelin güven puanı (0-1). Yoksa hiçbir şey gösterilmez. */
  confidence?: number | null;
}

/**
 * Renk bilginin parçasıdır ama tek başına taşıyıcı değildir: her sonucun farklı simgesi ve yazısı var.
 * Sonuç kutusunda etiketin anlamı yinelenmez ("Sonuç türleri" listesinde yazar); yalnızca yanlış
 * okunmayı önleyen uyarı (örn. "bu, iddianın yanlış olduğu anlamına gelmez") gösterilir.
 */
export function VerdictSummary({ verdict, variant = "block", confidence = null }: Props) {
  const m = VERDICT_META[verdict];

  if (variant === "inline") {
    return (
      <span className={`verdict-inline tone-${m.tone}`}>
        <Icon name={m.icon} />
        {m.label}
      </span>
    );
  }

  if (variant === "detail" && !m.caveat && confidence === null) return null;
  return (
    <div className={`verdict tone-${m.tone}`}>
      {variant !== "detail" && <p className="verdict-label">
        <Icon name={m.icon} />
        {m.label}
      </p>}
      {m.caveat && <p className="verdict-caveat">{m.caveat}</p>}
      {confidence !== null && (
        <p className="verdict-confidence">
          Modelin güven puanı: <strong>{formatPercent(confidence)}</strong>. Bu, sonucun doğru olma olasılığı değil,
          modelin kendi tahminidir; asıl dayanak aşağıdaki kaynaklardır.
        </p>
      )}
    </div>
  );
}
