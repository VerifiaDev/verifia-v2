import type { ReactNode } from "react";
import { splitIds } from "@/lib/citations";
import { sourceAnchor } from "@/lib/format";
import type { Source } from "@/lib/types";

/**
 * Açıklamadaki [kaynak_1] gibi atıfları, aşağıdaki kanıt listesine giden numaralı bağlantılara
 * çevirir ([1], [2]). Listede olmayan atıflar düz metin kalır: kaynak uydurulmaz.
 */
export function Explanation({ text, sources, claimId }: { text: string; sources: Source[]; claimId: string }) {
  const parts = text.split(/(\[[^\]]+\])/g);

  return (
    <p className="explanation">
      {parts.map((part, i): ReactNode => {
        const m = /^\[([^\]]+)\]$/.exec(part);
        if (!m) return part;

        const numbers = splitIds(m[1]).map((id) => sources.findIndex((s) => s.id === id) + 1);
        if (numbers.length === 0 || numbers.some((n) => n === 0)) return part;

        return (
          <span key={i}>
            [
            {numbers.map((n, j) => (
              <span key={n}>
                {j > 0 && ", "}
                <a className="cite" href={`#${sourceAnchor(claimId, n)}`}>
                  {n}
                  <span className="sr-only"> numaralı kaynağa git</span>
                </a>
              </span>
            ))}
            ]
          </span>
        );
      })}
    </p>
  );
}
