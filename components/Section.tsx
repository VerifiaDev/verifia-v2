import type { ReactNode } from "react";

/** Sayfa bölümü: ayraç çizgisi, kapsayıcı ve başlık. `id` hem bağlantı hedefi hem başlık kimliğinin kökü. */
export function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="section" aria-labelledby={`${id}-title`}>
      <div className="container section-grid">
        <div className="section-head">
          <h2 id={`${id}-title`} className="t-h2">
            {title}
          </h2>
        </div>
        <div className="section-body">{children}</div>
      </div>
    </section>
  );
}
