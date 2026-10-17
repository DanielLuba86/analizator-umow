import type { Analysis, AnalysisStatus, Finding, FragmentDto, RiskLevel } from "../api/types";
import { quarantineReason } from "./quarantine";

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  queued: "w kolejce",
  running: "w toku",
  done: "zakończona",
  failed: "nieudana",
  quarantined: "w kwarantannie",
  budget_exceeded: "przekroczony budżet",
};

const RISK_ORDER: Record<RiskLevel, number> = { wysokie: 0, średnie: 1, niskie: 2 };

function riskRank(f: Finding): number {
  return f.poziom_ryzyka === null ? 3 : RISK_ORDER[f.poziom_ryzyka];
}

/** Raport jest ukryty, dopóki wniosek o zwolnienie z kwarantanny nie zostanie zatwierdzony. */
export function isReportHidden(a: Analysis): boolean {
  return a.quarantine !== null && a.quarantine.status !== "zatwierdzona";
}

type Props = {
  analysis: Analysis;
  fragments: FragmentDto[];
  selectedId?: number | null;
  onSelect?: (findingId: number) => void;
  /** Ponowne pobranie raportu, np. gdy prawnik zatwierdzi wniosek o zwolnienie z kwarantanny. */
  onRefresh?: () => void;
};

export function RiskReport({ analysis, fragments, selectedId = null, onSelect, onRefresh }: Props) {
  const labels = new Map(fragments.map((f) => [f.id, f.label]));
  const hidden = isReportHidden(analysis);
  const findings = [...analysis.findings].sort((a, b) => riskRank(a) - riskRank(b) || a.id - b.id);

  return (
    <section className="report card" aria-label="Raport ryzyka">
      <p className="status">
        Status analizy: <strong className={`pill status-${analysis.status}`}>{STATUS_LABELS[analysis.status]}</strong>
        {analysis.official && " · oficjalna opinia"}
      </p>
      {hidden && (
        <p role="alert" className="banner quarantine">
          Analiza jest w kwarantannie: {quarantineReason(analysis.reason)}. Wyniki pozostaną ukryte, dopóki prawnik nie
          zatwierdzi wniosku o ich udostępnienie.
          {analysis.quarantine?.status === "odrzucona" && " Wniosek został odrzucony."}
          {onRefresh && (
            <>
              {" "}
              <button type="button" onClick={onRefresh}>
                Odśwież
              </button>
            </>
          )}
        </p>
      )}
      {!hidden && analysis.incomplete && (
        <p className="banner incomplete">Wyniki niepełne — analiza nie dobiegła końca.</p>
      )}
      {!hidden && findings.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Typ</th>
                <th>Teza</th>
                <th>Cytat</th>
                <th>Poziom ryzyka</th>
                <th>Uzasadnienie</th>
                <th>Fragment</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr
                  key={f.id}
                  aria-selected={f.id === selectedId}
                  className={f.id === selectedId ? "selected" : undefined}
                  onClick={() => onSelect?.(f.id)}
                >
                  <td>{f.typ}</td>
                  <td>{f.teza}</td>
                  <td className="quote">{f.cytat}</td>
                  <td className={f.poziom_ryzyka ? `risk risk-${f.poziom_ryzyka}` : "risk"}>
                    {f.poziom_ryzyka ? <span className="pill">{f.poziom_ryzyka}</span> : "—"}
                  </td>
                  <td>{f.uzasadnienie}</td>
                  <td>{labels.get(f.fragment_id) ?? f.fragment_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!hidden && findings.length === 0 && analysis.status === "done" && <p>Brak tez.</p>}
    </section>
  );
}
