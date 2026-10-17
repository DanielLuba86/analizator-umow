import { useCallback, useEffect, useState } from "react";

import { apiFetch, errorMessage, postJson } from "../api/client";
import { FINAL_STATUSES, type AnalysisStarted, type Contract, type PendingAction, type Version } from "../api/types";
import { DocumentView } from "../document/DocumentView";
import { RiskReport, STATUS_LABELS, isReportHidden } from "../document/RiskReport";
import { useAnalysis } from "../document/useAnalysis";
import { useBusy } from "../useBusy";
import { NewVersionForm } from "./NewVersionForm";

type Props = { contractId: number; versionId?: number; analysisId?: number };

export function ContractPage({ contractId, versionId, analysisId }: Props) {
  const [contract, setContract] = useState<Contract | null>(null);
  const [version, setVersion] = useState<Version | null>(null);
  const [chosenAnalysis, setChosenAnalysis] = useState<number | null>(analysisId ?? null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, guard] = useBusy();
  const [contractTick, setContractTick] = useState(0);

  useEffect(() => {
    let active = true;
    apiFetch<Contract>(`/api/contracts/${contractId}`)
      .then((c) => active && setContract(c))
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [contractId, contractTick]);

  const currentVersionId = versionId ?? contract?.versions.at(-1)?.id ?? null;

  const loadVersion = useCallback(async (id: number) => {
    const v = await apiFetch<Version>(`/api/versions/${id}`);
    setVersion(v);
    return v;
  }, []);

  useEffect(() => {
    if (currentVersionId === null) return;
    let active = true;
    setVersion(null);
    setSelected(null);
    loadVersion(currentVersionId)
      .then((v) => {
        if (!active) return;
        const requested = v.analyses.find((a) => a.id === analysisId);
        setChosenAnalysis(requested?.id ?? v.analyses[0]?.id ?? null);
      })
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [currentVersionId, analysisId, loadVersion]);

  const { analysis, error: analysisError, reload } = useAnalysis(chosenAnalysis);

  function startAnalysis() {
    if (!version) return;
    void guard(async () => {
      setError(null);
      try {
        const { analysis_id } = await postJson<AnalysisStarted>(`/api/versions/${version.id}/analyses`, {});
        setChosenAnalysis(analysis_id);
        setSelected(null);
        await loadVersion(version.id);
      } catch (e) {
        setError(errorMessage(e));
      }
    });
  }

  if (!contract) {
    return error ? <p role="alert">{error}</p> : <p>Ładowanie…</p>;
  }

  const hidden = analysis ? isReportHidden(analysis) : true;
  const final = analysis ? FINAL_STATUSES.includes(analysis.status) : false;

  return (
    <section className="contract">
      <div className="page-head">
        <h2>{contract.title}</h2>
        <p className="meta">
          Rodzaj: {contract.kind} · Źródło: {contract.source}
        </p>
      </div>
      <nav className="versions" aria-label="Wersje">
        {contract.versions.map((v) => (
          <a
            key={v.id}
            href={`#/contracts/${contract.id}/versions/${v.id}`}
            aria-current={v.id === currentVersionId ? "page" : undefined}
          >
            Wersja {v.nr}
          </a>
        ))}
        {contract.versions.length > 1 && <a href={`#/contracts/${contract.id}/compare`}>Porównaj wersje</a>}
      </nav>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {version && (
        <>
          <div className="toolbar">
            <span data-testid="loaded-version">Wersja {version.nr}</span>
            <button type="button" className="primary" onClick={startAnalysis} disabled={busy}>
              Uruchom analizę
            </button>
            {version.analyses.length > 0 && (
              <label>
                Analiza
                <select
                  value={chosenAnalysis ?? ""}
                  onChange={(e) => {
                    setChosenAnalysis(Number(e.target.value));
                    setSelected(null);
                  }}
                >
                  {version.analyses.map((a) => (
                    <option key={a.id} value={a.id}>
                      #{a.id} — {STATUS_LABELS[a.id === analysis?.id ? analysis.status : a.status]}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {analysisError && (
            <p role="alert" className="error">
              {analysisError}
            </p>
          )}
          <div className="workspace">
            <DocumentView
              text={version.text}
              findings={analysis && !hidden ? analysis.findings : []}
              selectedId={selected}
              onSelect={setSelected}
            />
            {analysis && (
              <div className="side">
                <RiskReport
                  analysis={analysis}
                  fragments={version.fragments}
                  selectedId={selected}
                  onSelect={setSelected}
                  onRefresh={reload}
                />
                {final && !hidden && <AnalysisActions analysisId={analysis.id} />}
              </div>
            )}
          </div>
        </>
      )}

      <NewVersionForm
        contractId={contract.id}
        onCreated={(vid) => {
          setContractTick((t) => t + 1);
          window.location.hash = `#/contracts/${contract.id}/versions/${vid}`;
        }}
      />
    </section>
  );
}

const USER_ACTIONS = [
  { typ: "eksport", label: "Wnioskuj o eksport" },
  { typ: "opinia", label: "Wnioskuj o oficjalną opinię" },
] as const;

const ACTION_STATUS_LABELS = { oczekuje: "oczekuje", zatwierdzona: "zatwierdzony", odrzucona: "odrzucony" };

function AnalysisActions({ analysisId }: { analysisId: number }) {
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    apiFetch<PendingAction[]>(`/api/actions?analysis_id=${analysisId}`)
      .then((list) => active && setActions(list))
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [analysisId, tick]);

  async function request(typ: "eksport" | "opinia") {
    setError(null);
    try {
      await postJson(`/api/analyses/${analysisId}/actions`, { typ });
      setTick((t) => t + 1);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <section className="actions card" aria-label="Wnioski">
      <h3>Wnioski</h3>
      <div className="toolbar">
        {USER_ACTIONS.map((a) => (
          <button key={a.typ} type="button" onClick={() => request(a.typ)}>
            {a.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <ul>
        {actions.map((a) => (
          <li key={a.id}>
            #{a.id}: {a.typ} — {ACTION_STATUS_LABELS[a.status]}
            {a.export_id !== null && (
              <>
                {" "}
                <a href={`/api/exports/${a.export_id}`} download>
                  Pobierz eksport (JSON)
                </a>{" "}
                <a href={`/api/exports/${a.export_id}/pdf`} download>
                  Pobierz PDF
                </a>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
