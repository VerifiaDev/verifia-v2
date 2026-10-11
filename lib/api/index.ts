/**
 * Arayüzün backend ile konuştuğu TEK kapı.
 *
 *   UI (hooks/useAnalysis) → checkInput() → [mock servis | http servis] → adapter → UI tipleri
 *
 * Hangi servisin çalışacağı `NEXT_PUBLIC_API_BASE_URL` ile belirlenir: boşsa mock, doluysa FastAPI.
 * Mock da gerçek servis de AYNI ham sözleşmeyi (contract.ts) döner ve AYNI adapter'dan geçer;
 * böylece mock'ta çalışan her şey gerçek cevapla da aynı yolu izler.
 */
import { API_BASE_URL } from "../config";
import { InvalidResponseError, parseCheckResponse } from "./adapter";
import { ApiRequestError } from "./errors";
import { httpService } from "./http";
import { MOCK_EXAMPLES, mockService } from "./mock";
import { curatedSample } from "../sample-report";
import type { VerificationService } from "./service";
import type { AnalysisStage, CheckRequest, CheckResult, InputMode } from "../types";

export { ApiRequestError } from "./errors";

const isProduction = process.env.NODE_ENV === "production";
const hasBackend = API_BASE_URL !== "";

/** Adres yokken yalnızca geliştirmede örnek servis çalışır; yayında uydurma sonuç üretilmez. */
const usingMock = !hasBackend && !isProduction;
/** Yayın derlemesinde adres tanımlı değilse inceleme yapılamaz; bunu açıkça söyleriz. */
const unavailable = !hasBackend && isProduction;

const unavailableService: VerificationService = {
  supportsUrl: false,
  async check() {
    throw new ApiRequestError("NETWORK", "İnceleme servisi şu an bağlı değil.");
  },
};

const service: VerificationService = hasBackend
  ? httpService(API_BASE_URL)
  : usingMock
    ? mockService
    : unavailableService;

export interface ExampleInput {
  label: string;
  mode: InputMode;
  content: string;
  /** Geliştirici senaryosu (aşama taklidi, hata denemesi). Yayındaki sitede listelenmez. */
  dev?: boolean;
}

/** Yayın derlemesinde (`next build`) geliştirici senaryoları listeden çıkar; anahtar kelimeler yine çalışır. */
const showDevExamples = process.env.NODE_ENV !== "production";

/** Arayüz için servis bilgisi. Mock'un kendisini değil, yalnızca bunları bilir. */
export const apiInfo: {
  usingMock: boolean;
  unavailable: boolean;
  /** Bağlı servis bağlantıyla incelemeyi destekliyor mu? Desteklemiyorsa "Bağlantı" seçeneği gösterilmez. */
  urlSupported: boolean;
  examples: ExampleInput[];
} = {
  usingMock,
  unavailable,
  urlSupported: service.supportsUrl,
  examples: usingMock ? MOCK_EXAMPLES.filter((ex) => showDevExamples || !ex.dev) : [],
};

/**
 * Sabit örnek sonuç: servis bağlı değilken arayüzün ne ürettiğini göstermek için.
 * Gerçek cevapla aynı adapter'dan geçer. Arayüz bunu "Örnek" etiketiyle gösterir; gerçek inceleme gibi sunulmaz.
 */
export function sampleResult(): CheckResult {
  return curatedSample();
}

/** Sayfa açılınca çağrılır: uyuyan sunucuyu uyandırır (yalnızca gerçek servis bağlıyken bir şey yapar). */
export function warmUp(): void {
  service.warmUp?.();
}

export async function checkInput(
  req: CheckRequest,
  signal: AbortSignal,
  onStage?: (stage: AnalysisStage) => void,
  onServerWait?: (waiting: boolean) => void,
): Promise<CheckResult> {
  const raw = await service.check({ text: req.content, input_type: req.mode }, { signal, onStage, onServerWait });
  try {
    return parseCheckResponse(raw);
  } catch (err) {
    if (err instanceof InvalidResponseError) {
      throw new ApiRequestError("INTERNAL_ERROR", "Sunucudan beklenmeyen bir yanıt geldi.");
    }
    throw err;
  }
}
