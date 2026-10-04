/**
 * Sitenin yayın adresi (yalnızca sunucu tarafında, derleme sırasında okunur).
 * Koda elle yazılmaz: Vercel'in bildirdiği üretim alan adı kullanılır; alan adı değişirse ya da özel alan adı
 * eklenirse kendiliğinden izler. Yerelde değişken yoktur ve değer null olur (canonical yazılmaz).
 */
const PRODUCTION_HOST = process.env.VERCEL_PROJECT_PRODUCTION_URL;
export const SITE_ORIGIN: string | null = PRODUCTION_HOST ? `https://${PRODUCTION_HOST}` : null;
