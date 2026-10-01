import type { RawCheckRequest, RawCheckResponse } from "./contract";
import type { AnalysisStage } from "../types";

/**
 * Doğrulama servisinin tek arayüzü. Hem mock hem gerçek (FastAPI) servis bunu uygular;
 * arayüz hangisinin çalıştığını bilmez.
 *
 * Başarısızlıkta `ApiRequestError` fırlatır (bkz. errors.ts). Ham cevabı döner; çeviri `index.ts`'te yapılır.
 */
export interface VerificationService {
  check(
    req: RawCheckRequest,
    ctx: {
      signal: AbortSignal;
      /** Backend gerçek aşama bilgisi verirse çağrılır; vermiyorsa hiç çağrılmaz. */
      onStage?: (stage: AnalysisStage) => void;
    },
  ): Promise<RawCheckResponse>;
}
