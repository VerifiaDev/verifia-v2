"use client";

import { useId, useRef, useState } from "react";
import { MAX_INPUT_LENGTH } from "@/lib/config";
import { INPUT_MODES } from "@/lib/format";
import { validateInput } from "@/lib/input";
import type { ExampleInput } from "@/lib/api";
import type { CheckRequest, InputMode } from "@/lib/types";

interface Props {
  disabled?: boolean;
  onSubmit: (req: CheckRequest) => void;
  /** Örnek kullanım (yalnızca örnek veri modunda). */
  examples?: ExampleInput[];
}

/**
 * Giriş alanı: Metin / Bağlantı seçimi, doğrulama ve gönder.
 * Hata mesajı alanın hemen altında, alana `aria-describedby` ile bağlı gösterilir.
 * Değerler bu bileşende tutulur; hata ya da yeniden deneme sırasında kaybolmaz.
 */
export function VerificationInput({ disabled = false, onSubmit, examples }: Props) {
  const [mode, setMode] = useState<InputMode>("text");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const urlRef = useRef<HTMLInputElement>(null);
  const uid = useId();
  const fieldId = `${uid}-field`;
  const hintId = `${uid}-hint`;
  const errId = `${uid}-err`;

  function submit(m: InputMode, v: string) {
    const res = validateInput(m, v);
    if (!res.ok) {
      setError(res.error.message);
      (m === "url" ? urlRef : textRef).current?.focus();
      return;
    }
    setError(null);
    onSubmit(res.request);
  }

  function changeMode(next: InputMode) {
    setMode(next);
    setError(null);
  }

  const isText = mode === "text";
  const length = value.trim().length;
  const describedBy = error ? `${hintId} ${errId}` : hintId;

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit(mode, value);
      }}
    >
      <fieldset className="modes-set" disabled={disabled}>
        <legend className="sr-only">Girdi türü</legend>
        <div className="modes" role="radiogroup" aria-label="Girdi türü">
          {INPUT_MODES.map((m) => (
            <label key={m.id} className="mode">
              <input
                type="radio"
                name={`${uid}-mode`}
                value={m.id}
                checked={mode === m.id}
                onChange={() => changeMode(m.id)}
              />
              <span>{m.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <label htmlFor={fieldId} className="field-label t-h4">
        {isText ? "Doğrulanacak metin" : "Doğrulanacak haberin bağlantısı"}
      </label>

      {isText ? (
        <textarea
          ref={textRef}
          id={fieldId}
          className="field"
          rows={7}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder="Bir haber metnini, sosyal medya paylaşımını ya da tek bir iddiayı yapıştırın."
        />
      ) : (
        <input
          ref={urlRef}
          id={fieldId}
          className="field"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder="https://ornek.com/haber"
        />
      )}

      <div className="field-foot">
        <p id={hintId} className="field-hint">
          {isText
            ? `Uzun metinlerde birden fazla iddia ayrı ayrı incelenir. En fazla ${MAX_INPUT_LENGTH.toLocaleString("tr-TR")} karakter.`
            : "Haberin tam adresini girin. Sayfa açılamazsa metni kopyalayıp “Metin” sekmesinden gönderebilirsiniz."}
          {isText && length > 0 && (
            <>
              {" "}
              <span aria-hidden="true">({length.toLocaleString("tr-TR")} karakter)</span>
            </>
          )}
        </p>
        {error && (
          <p id={errId} className="field-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="actions">
        <button type="submit" className="btn" disabled={disabled}>
          Kanıtlara bak
        </button>
      </div>

      {examples && examples.length > 0 && (
        <div className="examples">
          <p className="t-meta muted">Örnek deneyin (örnek veri):</p>
          <ul className="examples-list">
            {examples.map((ex) => (
              <li key={ex.label}>
                <button
                  type="button"
                  className="link-btn"
                  disabled={disabled}
                  onClick={() => {
                    setMode(ex.mode);
                    setValue(ex.content);
                    setError(null);
                    submit(ex.mode, ex.content);
                  }}
                >
                  {ex.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
