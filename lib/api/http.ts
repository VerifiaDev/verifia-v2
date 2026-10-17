import { HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS, SERVER_WAIT_NOTICE_MS } from "../config";
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
  "RATE_LIMITED",
  "NETWORK",
  "INTERNAL_ERROR",
];

/**
 * Backend hata kodları → arayüz kodları.
 * İlk üçü backend/main.py'de VAR (VALIDATION_ERROR hem boş hem 10.000 karakterden uzun metinde döner).
 * Diğerleri docs/BACKEND_TODO.md'de ÖNERİLEN kodlardır; backend eklediği gün doğru mesaj gösterilsin diye
 * şimdiden tanınır. Eklenmezlerse hiçbir etkileri yoktur (durum koduna bakılır).
 */
const BACKEND_CODES: Record<string, ErrorCode> = {
  VALIDATION_ERROR: "INVALID_INPUT",
  EMPTY_TEXT: "INVALID_INPUT",
  VERIFY_FAILED: "INTERNAL_ERROR",
  TEXT_TOO_LONG: "INPUT_TOO_LONG",
  RATE_LIMITED: "RATE_LIMITED",
  BUSY: "SERVER_BUSY",
  DAILY_QUOTA_EXCEEDED: "QUOTA_EXCEEDED",
  UPSTREAM_UNAVAILABLE: "SERVICE_UNAVAILABLE",
  // backend_v2 (MertBulut11/verify-v2): iddia ayrıştırma ve yapılandırma hataları
  EXTRACTION_TIMEOUT: "TIMEOUT",
  EXTRACTION_FAILED: "SERVICE_UNAVAILABLE",
  CONFIG_ERROR: "SERVICE_UNAVAILABLE",
};

/**
 * Gövdede tanınan bir kod yoksa HTTP durum kodunun standart anlamına bakılır.
 * Örn. FastAPI'nin varsayılan doğrulama hatası 422 + `{ detail }` döner; bunu "sunucu hatası, sorun
 * girdinizde değil" diye göstermek kullanıcıyı yanlış yönlendirir. Backend'e özgü bir varsayım yoktur.
 */
function codeFromStatus(status: number): ErrorCode {
  if (status === 429) return "RATE_LIMITED";
  if (status === 413) return "INPUT_TOO_LONG";
  if (status === 400 || status === 422) return "INVALID_INPUT";
  if (status === 408 || status === 504) return "TIMEOUT";
  if (status === 502 || status === 503) return "SERVICE_UNAVAILABLE";
  return "INTERNAL_ERROR";
}

/** Backend hata gövdesinden kod çıkarır; tanımazsa durum koduna bakar. Ham sunucu metni kullanıcıya gösterilmez. */
function errorFromResponse(body: unknown, status: number): ApiRequestError {
  const b = body as { error?: unknown; message?: unknown } | null;
  // Gerçek backend: { status:"error", error:"VERIFY_FAILED", message }  (error düz yazı).
  // Eski/varsayılan şekil: { error: { code, message } }.
  const nested = typeof b?.error === "object" && b.error !== null ? (b.error as { code?: unknown; message?: unknown }) : null;
  const rawCode = typeof b?.error === "string" ? b.error : typeof nested?.code === "string" ? nested.code : "";
  const rawMessage = typeof b?.message === "string" ? b.message : nested?.message;
  const code = KNOWN_CODES.find((c) => c === rawCode) ?? BACKEND_CODES[rawCode] ?? codeFromStatus(status);
  const message = typeof rawMessage === "string" && rawMessage ? rawMessage : "Sunucu isteği tamamlayamadı.";
  return new ApiRequestError(code, message);
}

/**
 * İncelemeden önce sunucunun yanıt verip vermediğine bakar (`GET /health`, backend/main.py).
 *
 * Neden: backend tek bir incelemeyi işlerken başka hiçbir isteğe yanıt vermeyebiliyor ve her inceleme
 * dış servislerde (dil modeli, web araması) kota harcıyor. Kilitli sunucuya ikinci bir inceleme göndermek
 * hem kullanıcıyı boşuna bekletir hem kotayı boşa harcar. Bu yüzden sağlık yanıtı süresinde gelmezse
 * inceleme isteği HİÇ gönderilmez ve "sunucu yanıt vermiyor" denir.
 *
 * Sağlık denetimi başarısızsa inceleme gönderilmez. Eski servislerde `/health` bulunmaması (404)
 * uyumluluk için kabul edilir; diğer HTTP hataları ve `degraded` durumu kullanıcıya bildirilir.
 */
async function waitForHealth(base: string, signal: AbortSignal, onServerWait?: (waiting: boolean) => void): Promise<void> {
  signal.throwIfAborted();
  const controller = new AbortController();
  let timedOut = false;
  let noticed = false;
  const onAbort = () => controller.abort();
  signal.addEventListener("abort", onAbort);
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, HEALTH_TIMEOUT_MS);
  // Yanıt gecikirse arayüz "inceleniyor" demesin: henüz hiçbir şey incelenmiyor, sunucu bekleniyor.
  const notice = setTimeout(() => {
    noticed = true;
    onServerWait?.(true);
  }, SERVER_WAIT_NOTICE_MS);
  try {
    const res = await fetch(`${base}/health`, { method: "GET", cache: "no-store", signal: controller.signal });
    const body: unknown = await res.json().catch(() => null);
    controller.signal.throwIfAborted();
    if (!res.ok && res.status !== 404) throw errorFromResponse(body, res.status);
    if (res.ok && typeof body === "object" && body !== null && "status" in body && (body.status === "degraded" || body.status === "error")) {
      throw new ApiRequestError("SERVICE_UNAVAILABLE", "İnceleme servisi henüz hazır değil.");
    }
    if (noticed) onServerWait?.(false);
  } catch (err) {
    if (signal.aborted) throw err;
    if (err instanceof ApiRequestError) throw err;
    if (timedOut) throw new ApiRequestError("SERVER_BUSY", "Sunucu sağlık denetimine yanıt vermedi.");
    throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
  } finally {
    clearTimeout(timer);
    clearTimeout(notice);
    signal.removeEventListener("abort", onAbort);
  }
}

/**
 * Gerçek servis: `POST {baseUrl}/verify` (backend/main.py, teyitli)  →  tek istek, tek cevap.
 *
 * Backend yalnızca `{ text }` kabul eder. Bağlantı (URL) desteği henüz yok: bağlantıyı iddia gibi
 * göndermek anlamsız sonuç verirdi, bu yüzden "url" modu açık bir hata olarak döner
 * (URL_UNSUPPORTED: "sayfa açılamadı" değil, "bu özellik henüz yok").
 * Önce `GET /health` ile sunucunun yanıt verdiği denetlenir (bkz. waitForHealth).
 * Backend aşama bilgisi vermediği için `onStage` çağrılmaz.
 */
export function httpService(baseUrl: string): VerificationService {
  // Sondaki "/" karakterleri atılır: ".../" + "/verify" çift eğik çizgiye ("//verify") dönüşmesin.
  const base = baseUrl.replace(/\/+$/, "");
  return {
    supportsUrl: false,
    /**
     * Barındırma hizmeti boşta kalan sunucuyu uyutuyor; uyanması dakikaları bulabiliyor (11 Ekim 2026 ölçümü:
     * ilk `/health` yanıtı yaklaşık 132 saniye). Sayfa açılınca gönderilen bu hafif istek, kullanıcı metnini
     * yapıştırırken sunucunun açılmasını sağlar. Kota harcamaz; yanıtı beklenmez, hatası yok sayılır.
     */
    warmUp(): void {
      fetch(`${base}/health`, { method: "GET", cache: "no-store" })
        .then((res) => res.body?.cancel())
        .catch(() => {});
    },
    async check(req: RawCheckRequest, { signal, onServerWait }): Promise<RawCheckResponse> {
      if (req.input_type === "url") {
        throw new ApiRequestError("URL_UNSUPPORTED", "Bağlantı ile doğrulama henüz desteklenmiyor.");
      }
      await waitForHealth(base, signal, onServerWait);
      signal.throwIfAborted();

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
        controller.signal.throwIfAborted();
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
