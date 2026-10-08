import { VerdictSummary } from "./VerdictSummary";
import { VERDICT_META, VERDICT_ORDER } from "@/lib/format";
import { Icon } from "./Icon";

export function LegendDisclosure() {
  return <details className="more legend-disclosure no-print">
    <summary>Sonuç türleri ne anlama gelir?<Icon name="chevron" className="chevron" /></summary>
    <Legend />
  </details>;
}

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
