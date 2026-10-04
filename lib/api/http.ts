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

/**
 * Gövdede tanınan bir kod yoksa HTTP durum kodunun standart anlamına bakılır.
 * Örn. FastAPI'nin varsayılan doğrulama hatası 422 + `{ detail }` döner; bunu "sunucu hatası, sorun
 * girdinizde değil" diye göstermek kullanıcıyı yanlış yönlendirir. Backend'e özgü bir varsayım yoktur.
 */
function codeFromStatus(status: number): ErrorCode {
  if (status === 413) return "INPUT_TOO_LONG";
  if (status === 400 || status === 422) return "INVALID_INPUT";
  if (status === 408 || status === 504) return "TIMEOUT";
  return "INTERNAL_ERROR";
}

/** Backend hata gövdesinden kod çıkarır; tanımazsa durum koduna bakar. Ham sunucu metni kullanıcıya gösterilmez. */
function errorFromResponse(body: unknown, status: number): ApiRequestError {
  const e = (body as { error?: { code?: string; message?: string } } | null)?.error;
  const code = KNOWN_CODES.find((c) => c === e?.code) ?? codeFromStatus(status);
  const message = typeof e?.message === "string" && e.message ? e.message : "Sunucu isteği tamamlayamadı.";
  return new ApiRequestError(code, message);
}

/**
 * Gerçek servis: `POST {baseUrl}/verify` (backend/main.py)  →  tek istek, tek cevap.
 *
 * Backend yalnızca `{ text }` kabul eder. Bağlantı (URL) desteği henüz yok: bağlantıyı iddia gibi
 * göndermek anlamsız sonuç verirdi, bu yüzden "url" modu açık bir hata olarak döner
 * (URL_UNSUPPORTED: "sayfa açılamadı" değil, "bu özellik henüz yok").
 * Backend aşama bilgisi vermediği için `onStage` çağrılmaz.
 */
export function httpService(baseUrl: string): VerificationService {
  // Sondaki "/" karakterleri atılır: ".../" + "/verify" çift eğik çizgiye ("//verify") dönüşmesin.
  const base = baseUrl.replace(/\/+$/, "");
  return {
    async check(req: RawCheckRequest, { signal }): Promise<RawCheckResponse> {
      if (req.input_type === "url") {
        throw new ApiRequestError("URL_UNSUPPORTED", "Bağlantı ile doğrulama henüz desteklenmiyor.");
      }
      const controller = new AbortController();
      let timedOut = false;
      const onAbort = () => controller.abort();
      signal.addEventListener("abort", onAbort);
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const res = await fetch(`${base}/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: req.text }),
          signal: controller.signal,
        });
        const body: unknown = await res.json().catch(() => null);
        if (!res.ok) throw errorFromResponse(body, res.status);
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
