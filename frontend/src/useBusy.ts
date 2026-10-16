import { useCallback, useRef, useState } from "react";

/**
 * Blokada akcji na czas żądania. Stan `busy` wyłącza przycisk dopiero po renderze, więc
 * szybkie podwójne kliknięcie przeszłoby dwa razy — ref odrzuca drugie wywołanie od razu.
 */
export function useBusy(): [boolean, (fn: () => Promise<void>) => Promise<void>] {
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const run = useCallback(async (fn: () => Promise<void>) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    try {
      await fn();
    } finally {
      running.current = false;
      setBusy(false);
    }
  }, []);
  return [busy, run];
}
