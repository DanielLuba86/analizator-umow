import { useMemo } from "react";

import type { Finding } from "../api/types";
import { toSegments } from "./segments";

type Props = {
  text: string;
  findings: Finding[];
  selectedId?: number | null;
  onSelect?: (findingId: number) => void;
};

/** Treść umowy wyłącznie jako węzły tekstowe Reacta — nigdy HTML ani markdown. */
export function DocumentView({ text, findings, selectedId = null, onSelect }: Props) {
  const segments = useMemo(
    () => toSegments(text, findings.map((f) => ({ id: f.id, start: f.start, end: f.end }))),
    [text, findings],
  );

  return (
    <pre className="document" aria-label="Treść umowy">
      {segments.map((s, i) => {
        if (s.findingIds.length === 0) return <span key={i}>{s.text}</span>;
        const selected = selectedId !== null && s.findingIds.includes(selectedId);
        const select = () => onSelect?.(selected && selectedId !== null ? selectedId : s.findingIds[0]);
        return (
          <mark
            key={i}
            data-finding-ids={s.findingIds.join(" ")}
            className={selected ? "selected" : undefined}
            role="button"
            tabIndex={0}
            onClick={select}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                select();
              }
            }}
          >
            {s.text}
          </mark>
        );
      })}
    </pre>
  );
}
