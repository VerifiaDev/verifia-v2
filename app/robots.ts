import type { MetadataRoute } from "next";
import { robotsRules } from "@/lib/seo";

/** /robots.txt (derlemede statik üretilir). Kurallar: lib/seo.ts */
export default function robots(): MetadataRoute.Robots {
  return robotsRules();
}
