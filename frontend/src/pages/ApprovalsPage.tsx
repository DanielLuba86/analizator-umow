import { useEffect, useState } from "react";

import { ApiError, apiFetch, errorMessage, postJson } from "../api/client";
import type { Decision, PendingAction } from "../api/types";

const ALREADY_DECIDED = "Wniosek został już rozstrzygnięty.";

/** Opis wniosku jako zwykły tekst; uzasadnienie agenta bywa ukryte, dopóki raport jest niewidoczny. */
function describe(a: PendingAction): string {
  const p = a.payload;
  if (a.typ === "kwarantanna") return `Powód: ${String(p["powód"] ?? "nieznany")}`;
  if (p.zrodlo === "agent") {
    return p.ukryte
      ? "Uzasadnienie agenta ukryte do czasu zwolnienia raportu z kwarantanny."
      : `Uzasadnienie agenta: ${String(p.uzasadnienie ?? "")}`;
  }
  return "Wniosek użytkownika.";
}

export function ApprovalsPage() {
  const [actions, setActions] = useState<PendingAction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<PendingAction[]>("/api/actions?status=oczekuje")
      .then((a) => active && setActions(a))
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, []);

  const remove = (id: number) => setActions((prev) => prev?.filter((a) => a.id !== id) ?? null);

  async function decide(id: number, body: object) {
    setError(null);
    try {
      await postJson<Decision>(`/api/actions/${id}/decision`, body);
      remove(id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(ALREADY_DECIDED);
        remove(id);
      } else {
        setError(errorMessage(e));
      }
    }
  }

  return (
    <section className="approvals">
      <h2>Wnioski do zatwierdzenia</h2>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {actions === null && !error && <p>Ładowanie…</p>}
      {actions !== null && actions.length === 0 && <p>Brak oczekujących wniosków.</p>}
      {actions !== null && actions.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Nr</th>
              <th>Typ</th>
              <th>Analiza</th>
              <th>Szczegóły</th>
              <th>Decyzja</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((a) => (
              <ActionRow key={a.id} action={a} onDecide={(body) => decide(a.id, body)} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function ActionRow({ action, onDecide }: { action: PendingAction; onDecide: (body: object) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const isTemplate = action.typ === "wzorzec";
  const templateReady = name.trim() !== "" && text.trim() !== "";

  async function run(approve: boolean) {
    setBusy(true);
    try {
      await onDecide(
        approve && isTemplate ? { approve, template: { nazwa_klauzuli: name, tresc: text } } : { approve },
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr>
      <td>#{action.id}</td>
      <td>{action.typ}</td>
      <td>
        <a href={`#/analyses/${action.analysis_id}`}>Analiza #{action.analysis_id}</a>
      </td>
      <td>
        <p>{describe(action)}</p>
        {isTemplate && (
          <div className="template-form">
            <label>
              Nazwa klauzuli
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
            </label>
            <label>
              Treść klauzuli
              <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={20000} rows={4} />
            </label>
          </div>
        )}
      </td>
      <td className="decision">
        <button type="button" disabled={busy || (isTemplate && !templateReady)} onClick={() => run(true)}>
          Zatwierdź
        </button>
        <button type="button" disabled={busy} onClick={() => run(false)}>
          Odrzuć
        </button>
      </td>
    </tr>
  );
}
