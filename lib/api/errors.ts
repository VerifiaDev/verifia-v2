import type { ApiError, ErrorCode } from "../types";

/** Arayüzün tek bir hata tipi görmesi için: her başarısızlık bunu fırlatır. */
export class ApiRequestError extends Error {
  code: ErrorCode;
  requestId?: string;
  retryAfterSeconds?: number;
  constructor(code: ErrorCode, message: string, requestId?: string, retryAfterSeconds?: number) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.retryAfterSeconds = retryAfterSeconds;
  }
  toApiError(): ApiError {
    const out: ApiError = { code: this.code, message: this.message };
    if (this.requestId) out.requestId = this.requestId;
    if (this.retryAfterSeconds) out.retryAfterSeconds = this.retryAfterSeconds;
    return out;
  }
}
