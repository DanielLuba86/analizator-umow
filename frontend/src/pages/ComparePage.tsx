import { useEffect, useState, type FormEvent } from "react";

import { apiFetch, errorMessage, postJson } from "../api/client";
import type { Comparison, Contract, FindingKey } from "../api/types";

export function ComparePage({ contractId }: { contractId: number }) {
  const [contract, setContract] = useState<Contract | null>(null);
  const [oldId, setOldId] = useState<number | null>(null);
  const [newId, setNewId] = useState<number | null>(null);
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    apiFetch<Contract>(`/api/contracts/${contractId}`)
      .then((c) => {
        if (!active) return;
        setContract(c);
        setOldId(c.versions.at(-2)?.id ?? c.versions[0]?.id ?? null);
        setNewId(c.versions.at(-1)?.id ?? null);
      })
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, [contractId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (oldId === null || newId === null) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await postJson<Comparison>("/api/comparisons", { version_a: oldId, version_b: newId }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (!contract) return error ? <p role="alert">{error}</p> : <p>Ładowanie…</p>;

  const versionSelect = (label: string, value: number | null, set: (id: number) => void) => (
    <label>
      {label}
      <select value={value ?? ""} onChange={(e) => set(Number(e.target.value))}>
        {contract.versions.map((v) => (
          <option key={v.id} value={v.id}>
            Wersja {v.nr}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <section className="compare card">
      <h2>Porównanie wersji: {contract.title}</h2>
      <p>
        <a href={`#/contracts/${contract.id}`}>← Wróć do umowy</a>
      </p>
      <form className="toolbar" onSubmit={onSubmit}>
        {versionSelect("Stara wersja", oldId, setOldId)}
        {versionSelect("Nowa wersja", newId, setNewId)}
        <button type="submit" className="primary" disabled={busy}>
          Porównaj
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && (
        <>
          <section aria-label="Zmienione fragmenty">
            <h3>Zmienione fragmenty</h3>
            {result.fragment_changes.length === 0 && <p>Brak zmian w treści.</p>}
            {result.fragment_changes.map((c) => (
              <article key={`${c.kind}-${c.label}`} className={`change change-${c.kind}`}>
                <h4>
                  {c.label} — {c.kind}
                </h4>
                <div className="side-by-side">
                  <pre aria-label="Stary tekst">{c.old_text ?? ""}</pre>
                  <pre aria-label="Nowy tekst">{c.new_text ?? ""}</pre>
                </div>
              </article>
            ))}
          </section>
          <section aria-label="Zmiany tez">
            <h3>Zmiany tez</h3>
            {result.finding_changes === null ? (
              <p>Zmian tez nie pokazano: obie wersje muszą mieć zakończoną analizę.</p>
            ) : (
              <>
                <FindingKeyList label="Nowe tezy" keys={result.finding_changes.nowe} />
                <FindingKeyList label="Tezy, które ustąpiły" keys={result.finding_changes.ustąpiło} />
              </>
            )}
          </section>
        </>
      )}
    </section>
  );
}

function FindingKeyList({ label, keys }: { label: string; keys: FindingKey[] }) {
  return (
    <>
      <h4>{label}</h4>
      {keys.length === 0 ? (
        <p>Brak.</p>
      ) : (
        <ul aria-label={label}>
          {keys.map((k) => (
            <li key={`${k.typ}|${k.label}|${k.cytat}`}>
              {k.typ} · {k.label}: <q>{k.cytat}</q>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
