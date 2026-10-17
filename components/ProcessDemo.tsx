"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import { Icon } from "./Icon";
import { VERDICT_META } from "@/lib/format";
import type { Verdict } from "@/lib/types";

/**
 * "Nasıl çalışır?" bölümündeki kısa canlandırma: yapıştırılan bir metnin iddialara ayrılması, her iddiaya
 * kaynak bulunması ve sonuç etiketinin gelmesi. İçerik uydurma değildir; sitedeki kaynaklı Apollo 11 örnek
 * raporunun (lib/sample-report.ts, /ornek/apollo-11) kısaltılmış hâlidir.
 *
 * Hareket kuralları:
 * - Bölüm ekranda yarısı görünür olduğunda BİR KEZ oynar (yaklaşık 4,8 sn; 5 sn'yi geçmez, durdurma düğmesi
 *   gerektirmez). Döngü yoktur. "Yeniden oynat" ile kullanıcı tekrar izleyebilir.
 * - Cihaz "hareketi azalt" diyorsa ya da JavaScript yoksa son hâl doğrudan gösterilir; içerik her zaman
 *   sayfadadır, hareket yalnızca görünürlüğü sırayla açar (ekran okuyucu son hâli okur).
 * - Yalnızca opaklık, küçük bir kayma ve alt çizgi rengi değişir; yeni renk ya da yazı tipi yoktur.
 */

const SENTENCES: { text: string; claim: boolean }[] = [
  { text: "Apollo 11, 20 Temmuz 1969'da Ay'a indi.", claim: true },
  { text: "Görevdeki üç astronot da Ay yüzeyinde yürüdü.", claim: true },
  { text: "Görevden sonra Türkiye'de astronomiye ilgi iki katına çıktı.", claim: true },
  { text: "Bu, insanlığın en etkileyici yolculuğuydu.", claim: false },
];

const ROWS: { claim: string; sources: string; verdict: Verdict }[] = [
  { claim: SENTENCES[0].text, sources: "NASA, 2 kaynak", verdict: "SUPPORTED" },
  { claim: SENTENCES[1].text, sources: "NASA, 1 kaynak", verdict: "REFUTED" },
  { claim: SENTENCES[2].text, sources: "Kaynak bulunamadı", verdict: "NOT_ENOUGH_EVIDENCE" },
];

/** idle: son hâl (sunucu çıktısı, hareket azaltma). armed: oynamayı bekliyor (parçalar gizli). play: oynuyor. */
type Phase = "idle" | "armed" | "play";

/** Son öğenin bitişi (ms): en geç gelen sonuç etiketi. CSS'teki gecikmelerle aynı tutulmalı. */
const DURATION_MS = 4800;

function subscribeMotion(notify: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", notify);
  return () => mq.removeEventListener("change", notify);
}
const motionAllowed = () => typeof IntersectionObserver !== "undefined" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const serverMotionAllowed = () => false;

export function ProcessDemo() {
  const ref = useRef<HTMLElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const canReplay = useSyncExternalStore(subscribeMotion, motionAllowed, serverMotionAllowed);

  useEffect(() => {
    const el = ref.current;
    if (!el || !canReplay) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          setPhase("play");
        }
      },
      // A tall figure may never be 50% visible on a short phone screen.
      { threshold: 0.1 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [canReplay]);

  useEffect(() => {
    if (phase !== "play") return;
    const t = setTimeout(() => setPhase("idle"), DURATION_MS + 200);
    return () => clearTimeout(t);
  }, [phase]);

  function replay() {
    setPhase("armed");
    // Bir sonraki karede oynat: tarayıcı gizli başlangıç hâlini çizsin ki canlandırma baştan başlasın.
    requestAnimationFrame(() => requestAnimationFrame(() => setPhase("play")));
  }

  return (
    <figure ref={ref} className="demo" data-phase={canReplay ? phase : "idle"} aria-labelledby="demo-caption">
      <div className="demo-input">
        <p className="demo-label">Yapıştırılan metin</p>
        <p className="demo-text">
          {SENTENCES.map((s, i) => (
            <span key={s.text} className={s.claim ? "demo-s demo-s--claim" : "demo-s demo-s--opinion"} style={{ "--i": i } as CSSProperties}>
              {s.text}{" "}
            </span>
          ))}
        </p>
      </div>

      <ol className="demo-rows">
        {ROWS.map((r, i) => {
          const m = VERDICT_META[r.verdict];
          return (
            <li key={r.claim} className="demo-row" style={{ "--i": i } as CSSProperties}>
              <span className="demo-claim">{r.claim}</span>
              <span className="demo-meta">
                <span className="demo-src">{r.sources}</span>
                <span className={`demo-verdict verdict-inline tone-${m.tone}`}>
                  <Icon name={m.icon} />
                  {m.label}
                </span>
              </span>
            </li>
          );
        })}
        <li className="demo-row demo-row--opinion" style={{ "--i": 3 } as CSSProperties}>
          <span className="demo-claim">{SENTENCES[3].text}</span>
          <span className="demo-meta">
            <span className="demo-src">Görüş, incelenmez</span>
          </span>
        </li>
      </ol>

      <figcaption id="demo-caption" className="demo-caption">
        <span>
          Örnek: kaynaklı Apollo 11 raporunun kısaltılmış hâli. <a href="/ornek/apollo-11">Raporun tamamını açın</a>
        </span>
        {canReplay && (
          <button type="button" className="btn btn-quiet demo-replay" onClick={replay} disabled={phase === "play"}>
            Yeniden oynat
          </button>
        )}
      </figcaption>
    </figure>
  );
}
