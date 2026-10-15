import { useEffect, useState } from "react";

import { apiFetch, errorMessage } from "../api/client";
import type { Analysis, Version } from "../api/types";
import { navigate } from "../router";

/** "#/analyses/:id" (link z kolejki wniosków) → strona umowy z tą wersją i analizą. */
export function AnalysisRedirect({ analysisId }: { analysisId: number }) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const a = await apiFetch<Analysis>(`/api/analyses/${analysisId}`);
      const v = await apiFetch<Version>(`/api/versions/${a.version_id}`);
      if (active) navigate(`/contracts/${v.contract_id}/versions/${v.id}/analyses/${a.id}`);
    })().catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [analysisId]);

  return error ? <p role="alert">{error}</p> : <p>Ładowanie…</p>;
}
