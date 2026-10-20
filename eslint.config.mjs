import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  // "**/.next/**": alt klasörlerde kalmış eski derleme çıktıları da (ör. önceki depo yapısından frontend/.next) taranmaz.
  globalIgnores(["**/.next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
