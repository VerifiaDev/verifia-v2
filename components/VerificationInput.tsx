"use client";

import { useId, useRef, useState } from "react";
import { MAX_INPUT_LENGTH } from "@/lib/config";
import { INPUT_MODES } from "@/lib/format";
import { validateInput } from "@/lib/input";
import type { ExampleInput } from "@/lib/api";
import type { CheckRequest, InputMode } from "@/lib/types";

interface Props {
  disabled?: boolean;
  busy?: boolean;
  readOnly?: boolean;
  onEdit?: () => void;
  onSubmit: (req: CheckRequest) => void;
  /** Örnek kullanım (yalnızca örnek veri modunda). */
  examples?: ExampleInput[];
}

/**
 * Giriş alanı: Metin / Bağlantı seçimi, doğrulama ve gönder.
 * Hata mesajı alanın hemen altında, alana `aria-describedby` ile bağlı gösterilir.
 * Değerler bu bileşende tutulur; hata ya da yeniden deneme sırasında kaybolmaz.
 * Metin ve Bağlantı sekmelerinin değerleri ayrı tutulur (metin, bağlantı alanına taşınmaz).
 */
export function VerificationInput({ disabled = false, busy = false, readOnly = false, onEdit, onSubmit, examples }: Props) {
  const [mode, setMode] = useState<InputMode>("text");
  const [values, setValues] = useState<Record<InputMode, string>>({ text: "", url: "" });
  const value = values[mode];
  const [error, setError] = useState<string | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const urlRef = useRef<HTMLInputElement>(null);
  const uid = useId();
  const fieldId = `${uid}-field`;
  const hintId = `${uid}-hint`;
  const errId = `${uid}-err`;

  function submit(m: InputMode, v: string) {
    if (disabled || busy || readOnly) return;
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

  /** Yazılan değeri o sekmeye kaydeder; yazmaya başlayınca eski hata mesajı kalkar. */
  function setValue(next: string, m: InputMode = mode) {
    setValues((prev) => ({ ...prev, [m]: next }));
    if (error) setError(null);
  }

  // Örnekler iki grupta gösterilir: sonuç türleri (herkes için) ve geliştirici senaryoları (yalnızca geliştirmede gelir).
  const userExamples = (examples ?? []).filter((ex) => !ex.dev);
  const devExamples = (examples ?? []).filter((ex) => ex.dev);
  const exampleItem = (ex: ExampleInput) => (
    <li key={ex.label}>
      <button
        type="button"
        className="link-btn"
        disabled={disabled}
        onClick={() => {
          setMode(ex.mode);
          setValue(ex.content, ex.mode);
          setError(null);
          submit(ex.mode, ex.content);
        }}
      >
        {ex.label}
      </button>
    </li>
  );

  const isText = mode === "text";
  const length = value.trim().length;
  const describedBy = error ? `${hintId} ${errId}` : hintId;

  return (
    <form
      className="verification-form"
      aria-busy={busy}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit(mode, value);
      }}
    >
      <fieldset className="modes-set" disabled={disabled || readOnly}>
        <legend className="sr-only">Girdi türü</legend>
        {/* Grup adı fieldset + legend ile verilir; ikinci bir radiogroup etiketi aynı adı iki kez okuturdu. */}
        <div className="modes">
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
        {isText ? "İncelenecek metin" : "İncelenecek haberin bağlantısı"}
      </label>

      {isText ? (
        <textarea
          ref={textRef}
          id={fieldId}
          className="field"
          rows={5}
          value={value}
          disabled={disabled}
          readOnly={readOnly}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder="Haber metni, paylaşım ya da tek bir iddia yapıştırın."
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
          readOnly={readOnly}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder="https://ornek.com/haber"
        />
      )}

      <div className="field-foot">
        <p id={hintId} className="field-hint">
          {isText
            ? `En fazla ${MAX_INPUT_LENGTH.toLocaleString("tr-TR")} karakter. İddialar ayrı ayrı incelenir.`
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
        {readOnly ? (
          <button key="edit" type="button" className="btn btn-quiet" onClick={(event) => {
            event.preventDefault();
            onEdit?.();
          }}>İçeriği düzenle</button>
        ) : (
          <button key="submit" type="submit" className="btn" disabled={disabled || busy}>
            {busy && <span className="activity-indicator" aria-hidden="true" />}
            {busy ? "İnceleniyor…" : "İncelemeyi başlat"}
            {!busy && <span aria-hidden="true">→</span>}
          </button>
        )}
      </div>

      {!readOnly && userExamples.length > 0 && (
        <div className="examples">
          <p className="t-meta muted">Örnek deneyin (örnek veri):</p>
          <ul className="examples-list">{userExamples.map(exampleItem)}</ul>
        </div>
      )}
      {!readOnly && devExamples.length > 0 && (
        <div className="examples examples--dev">
          <p className="t-meta muted">Geliştirici senaryoları (yayındaki sitede görünmez):</p>
          <ul className="examples-list">{devExamples.map(exampleItem)}</ul>
        </div>
      )}
    </form>
  );
}
