"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";

const KEY = "verify-theme";
/** globals.css'teki --paper değerleri; telefon tarayıcısının üst çubuk rengi için. */
const BAR_COLOR = { light: "#f6f7f5", dark: "#11151a" } as const;

/** Elle seçilmiş tema varsa tüm theme-color etiketlerini ona sabitler (sistem tercihine bağlı olanlar yanlış renk verir). */
function applyBarColor(theme: "light" | "dark") {
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
    m.removeAttribute("media");
    m.setAttribute("content", BAR_COLOR[theme]);
  });
}

/** Geçerli görünüm: elle seçilmişse o, değilse sistem tercihi. */
function currentIsDark(): boolean {
  const set = document.documentElement.dataset.theme;
  if (set === "dark") return true;
  if (set === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * Gece modu düğmesi: her genişlikte çerçevesiz bir simge düğmesi (menüden ağır durmasın); adı ekran
 * okuyucuya okunur ve üzerine gelince ipucu olarak görünür. Tercih yoksa sistem ayarı izlenir; tıklayınca seçim tarayıcıda saklanır.
 * İlk boyamada yanıp sönme olmasın diye `data-theme` değerini app/layout.tsx içindeki satır içi betik atar.
 * Depolama kullanılamıyorsa (gizli pencere vb.) düğme yine o oturum için çalışır.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(currentIsDark());
    // Etiketlerin bir kısmı ilk boyama betiğinden sonra eklenebilir; kayıtlı seçim varsa burada yeniden uygulanır.
    const chosen = document.documentElement.dataset.theme;
    if (chosen === "dark" || chosen === "light") applyBarColor(chosen);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setDark(currentIsDark());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function toggle() {
    const next = currentIsDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    applyBarColor(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* depolama kapalı: seçim yalnızca bu sayfa için geçerli */
    }
    setDark(next === "dark");
  }

  return (
    <button type="button" className="theme-toggle" aria-pressed={dark} title="Gece modu" onClick={toggle}>
      <Icon name="moon" />
      <span className="sr-only">Gece modu</span>
    </button>
  );
}
