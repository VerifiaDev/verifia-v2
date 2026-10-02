"use client";

import { useEffect, useState } from "react";

const KEY = "verify-theme";
/** globals.css'teki --paper değerleri; telefon tarayıcısının üst çubuk rengi için. */
const BAR_COLOR = { light: "#f6f7f5", dark: "#11151a" } as const;

/** Geçerli görünüm: elle seçilmişse o, değilse sistem tercihi. */
function currentIsDark(): boolean {
  const set = document.documentElement.dataset.theme;
  if (set === "dark") return true;
  if (set === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * Gece modu düğmesi. Tercih yoksa sistem ayarı izlenir; tıklayınca seçim tarayıcıda saklanır.
 * İlk boyamada yanıp sönme olmasın diye `data-theme` değerini app/layout.tsx içindeki satır içi betik atar.
 * Depolama kullanılamıyorsa (gizli pencere vb.) düğme yine o oturum için çalışır.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(currentIsDark());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setDark(currentIsDark());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function toggle() {
    const next = currentIsDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    // Elle seçimde sistem tercihine bağlı (media'lı) etiketler yanlış renk verir; hepsi seçilen renge sabitlenir.
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {
      m.removeAttribute("media");
      m.setAttribute("content", BAR_COLOR[next]);
    });
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* depolama kapalı: seçim yalnızca bu sayfa için geçerli */
    }
    setDark(next === "dark");
  }

  return (
    <button type="button" className="theme-toggle" aria-pressed={dark} onClick={toggle}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
      </svg>
      <span className="theme-toggle-text">Gece modu</span>
    </button>
  );
}
