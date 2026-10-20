import { HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS, SERVER_WAIT_NOTICE_MS, STREAM_IDLE_TIMEOUT_MS } from "../config";
import { ApiRequestError } from "./errors";
import type { RawCheckRequest, RawCheckResponse, RawClaim } from "./contract";
import type { AnalysisStage, ErrorCode } from "../types";
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
  // backend_v2: bellek sınırı (security.py, 503 + Retry-After) ve yapay zekâ servisinin kullanım sınırı (upstream_errors.py)
  LOW_MEMORY: "SERVER_BUSY",
  UPSTREAM_RATE_LIMITED: "SERVICE_UNAVAILABLE",
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

/**
 * Sunucunun `X-Request-ID` başlığı (backend_v2: her yanıtta var, CORS ile açık). Yalnızca backend'in kendi
 * biçimine uyuyorsa (8-64 karakter, harf/rakam/. _ -) alınır; böylece ekrana beklenmedik içerik basılmaz.
 */
export function readRequestId(res: Pick<Response, "headers">): string | undefined {
  const id = res.headers?.get("X-Request-ID");
  return id && /^[A-Za-z0-9._-]{8,64}$/.test(id) ? id : undefined;
}

/**
 * `Retry-After` başlığı (backend_v2: 429 ve 503'te saniye cinsinden tam sayı). Yalnızca 1-3600 arası
 * tam sayı alınır; tarih biçimi ya da anlamsız değer yok sayılır (bekleme süresi uydurulmaz).
 */
export function readRetryAfter(res: Pick<Response, "headers">): number | undefined {
  const raw = res.headers?.get("Retry-After");
  if (!raw || !/^\d{1,4}$/.test(raw.trim())) return undefined;
  const n = Number(raw);
  return n >= 1 && n <= 3600 ? n : undefined;
}

/** Backend hata gövdesinden kod çıkarır; tanımazsa durum koduna bakar. Ham sunucu metni kullanıcıya gösterilmez. */
function errorFromResponse(body: unknown, status: number, requestId?: string, retryAfter?: number): ApiRequestError {
  const b = body as { error?: unknown; message?: unknown } | null;
  // Gerçek backend: { status:"error", error:"VERIFY_FAILED", message }  (error düz yazı).
  // Eski/varsayılan şekil: { error: { code, message } }.
  const nested = typeof b?.error === "object" && b.error !== null ? (b.error as { code?: unknown; message?: unknown }) : null;
  const rawCode = typeof b?.error === "string" ? b.error : typeof nested?.code === "string" ? nested.code : "";
  const rawMessage = typeof b?.message === "string" ? b.message : nested?.message;
  const code = KNOWN_CODES.find((c) => c === rawCode) ?? BACKEND_CODES[rawCode] ?? codeFromStatus(status);
  const message = typeof rawMessage === "string" && rawMessage ? rawMessage : "Sunucu isteği tamamlayamadı.";
  return new ApiRequestError(code, message, requestId, retryAfter);
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
    if (!res.ok && res.status !== 404) throw errorFromResponse(body, res.status, readRequestId(res), readRetryAfter(res));
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

/** Akıştaki bir olay bloğu: `event: <ad>` + `data: <json>`. `:` ile başlayan satırlar (keep-alive) yok sayılır. */
function parseEvent(block: string): Record<string, unknown> | null {
  let name = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!data.length) return null;
  try {
    const parsed: unknown = JSON.parse(data.join("\n"));
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
    const event = parsed as Record<string, unknown>;
    return { ...event, type: typeof event.type === "string" ? event.type : name };
  } catch {
    return null; // bozuk satır: yok sayılır, sonuç done/error'a göre belirlenir
  }
}

/** `request_id` yalnızca backend'in biçimine uyuyorsa alınır (bkz. readRequestId). */
function safeRequestId(value: unknown): string | undefined {
  return typeof value === "string" && /^[A-Za-z0-9._-]{8,64}$/.test(value) ? value : undefined;
}

/**
 * POST /verify/stream olaylarını (backend_v2/app/streaming.py) okuyup /verify ile aynı ham cevabı kurar.
 * Aşama yalnızca backend bildirdikçe verilir: ayrıştırma başladı → "extracting_claims"; doğrulama başladı →
 * "retrieving_evidence"; ilk gerçek hüküm geldi → "verifying" (backend arama ile karşılaştırmayı ayrı bildirmez).
 * Tanınmayan olaylar yok sayılır. `done` gelmeden akış biterse bağlantı kopmuş sayılır.
 */
async function readStream(
  body: ReadableStream<Uint8Array>,
  { signal, onStage, onActivity, requestId }: {
    signal: AbortSignal; onStage?: (stage: AnalysisStage) => void; onActivity: () => void; requestId?: string;
  },
): Promise<RawCheckResponse> {
  const reader = body.getReader();
  // İptal edilince bekleyen okuma hemen biter (gerçek fetch'te bağlantı da kapanır; backend işi durdurur).
  const cancel = () => { reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", cancel);
  const decoder = new TextDecoder();
  let buffer = "";
  let order: string[] = [];
  const results = new Map<string, RawClaim>();
  let verdictSeen = false;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      signal.throwIfAborted();
      if (done) break;
      onActivity();
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const event = parseEvent(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        if (!event) continue;
        if (event.type === "stage" && event.status === "started") {
          if (event.stage === "extract") onStage?.("extracting_claims");
          if (event.stage === "verify") onStage?.("retrieving_evidence");
        } else if (event.type === "claims" && Array.isArray(event.claims)) {
          order = event.claims.flatMap((c) => (typeof c === "object" && c && typeof c.claim_id === "string" ? [c.claim_id] : []));
        } else if (event.type === "result" && typeof event.result === "object" && event.result !== null) {
          const result = event.result as RawClaim;
          results.set(typeof result.claim_id === "string" ? result.claim_id : `#${results.size}`, result);
          if (!verdictSeen && result.verdict != null) {
            verdictSeen = true;
            onStage?.("verifying");
          }
        } else if (event.type === "error") {
          throw errorFromResponse(event, 502, safeRequestId(event.request_id) ?? requestId);
        } else if (event.type === "done") {
          const ordered = [...order.filter((id) => results.has(id)), ...[...results.keys()].filter((id) => !order.includes(id))];
          return { results: ordered.map((id) => results.get(id)!), partial: event.partial === true };
        }
      }
    }
    throw new ApiRequestError("NETWORK", "Sunucuyla bağlantı inceleme bitmeden kesildi.", requestId);
  } finally {
    signal.removeEventListener("abort", cancel);
  }
}

/**
 * Gerçek servis: önce `POST {baseUrl}/verify/stream` (backend_v2, Server-Sent Events).
 *
 * Akış sayesinde backend gerçek aşama bilgisi verir (`onStage`) ve kullanıcı vazgeçince bağlantı kapanır;
 * backend bunu fark edip incelemeyi iptal eder (düz /verify'da iş sürüyordu). Sonuç /verify ile aynı ham
 * şekildedir ve aynı adapter'dan geçer. `/verify/stream` yoksa (404/405, eski backend) `POST /verify` kullanılır;
 * yanıt akış değil düz JSON gelirse eskisi gibi okunur.
 *
 * Backend yalnızca `{ text }` kabul eder. Bağlantı (URL) desteği henüz yok: bağlantıyı iddia gibi
 * göndermek anlamsız sonuç verirdi, bu yüzden "url" modu açık bir hata olarak döner
 * (URL_UNSUPPORTED: "sayfa açılamadı" değil, "bu özellik henüz yok").
 * Önce `GET /health` ile sunucunun yanıt verdiği denetlenir (bkz. waitForHealth).
 * Süre: toplam REQUEST_TIMEOUT_MS; akışta ayrıca STREAM_IDLE_TIMEOUT_MS boyunca hiç veri gelmezse vazgeçilir.
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
    async check(req: RawCheckRequest, { signal, onServerWait, onStage }): Promise<RawCheckResponse> {
      if (req.input_type === "url") {
        throw new ApiRequestError("URL_UNSUPPORTED", "Bağlantı ile doğrulama henüz desteklenmiyor.");
      }
      await waitForHealth(base, signal, onServerWait);
      signal.throwIfAborted();

      const controller = new AbortController();
      let timedOut = false;
      const expire = () => {
        timedOut = true;
        controller.abort();
      };
      const onAbort = () => controller.abort();
      signal.addEventListener("abort", onAbort);
      const timer = setTimeout(expire, REQUEST_TIMEOUT_MS);
      let idle: ReturnType<typeof setTimeout> | undefined;
      const resetIdle = () => {
        clearTimeout(idle);
        idle = setTimeout(expire, STREAM_IDLE_TIMEOUT_MS);
      };
      const post = (path: string) => fetch(`${base}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: req.text }),
        signal: controller.signal,
      });

      try {
        let res = await post("/verify/stream");
        if (res.status === 404 || res.status === 405) {
          await res.body?.cancel().catch(() => {});
          res = await post("/verify"); // akış desteği olmayan eski backend
        }
        if (res.ok && res.body && (res.headers.get("Content-Type") ?? "").includes("text/event-stream")) {
          resetIdle();
          return await readStream(res.body, { signal: controller.signal, onStage, onActivity: resetIdle, requestId: readRequestId(res) });
        }
        const body: unknown = await res.json().catch(() => null);
        controller.signal.throwIfAborted();
        if (!res.ok) throw errorFromResponse(body, res.status, readRequestId(res), readRetryAfter(res));
        return body as RawCheckResponse; // şekil adapter'da doğrulanır
      } catch (err) {
        if (err instanceof ApiRequestError) throw err;
        if (timedOut) throw new ApiRequestError("TIMEOUT", "Sunucu zamanında yanıt vermedi.");
        if (signal.aborted) throw err; // kullanıcı vazgeçti; çağıran taraf bunu yok sayar
        throw new ApiRequestError("NETWORK", "Sunucuya ulaşılamadı.");
      } finally {
        clearTimeout(timer);
        clearTimeout(idle);
        signal.removeEventListener("abort", onAbort);
      }
    },
  };
}
