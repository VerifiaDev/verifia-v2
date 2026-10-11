"use client";

import { useEffect, useRef, useState } from "react";
import type { CheckResult } from "@/lib/types";
import { reportText } from "@/lib/report";
import { sampleReportUrl } from "@/lib/config";
import { Icon } from "./Icon";

export function ReportTools({ result, input, sample = false, showcase = false }: {
  result: CheckResult; input?: string; sample?: boolean; showcase?: boolean;
}) {
  const [notice, setNotice] = useState({ text: "", sequence: 0 });
  const [fallback, setFallback] = useState("");
  const [copying, setCopying] = useState(false);
  const fallbackRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!notice.text) return;
    const timer = setTimeout(() => setNotice((current) => ({ ...current, text: "" })), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => { if (fallback) fallbackRef.current?.focus(); }, [fallback]);

  useEffect(() => {
    // Ctrl+P dahil: kapalı iddialar ve tam pasajlar da çıktıya girer.
    let closed: HTMLDetailsElement[] = [];
    const prepare = () => {
      if (closed.length) return;
      closed = Array.from(document.querySelectorAll<HTMLDetailsElement>("#report details:not([open])"));
      closed.forEach((item) => { item.open = true; });
    };
    const restore = () => {
      closed.forEach((item) => { item.open = false; });
      closed = [];
    };
    window.addEventListener("beforeprint", prepare);
    window.addEventListener("afterprint", restore);
    return () => {
      window.removeEventListener("beforeprint", prepare);
      window.removeEventListener("afterprint", restore);
      restore();
    };
  }, []);

  async function copy(text: string, success: string) {
    setCopying(true);
    try {
      await navigator.clipboard.writeText(text);
      setFallback("");
      setNotice((current) => ({ text: success, sequence: current.sequence + 1 }));
    } catch {
      setFallback(text);
      setNotice((current) => ({ text: "Otomatik kopyalanamadı. Seçili metni elle kopyalayabilirsiniz.", sequence: current.sequence + 1 }));
    } finally { setCopying(false); }
  }

  return (
    <details className="more report-tools no-print">
      <summary>Raporu kopyala veya yazdır <Icon name="chevron" className="chevron" /></summary>
      <div className="report-actions" aria-label="Rapor araçları">
        <button type="button" className="btn btn-quiet" disabled={copying} onClick={() => void copy(reportText(result, input, sample), "Rapor kaynaklarıyla birlikte kopyalandı.")}>Raporu kopyala</button>
        <button type="button" className="btn btn-quiet" onClick={() => window.print()}>Yazdır / PDF kaydet</button>
        {/* Bağlantı, raporun kendi sayfasını gösterir: JavaScript olmadan ve bağlantı önizlemelerinde de açılır. */}
        {showcase && <button type="button" className="btn btn-quiet" disabled={copying} onClick={() => {
          void copy(sampleReportUrl(window.location.origin), "Örnek raporun bağlantısı kopyalandı.");
        }}>Örnek bağlantısını kopyala</button>}
      </div>
      <p role="status" aria-atomic="true" className="t-meta muted"><span key={notice.sequence}>{notice.text}</span></p>
      {fallback && <label className="copy-fallback">Kopyalanacak metin<textarea ref={fallbackRef} readOnly className="field" rows={6} value={fallback} onFocus={(event) => event.currentTarget.select()} /></label>}
    </details>
  );
}
