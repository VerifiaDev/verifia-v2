import { REQUEST_TIMEOUT_MS } from "../config";
import { ApiRequestError } from "./errors";
import type { RawCheckRequest, RawCheckResponse } from "./contract";
import type { ErrorCode } from "../types";
import type { VerificationService } from "./service";

const KNOWN_CODES: ErrorCode[] = [
  "INVALID_INPUT",
  "INPUT_TOO_LONG",
  "URL_UNREADABLE",
  "IMAGE_UNREADABLE",
  "TIMEOUT",
  "NETWORK",
  "INTERNAL_ERROR",
];

/** Backend hata gövdesinden kod çıkarır; tanımazsa INTERNAL_ERROR. Ham sunucu metni kullanıcıya gösterilmez. */
function errorFromBody(body: unknown): ApiRequestError {
  const e = (body as { error?: { code?: string; message?: string } } | null)?.error;
  const code = KNOWN_CODES.find((c) => c === e?.code) ?? "INTERNAL_ERROR";
  const message = typeof e?.message === "string" && e.message ? e.message : "Sunucu isteği tamamlayamadı.";
  return new ApiRequestError(code, message);
}

/**
 * Gerçek servis: `POST {baseUrl}/check`  →  tek istek, tek cevap.
 *
 * VARSAYIM: backend README'si yalnızca { text } tanımlıyor; `input_type` bizim eklememiz ve
 * backend ekibiyle teyit edilmeli. Backend aşama bilgisi vermediği için `onStage` çağrılmaz.
 */
export function httpService(baseUrl: string): VerificationService {
  return {
    async check(req: RawCheckRequest, { signal }): Promise<RawCheckResponse> {
      const controller = new AbortController();
      let timedOut = false;
      const onAbort = () => controller.abort();
      signal.addEventListener("abort", onAbort);
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const res = await fetch(`${baseUrl}/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(req),
          signal: controller.signal,
        });
        const body: unknown = await res.json().catch(() => null);
        if (!res.ok) throw errorFromBody(body);
        return body as RawCheckResponse; // şekil adapter'da doğrulanır
      } catch (err) {
        if (err instanceof ApiRequestError) throw err;
        if (timedOut) throw new ApiRequestError("TIMEOUT", "Sunucu zamanında yanıt vermedi.");
        if (signal.aborted) throw err; // kullanıcı vazgeçti; çağıran taraf bunu yok sayar
        throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
      } finally {
        clearTimeout(timer);
        signal.removeEventListener("abort", onAbort);
      }
    },
  };
}
