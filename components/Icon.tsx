import type { ReactNode } from "react";

/**
 * Sitedeki tüm simgeler tek settir: 24×24, yalnızca çizgi, aynı çizgi kalınlığı (stil: globals.css `.icon`).
 * Simge her zaman yazıyla birlikte kullanılır ve süslemedir (`aria-hidden`); anlamı yanındaki yazı taşır.
 */
export type IconName = "check" | "cross" | "not-equal" | "question" | "moon" | "chevron" | "external";

const RING = <circle cx="12" cy="12" r="9.5" />;

const SHAPES: Record<IconName, ReactNode> = {
  check: (
    <>
      {RING}
      <path d="m8 12.4 2.7 2.7L16 9.6" />
    </>
  ),
  cross: (
    <>
      {RING}
      <path d="m9 9 6 6M15 9l-6 6" />
    </>
  ),
  "not-equal": (
    <>
      {RING}
      <path d="M8 10.2h8M8 13.8h8M14.2 7.6l-4.4 8.8" />
    </>
  ),
  question: (
    <>
      {RING}
      <path d="M9.7 9.7a2.4 2.4 0 1 1 3.6 2.1c-.8.5-1.3 1-1.3 1.9M12 16.6v.1" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  external: <path d="M14 5h5v5M19 5l-8 8M11 7H6.5A1.5 1.5 0 0 0 5 8.5v9A1.5 1.5 0 0 0 6.5 19h9a1.5 1.5 0 0 0 1.5-1.5V13" />,
};

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      data-icon={name}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {SHAPES[name]}
    </svg>
  );
}
