/**
 * ALTERNATİF, ŞU AN KULLANILMIYOR. Navbar kendi işaretini (belge + nokta) çiziyor; bu dosya "Logo A: Atıf"
 * önerisinin işaretidir: köşeli parantez içinde 1, yani ürünün kendi atıf işareti.
 * Geçmek isterseniz Navbar.tsx içindeki yerel BrandMark yerine bunu içe aktarın; istemezseniz bu dosya silinebilir.
 * 16'lık ızgaraya oturtulmuştur; parantezler yazı rengini, rakam vurgu rengini alır.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M1 2h4v2H3v8h2v2H1zM15 2h-4v2h2v8h-2v2h4z" fill="currentColor" />
      <path d="M7.5 4h2v8h-2zM6 5h1.5v1.5H6z" fill="var(--accent)" />
    </svg>
  );
}
