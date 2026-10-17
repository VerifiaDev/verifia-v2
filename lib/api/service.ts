import type { RawCheckRequest, RawCheckResponse } from "./contract";
import type { AnalysisStage } from "../types";

/**
 * Doğrulama servisinin tek arayüzü. Hem mock hem gerçek (FastAPI) servis bunu uygular;
 * arayüz hangisinin çalıştığını bilmez.
 *
 * Başarısızlıkta `ApiRequestError` fırlatır (bkz. errors.ts). Ham cevabı döner; çeviri `index.ts`'te yapılır.
 */
export interface VerificationService {
  /** Servis bağlantıyla (URL) incelemeyi destekliyor mu? Desteklemiyorsa arayüz "Bağlantı" seçeneğini hiç göstermez. */
  supportsUrl: boolean;
  /**
   * Sunucuyu uyandırır (sayfa açılınca çağrılır). Sonucu beklenmez, hata fırlatmaz.
   * Yalnızca gerçek servis uygular; örnek (mock) ve "bağlı değil" servislerinde yoktur.
   */
  warmUp?(): void;
  check(
    req: RawCheckRequest,
    ctx: {
      signal: AbortSignal;
      /** Backend gerçek aşama bilgisi verirse çağrılır; vermiyorsa hiç çağrılmaz. */
      onStage?: (stage: AnalysisStage) => void;
      /**
       * İnceleme henüz başlamadı, sunucunun yanıtı bekleniyor (true) / sunucu yanıt verdi (false).
       * Yalnızca bekleme fark edilir hâle gelince çağrılır; sunucu hemen yanıt verirse hiç çağrılmaz.
       */
      onServerWait?: (waiting: boolean) => void;
    },
  ): Promise<RawCheckResponse>;
}
