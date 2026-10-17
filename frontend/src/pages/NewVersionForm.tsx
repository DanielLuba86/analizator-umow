import { useState, type ChangeEvent, type FormEvent } from "react";

import { errorMessage, postJson } from "../api/client";
import type { VersionCreated } from "../api/types";
import { useBusy } from "../useBusy";
import { readTextFile } from "./textFile";

type Props = { contractId: number; onCreated: (versionId: number) => void };

export function NewVersionForm({ contractId, onCreated }: Props) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, guard] = useBusy();

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

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void guard(async () => {
      setError(null);
      try {
        const { version_id } = await postJson<VersionCreated>(`/api/contracts/${contractId}/versions`, { text });
        setText("");
        onCreated(version_id);
      } catch (err) {
        setError(errorMessage(err));
      }
    });
  }

  return (
    <form className="new-version card" onSubmit={onSubmit}>
      <h3>Nowa wersja</h3>
      <label>
        Plik (.md, .txt)
        <input type="file" accept=".md,.txt,text/markdown,text/plain" onChange={onFile} />
      </label>
      <label>
        Tekst nowej wersji
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} required />
      </label>
      <button type="submit" className="primary" disabled={busy}>
        Dodaj wersję
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}
