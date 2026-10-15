import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import { apiFetch, errorMessage, postJson } from "../api/client";
import {
  CONTRACT_KINDS,
  CONTRACT_SOURCES,
  type ContractCreated,
  type ContractKind,
  type ContractListItem,
  type ContractSource,
} from "../api/types";
import { navigate } from "../router";
import { readTextFile } from "./textFile";

export function ContractsPage() {
  const [contracts, setContracts] = useState<ContractListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<ContractListItem[]>("/api/contracts")
      .then((c) => active && setContracts(c))
      .catch((e) => active && setError(errorMessage(e)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="contracts">
      <h2>Umowy</h2>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {contracts === null && !error && <p>Ładowanie…</p>}
      {contracts !== null && contracts.length === 0 && <p>Brak umów.</p>}
      {contracts !== null && contracts.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Tytuł</th>
              <th>Rodzaj</th>
              <th>Źródło</th>
              <th>Wersje</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => (
              <tr key={c.id}>
                <td>
                  <a href={`#/contracts/${c.id}`}>{c.title}</a>
                </td>
                <td>{c.kind}</td>
                <td>{c.source}</td>
                <td>{c.versions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <NewContractForm />
    </section>
  );
}

function NewContractForm() {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<ContractKind>("najem");
  const [source, setSource] = useState<ContractSource>("kontrahent");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setText(await readTextFile(file));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się odczytać pliku.");
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { id } = await postJson<ContractCreated>("/api/contracts", { title, kind, source, text });
      navigate(`/contracts/${id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="new-contract" onSubmit={onSubmit}>
      <h3>Nowa umowa</h3>
      <label>
        Tytuł
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} required />
      </label>
      <label>
        Rodzaj
        <select value={kind} onChange={(e) => setKind(e.target.value as ContractKind)}>
          {CONTRACT_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </label>
      <label>
        Źródło
        <select value={source} onChange={(e) => setSource(e.target.value as ContractSource)}>
          {CONTRACT_SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label>
        Plik (.md, .txt)
        <input type="file" accept=".md,.txt,text/markdown,text/plain" onChange={onFile} />
      </label>
      <label>
        Tekst umowy
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} required />
      </label>
      <button type="submit" disabled={busy}>
        Dodaj umowę
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}
