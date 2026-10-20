import type { ApiError, ErrorCode } from "../types";

/** Arayüzün tek bir hata tipi görmesi için: her başarısızlık bunu fırlatır. */
export class ApiRequestError extends Error {
  code: ErrorCode;
  requestId?: string;
  constructor(code: ErrorCode, message: string, requestId?: string) {
    super(message);
    this.code = code;
    this.requestId = requestId;
  }
  toApiError(): ApiError {
    return this.requestId ? { code: this.code, message: this.message, requestId: this.requestId } : { code: this.code, message: this.message };
  }
}
