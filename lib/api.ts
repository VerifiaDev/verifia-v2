import { API_BASE_URL, REQUEST_TIMEOUT_MS, USING_MOCK } from "./config";
import { InvalidResponseError, parseCheckResponse } from "./adapter";
import { ApiRequestError } from "./errors";
import { mockCheck } from "./mock";
import type { CheckRequest, CheckResult, ErrorCode } from "./types";

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
 * POST /check  { text, input_type }  →  { claims: [...] }   (tek istek, bekleme yok)
 *
 * VARSAYIM: backend README'si yalnızca { text } tanımlıyor. URL modunda bağlantı `text` alanında
 * gider ve `input_type: "url"` eklenir; backend ekibiyle teyit edilmeli.
 * `signal` ile kullanıcı vazgeçebilir.
 */
export async function checkInput(
  req: CheckRequest,
  signal: AbortSignal,
  // Backend aşama bilgisi verecek hale gelirse (durum sorgulama ya da akış) burada çağrılır.
  // Şu an backend vermiyor; tek istek olduğu için çağrılmaz.
  _onStage?: (phase: "extracting_claims" | "retrieving_evidence" | "verifying") => void,
): Promise<CheckResult> {
  if (USING_MOCK) return mockCheck(req);

  const controller = new AbortController();
  let timedOut = false;
  const onAbort = () => controller.abort();
  signal.addEventListener("abort", onAbort);
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_BASE_URL}/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: req.content, input_type: req.mode }),
      signal: controller.signal,
    });
    const body: unknown = await res.json().catch(() => null);
    if (!res.ok) throw errorFromBody(body);
    return parseCheckResponse(body);
  } catch (err) {
    if (err instanceof ApiRequestError) throw err;
    if (err instanceof InvalidResponseError) {
      throw new ApiRequestError("INTERNAL_ERROR", "Sunucudan beklenmeyen bir yanıt geldi.");
    }
    if (timedOut) throw new ApiRequestError("TIMEOUT", "Sunucu zamanında yanıt vermedi.");
    if (signal.aborted) throw err; // kullanıcı vazgeçti; çağıran taraf bunu yok sayar
    throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", onAbort);
  }
}
