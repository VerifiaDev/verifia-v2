"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiRequestError } from "@/lib/errors";
import { checkInput } from "@/lib/api";
import type { ApiError, CheckRequest, CheckResult } from "@/lib/types";

/**
 * Arayüzün durum makinesi. Bir anda yalnızca bir durumdayız:
 * idle → loading → completed | error   (tek istek; ara aşama bilgisi yok)
 *
 * Backend ileride aşama bilgisi (extracting_claims, retrieving_evidence, verifying) verirse
 * `loading` durumuna bir `stage` alanı eklenir; AnalysisProgress buna hazırdır.
 */
export type AnalysisState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "completed"; result: CheckResult; input: string }
  | { phase: "error"; error: ApiError };

type Action =
  | { type: "start" }
  | { type: "done"; result: CheckResult; input: string }
  | { type: "fail"; error: ApiError }
  | { type: "reset" };

function reducer(_state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case "start":
      return { phase: "loading" };
    case "done":
      return { phase: "completed", result: action.result, input: action.input };
    case "fail":
      return { phase: "error", error: action.error };
    case "reset":
      return { phase: "idle" };
  }
}

export function useAnalysis() {
  const [state, dispatch] = useReducer(reducer, { phase: "idle" });
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
      const result = await checkInput(req, ctrl.signal);
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
