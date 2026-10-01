"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiRequestError } from "@/lib/errors";
import { checkInput } from "@/lib/api";
import type { ApiError, CheckRequest, CheckResult } from "@/lib/types";

/**
 * Arayüzün durum makinesi. Bir anda yalnızca bir durumdayız.
 *
 *   idle → submitting → (extracting_claims → retrieving_evidence → verifying) → completed | error
 *
 * Parantez içindeki üç aşama YALNIZCA backend gerçekten aşama bilgisi verirse kullanılır
 * (`onStage` ile). Bilgi gelmezse `submitting` içinde kalırız; sahte ilerleme gösterilmez.
 */
export type BusyPhase = "submitting" | "extracting_claims" | "retrieving_evidence" | "verifying";

export type AnalysisState =
  | { phase: "idle" }
  | { phase: BusyPhase }
  | { phase: "completed"; result: CheckResult; input: string }
  | { phase: "error"; error: ApiError };

export type AnalysisAction =
  | { type: "start" }
  | { type: "stage"; phase: Exclude<BusyPhase, "submitting"> }
  | { type: "done"; result: CheckResult; input: string }
  | { type: "fail"; error: ApiError }
  | { type: "reset" };

export function isBusy(state: AnalysisState): state is { phase: BusyPhase } {
  return (
    state.phase === "submitting" ||
    state.phase === "extracting_claims" ||
    state.phase === "retrieving_evidence" ||
    state.phase === "verifying"
  );
}

export function analysisReducer(state: AnalysisState, action: AnalysisAction): AnalysisState {
  switch (action.type) {
    case "start":
      return { phase: "submitting" };
    case "stage":
      // Aşama bilgisi yalnızca devam eden bir istekte anlamlıdır; geç gelen bilgi yok sayılır.
      return isBusy(state) ? { phase: action.phase } : state;
    case "done":
      return { phase: "completed", result: action.result, input: action.input };
    case "fail":
      return { phase: "error", error: action.error };
    case "reset":
      return { phase: "idle" };
  }
}

export function useAnalysis() {
  const [state, dispatch] = useReducer(analysisReducer, { phase: "idle" });
  // Her yeni analizde artar; eski analizin gecikmiş cevabını yok saymak için.
  const runId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const lastRequest = useRef<CheckRequest | null>(null);

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
      const result = await checkInput(req, ctrl.signal, (phase) => {
        if (runId.current === myRun) dispatch({ type: "stage", phase });
      });
      if (runId.current !== myRun) return;
      dispatch({ type: "done", result, input: req.content });
    } catch (err) {
      if (runId.current !== myRun) return;
      const apiErr =
        err instanceof ApiRequestError
          ? err.toApiError()
          : ({ code: "INTERNAL_ERROR", message: "Beklenmeyen bir hata oluştu." } as ApiError);
      dispatch({ type: "fail", error: apiErr });
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

  return { state, start, retry, reset };
}
