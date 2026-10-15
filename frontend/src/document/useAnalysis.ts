import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch, errorMessage } from "../api/client";
import { FINAL_STATUSES, type Analysis } from "../api/types";

export const POLL_MS = 2000;

/** Pobiera raport analizy i odpytuje co 2 s, aż status będzie końcowy. */
export function useAnalysis(id: number | null) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  // Inna analiza: nie pokazuj poprzedniego raportu, zanim przyjdzie nowy.
  useEffect(() => {
    setAnalysis(null);
    setError(null);
  }, [id]);

  useEffect(() => {
    if (id === null) {
      setAnalysis(null);
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const a = await apiFetch<Analysis>(`/api/analyses/${id}`);
        if (!active) return;
        setAnalysis(a);
        setError(null);
        if (!FINAL_STATUSES.includes(a.status)) timer = setTimeout(load, POLL_MS);
      } catch (e) {
        if (!active) return;
        setError(errorMessage(e));
        // Błąd przejściowy (sieć, 5xx) nie zatrzymuje odpytywania; 4xx się nie zmieni.
        const transient = !(e instanceof ApiError) || e.status >= 500;
        if (transient) timer = setTimeout(load, POLL_MS);
      }
    };
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, tick]);

  return { analysis, error, reload };
}
