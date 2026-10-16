import type { MetadataRoute } from "next";
import { sitemapEntries } from "@/lib/seo";

/** /sitemap.xml (derlemede statik üretilir). Sayfa listesi: lib/seo.ts */
export default function sitemap(): MetadataRoute.Sitemap {
  return sitemapEntries();
}
