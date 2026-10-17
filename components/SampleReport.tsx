"use client";

import { ResultView } from "./ResultView";
import { curatedSample } from "@/lib/sample-report";

/**
 * Hazır örnek raporun kendi sayfasındaki görünümü (app/ornek/apollo-11). Rapor sunucuda çizilir; JavaScript
 * yalnızca açılır bölümler, kopyalama ve yazdırma için gerekir. "Örneği kapat" ana sayfaya götürür.
 */
export function SampleReport() {
  // Close the standalone report with a fresh page, clearing its transient state.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  return <ResultView result={curatedSample()} sample showcase onReset={() => window.location.assign("/")} />;
}
