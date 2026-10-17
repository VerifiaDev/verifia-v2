import type { ReactNode } from "react";
import { isCitationGroup, splitIds } from "@/lib/citations";
import { sourceAnchor } from "@/lib/format";
import type { Source } from "@/lib/types";

/**
 * Açıklamadaki [kaynak_1] gibi atıfları, aşağıdaki kanıt listesine giden numaralı bağlantılara
 * çevirir ([1], [2]). Eşleşmeyen atıfları açıkça belirtir; aynı gruptaki geçerli atıfları korur.
 * Atıf olmayan köşeli parantezli metin ([2023], [...]) olduğu gibi gösterilir (bkz. lib/citations.ts).
 */
export function Explanation({ text, sources, claimId }: { text: string; sources: Source[]; claimId: string }) {
  const parts = text.split(/(\[[^\]]+\])/g);

  return (
    <p className="explanation">
      {parts.map((part, i): ReactNode => {
        const m = /^\[([^\]]+)\]$/.exec(part);
        if (!m || !isCitationGroup(m[1], sources)) return part;

        const numbers = splitIds(m[1]).map((id) => sources.findIndex((s) => s.id === id) + 1);

        return (
          <span key={i}>
            [
            {numbers.map((n, j) => (
              <span key={j}>
                {j > 0 && ", "}
                {n === 0 ? <span className="missing-citation">Kaynak eşleşmesi bulunamadı</span> : <a className="cite" href={`#${sourceAnchor(claimId, n)}`}>
                  {n}
                  <span className="sr-only"> numaralı kaynağa git</span>
                </a>}
              </span>
            ))}
            ]
          </span>
        );
      })}
    </p>
  );
}
