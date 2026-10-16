import type { ApiError, CheckRequest, InputMode } from "./types";
import { MAX_INPUT_LENGTH } from "./config";

function isHttpUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return (u.protocol === "http:" || u.protocol === "https:") && u.hostname.includes(".");
  } catch {
    return false;
  }
}

/**
 * Metin alanında Enter yeni satırdır; Ctrl+Enter (macOS: Cmd+Enter) incelemeyi başlatır.
 * Yazım yöntemi (IME) birleştirme sürerken Enter o birleştirmeyi onaylar; gönderim sayılmaz.
 */
export function isSubmitShortcut(e: { key: string; ctrlKey: boolean; metaKey: boolean; isComposing?: boolean }): boolean {
  return e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.isComposing;
}

/** Girdiyi moduna göre doğrular; geçerliyse gönderilecek isteği döner. */
export function validateInput(
  mode: InputMode,
  raw: string,
): { ok: true; request: CheckRequest } | { ok: false; error: ApiError } {
  const content = raw.trim();

  if (content.length === 0) {
    return {
      ok: false,
      error: {
        code: "INVALID_INPUT",
        message: mode === "url" ? "İncelenecek bir bağlantı girin." : "İncelenecek bir metin girin.",
      },
    };
  }
  if (mode === "url") {
    if (!isHttpUrl(content)) {
      return {
        ok: false,
        error: { code: "INVALID_INPUT", message: "Bağlantı geçersiz. https:// ile başlayan tam bir adres girin." },
      };
    }
    return { ok: true, request: { mode, content } };
  }
  if (content.length > MAX_INPUT_LENGTH) {
    return {
      ok: false,
      error: {
        code: "INPUT_TOO_LONG",
        message: `Metin çok uzun (${content.length.toLocaleString("tr-TR")} karakter). En fazla ${MAX_INPUT_LENGTH.toLocaleString("tr-TR")} karakter girebilirsiniz.`,
      },
    };
  }
  return { ok: true, request: { mode, content } };
}
