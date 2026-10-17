"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiRequestError, checkInput, sampleResult, warmUp } from "@/lib/api";
import type { AnalysisStage, ApiError, CheckRequest, CheckResult } from "@/lib/types";

/**
 * Arayüzün durum makinesi. Bir anda yalnızca bir durumdayız.
 *
 *   idle → submitting → (extracting_claims → retrieving_evidence → verifying) → completed | error
 *
 * Parantez içindeki üç aşama YALNIZCA backend gerçekten aşama bilgisi verirse kullanılır
 * (`onStage` ile). Bilgi gelmezse `submitting` içinde kalırız; sahte ilerleme gösterilmez.
 */
/**
 * `waiting_server`: istek gönderildi ama sunucu sağlık denetimine henüz yanıt vermedi (uyuyor ya da meşgul).
 * Bu sırada hiçbir şey incelenmiyor; arayüz "inceleniyor" yerine bunu söyler. Gerçek bilgidir, tahmin değildir.
 */
export type BusyPhase = "submitting" | "waiting_server" | AnalysisStage;

export type AnalysisState =
  | { phase: "idle" }
  | { phase: BusyPhase }
  /** `sample`: sonuç gerçek bir inceleme değil, sabit örnek (servis bağlı değilken gösterilir). */
  | { phase: "completed"; result: CheckResult; sample?: boolean }
  | { phase: "error"; error: ApiError };

export type AnalysisAction =
  | { type: "start" }
  | { type: "stage"; phase: AnalysisStage }
  | { type: "server_wait"; waiting: boolean }
  | { type: "done"; result: CheckResult; sample?: boolean }
  | { type: "fail"; error: ApiError }
  | { type: "reset" };

export function isBusy(state: AnalysisState): state is { phase: BusyPhase } {
  return (
    state.phase === "submitting" ||
    state.phase === "waiting_server" ||
    state.phase === "extracting_claims" ||
    state.phase === "retrieving_evidence" ||
    state.phase === "verifying"
  );
}

/**
 * "Kaynaklı örnek raporu aç" girişi gösterilsin mi? Sonuç ekrandayken gösterilmez: örnek, tek sonuç durumunun
 * üzerine yazar ve gerçek sonuç hiçbir yerde saklanmadığı için kullanıcı incelemeyi baştan başlatmak zorunda kalırdı.
 * Örnek açıkken de yinelenmez. "Yeni bir içerik incele" ya da "Örneği kapat" sonrası giriş geri gelir.
 */
export function sampleEntryVisible(state: AnalysisState): boolean {
  return state.phase !== "completed";
}

export function analysisReducer(state: AnalysisState, action: AnalysisAction): AnalysisState {
  switch (action.type) {
    case "start":
      return { phase: "submitting" };
    case "stage":
      // Aşama bilgisi yalnızca devam eden bir istekte anlamlıdır; geç gelen bilgi yok sayılır.
      return isBusy(state) ? { phase: action.phase } : state;
    case "server_wait":
      // Yalnızca inceleme henüz başlamamışken anlamlıdır; geç gelen bildirim başka bir durumu ezmez.
      if (state.phase !== "submitting" && state.phase !== "waiting_server") return state;
      return { phase: action.waiting ? "waiting_server" : "submitting" };
    case "done":
      return action.sample
        ? { phase: "completed", result: action.result, sample: true }
        : { phase: "completed", result: action.result };
    case "fail":
      return { phase: "error", error: action.error };
    case "reset":
      return { phase: "idle" };
  }
}

/**
 * Yakalanan hatayı arayüzün hata tipine çevirir. Tarayıcı çevrimdışı olduğunu bildiriyorsa ağ hatası
 * "internet bağlantısı yok" olarak gösterilir (sunucuyu suçlamak yanlış olurdu).
 */
export function toApiError(err: unknown, online: boolean): ApiError {
  if (!(err instanceof ApiRequestError)) return { code: "INTERNAL_ERROR", message: "Beklenmeyen bir hata oluştu." };
  if (err.code === "NETWORK" && !online) return { code: "OFFLINE", message: "Cihaz çevrimdışı." };
  return err.toApiError();
}

export function useAnalysis() {
  const [state, dispatch] = useReducer(analysisReducer, { phase: "idle" });
  // Her yeni analizde artar; eski analizin gecikmiş cevabını yok saymak için.
  const runId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const lastRequest = useRef<CheckRequest | null>(null);

  // Sayfa açılınca sunucu uyandırılır; kullanıcı metnini yapıştırana kadar açılmış olur. Kota harcamaz; yalnızca gerçek servis bağlıyken istek gider.
  useEffect(() => {
    warmUp();
  }, []);

  useEffect(() => {
    return () => {
      runId.current += 1;
      controller.current?.abort(); // sayfa kapanınca istek dursun
    };
  }, []);

  /** Girdi çağıran tarafta (VerificationInput) doğrulanmış olmalıdır. */
  const start = useCallback(async (req: CheckRequest) => {
    lastRequest.current = req;
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    const myRun = ++runId.current;
    dispatch({ type: "start" });

    try {
      const result = await checkInput(
        req,
        ctrl.signal,
        (phase) => {
          if (runId.current === myRun) dispatch({ type: "stage", phase });
        },
        (waiting) => {
          if (runId.current === myRun) dispatch({ type: "server_wait", waiting });
        },
      );
      if (runId.current !== myRun) return;
      dispatch({ type: "done", result });
    } catch (err) {
      if (runId.current !== myRun) return;
      const online = typeof navigator === "undefined" ? true : navigator.onLine;
      dispatch({ type: "fail", error: toApiError(err, online) });
    }
  }, []);

  /** Son gönderilen isteği aynen yeniden dener. */
  const retry = useCallback(() => {
    if (lastRequest.current) void start(lastRequest.current);
  }, [start]);

  /** Devam eden isteği iptal eder ve başa döner. */
  const reset = useCallback(() => {
    runId.current += 1;
    controller.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  /** Sabit örnek sonucu gösterir (istek gönderilmez). */
  const showSample = useCallback(() => {
    runId.current += 1;
    controller.current?.abort();
    dispatch({ type: "done", result: sampleResult(), sample: true });
  }, []);

  return { state, start, retry, reset, showSample };
}
