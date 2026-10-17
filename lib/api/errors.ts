import type { ApiError, ErrorCode } from "../types";

/** Arayüzün tek bir hata tipi görmesi için: her başarısızlık bunu fırlatır. */
export class ApiRequestError extends Error {
  code: ErrorCode;
  constructor(code: ErrorCode, message: string) {
    super(message);
    this.code = code;
  }
  toApiError(): ApiError {
    return { code: this.code, message: this.message };
  }
}
