"use client";

import { useId, useRef, useState } from "react";
import { MAX_INPUT_LENGTH } from "@/lib/config";
import { LEGAL_COMPLETE, PRIVACY_PATH } from "@/lib/legal";
import { INPUT_MODES } from "@/lib/format";
import { isSubmitShortcut, validateInput } from "@/lib/input";
import type { ExampleInput } from "@/lib/api";
import type { CheckRequest, InputMode } from "@/lib/types";

interface Props {
  disabled?: boolean;
  unavailable?: boolean;
  localOnly?: boolean;
  busy?: boolean;
  readOnly?: boolean;
  onEdit?: () => void;
  onSubmit: (req: CheckRequest) => void;
  /**
   * Servisin durumunu açıklayan notun kimliği; giriş alanı bu nota bağlanır.
   */
  noticeId?: string;
  /** Servis bağlantıyla incelemeyi desteklemiyorsa false: "Metin / Bağlantı" seçimi hiç gösterilmez. */
  urlSupported?: boolean;
  /** Hata gösterilirken true: gönder düğmesi ikincil görünür; ekranda tek birincil eylem (hata panelindeki) kalır. */
  demoteSubmit?: boolean;
  /** Örnek kullanım (yalnızca örnek veri modunda). */
  examples?: ExampleInput[];
}

/** Sınırın bu oranına gelince sayaç vurgulanır. */
const NEAR_LIMIT = 0.9;

/**
 * Giriş alanı: Metin / Bağlantı seçimi, doğrulama ve gönder.
 * İnceleme bitince (`readOnly`) form yerine tek satırlık özet ve "İçeriği düzenle" gösterilir.
 * Hata mesajı alanın hemen altında, alana `aria-describedby` ile bağlı gösterilir.
 * Değerler bu bileşende tutulur; hata ya da yeniden deneme sırasında kaybolmaz.
 * Metin ve Bağlantı sekmelerinin değerleri ayrı tutulur (metin, bağlantı alanına taşınmaz).
 */
export function VerificationInput({
  disabled = false,
  unavailable = false,
  localOnly = false,
  busy = false,
  readOnly = false,
  onEdit,
  onSubmit,
  noticeId,
  urlSupported = true,
  demoteSubmit = false,
  examples,
}: Props) {
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
  const privacyId = `${uid}-privacy`;

  function submit(m: InputMode, v: string) {
    if (disabled || unavailable || busy || readOnly) return;
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
  const describedBy = [hintId, privacyId, error ? errId : null, noticeId].filter(Boolean).join(" ");
  const countState = length > MAX_INPUT_LENGTH ? "over" : length >= MAX_INPUT_LENGTH * NEAR_LIMIT ? "near" : "ok";
  const limit = MAX_INPUT_LENGTH.toLocaleString("tr-TR");

  if (readOnly) {
    return (
      <div className="input-summary">
        <div className="input-summary-text">
          <p className="t-meta muted">{isText ? "İncelenen metin" : "İncelenen bağlantı"}</p>
          <p className="input-summary-value">{value}</p>
        </div>
        <button type="button" className="btn btn-quiet" onClick={() => onEdit?.()}>
          İçeriği düzenle
        </button>
      </div>
    );
  }

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
      {urlSupported && (
        <fieldset className="modes-set" disabled={disabled}>
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
      )}

      <label htmlFor={fieldId} className="field-label t-h4">
        {isText ? "Haber metnini yapıştır" : "İncelenecek haberin bağlantısı"}
      </label>

      {isText ? (
        <textarea
          ref={textRef}
          id={fieldId}
          className="field"
          rows={5}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (!isSubmitShortcut({ key: e.key, ctrlKey: e.ctrlKey, metaKey: e.metaKey, isComposing: e.nativeEvent.isComposing })) return;
            e.preventDefault();
            submit(mode, value);
          }}
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
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          placeholder="https://ornek.com/haber"
        />
      )}

      <div className="field-foot">
        <p id={hintId} className="field-hint">
          {isText
            ? "İddialar ayrı ayrı incelenir."
            : "Haberin tam adresini girin. Sayfa açılamazsa haber metnini giriş alanına kopyalayabilirsiniz."}
          {/* Sınır görünür sayaçta yazar; ekran okuyucu için ipucunun parçası olarak da okunur. */}
          {isText && <span className="sr-only"> En fazla {limit} karakter.</span>}
        </p>
        {isText && (
          <p className="field-count tnum" data-state={countState} aria-hidden="true">
            {length.toLocaleString("tr-TR")} / {limit}
          </p>
        )}
        {error && (
          <p id={errId} className="field-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <p className="sr-only" role="status" aria-atomic="true">
        {isText && countState === "over" ? "Karakter sınırı aşıldı. Metni kısaltın." : isText && countState === "near" ? "Karakter sınırına yaklaşıyorsunuz." : ""}
      </p>
      {!unavailable && <div className="actions">
        <button
          type="submit"
          className={demoteSubmit ? "btn btn-quiet" : "btn"}
          disabled={disabled || busy}
          aria-describedby={[noticeId, privacyId].filter(Boolean).join(" ")}
          aria-keyshortcuts="Control+Enter Meta+Enter"
        >
          {busy ? "İnceleniyor…" : "İncelemeyi başlat"}
        </button>
      </div>}
      {/* Formdaki bilgilendirme (KVKK m.10): gönderimden önce, düğmenin hemen altında. Onay kutusu bilerek yok:
          metin, kullanıcının istediği hizmet için işlenir (m.5/2-c); gereksiz "rıza" istemek yanıltıcı olurdu.
          Metin alanına ve düğmeye bağlıdır (aria-describedby), ekran okuyucu da duyurur. */}
      <p id={privacyId} className="form-privacy t-meta muted">
        {!unavailable &&
          !localOnly &&
          "İncelemeyi başlattığınızda metniniz, inceleme sunucumuz üzerinden yurt dışındaki yapay zekâ (Groq) ve web araması (Tavily) servislerine gönderilir. Ad, telefon, adres, kimlik numarası gibi kişisel bilgileri eklemeyin. "}
        Metin ve sonuçlar kaydedilmez; sayfa yenilenince kaybolur.{" "}
        <a href={LEGAL_COMPLETE ? PRIVACY_PATH : "#gizlilik"}>{LEGAL_COMPLETE ? "Gizlilik politikası" : "Veri kullanımı"}</a>
      </p>

      {userExamples.length > 0 && (
        <div className="examples">
          <p className="t-meta muted">Örnek deneyin (örnek veri):</p>
          <ul className="examples-list">{userExamples.map(exampleItem)}</ul>
        </div>
      )}
      {devExamples.length > 0 && (
        <div className="examples examples--dev">
          <p className="t-meta muted">Geliştirici senaryoları (yayındaki sitede görünmez):</p>
          <ul className="examples-list">{devExamples.map(exampleItem)}</ul>
        </div>
      )}
    </form>
  );
}
