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
import type { VerificationService } from "./service";
import type { AnalysisStage, CheckRequest, CheckResult, InputMode } from "../types";

export { ApiRequestError } from "./errors";

const usingMock = API_BASE_URL === "";
const service: VerificationService = usingMock ? mockService : httpService(API_BASE_URL);

export interface ExampleInput {
  label: string;
  mode: InputMode;
  content: string;
}

/** Arayüz için servis bilgisi. Mock'un kendisini değil, yalnızca bunları bilir. */
export const apiInfo: { usingMock: boolean; examples: ExampleInput[] } = {
  usingMock,
  examples: usingMock ? MOCK_EXAMPLES : [],
};

export async function checkInput(
  req: CheckRequest,
  signal: AbortSignal,
  onStage?: (stage: AnalysisStage) => void,
): Promise<CheckResult> {
  const raw = await service.check({ text: req.content, input_type: req.mode }, { signal, onStage });
  try {
    return parseCheckResponse(raw);
  } catch (err) {
    if (err instanceof InvalidResponseError) {
      throw new ApiRequestError("INTERNAL_ERROR", "Sunucudan beklenmeyen bir yanıt geldi.");
    }
    throw err;
  }
}
