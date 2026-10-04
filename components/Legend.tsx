import { VerdictSummary } from "./VerdictSummary";
import { VERDICT_META, VERDICT_ORDER } from "@/lib/format";

/**
 * Sonuç türlerinin açıklaması. Geniş ekranda yan sütunda sürekli görünür; dar ekranda kapalı bir
 * açılır satırın içindedir (bkz. app/page.tsx). İki yerde de aynı içerik kullanılsın diye ayrı bileşendir.
 */
export function Legend() {
  return (
    <>
      <dl className="legend">
        {VERDICT_ORDER.map((v) => (
          <div key={v}>
            {/* Sonuçlardaki simgenin aynısı: açıklama ile sonuç aynı görünsün. */}
            <dt>
              <VerdictSummary verdict={v} variant="inline" />
            </dt>
            <dd>{VERDICT_META[v].meaning}</dd>
          </div>
        ))}
      </dl>
      <p className="legend-note">
        Bir sonuç kesin hüküm değildir. Kaynağı, bağlamı ve kanıtın sınırlarını birlikte okuyun.
      </p>
    </>
  );
}
