import { act, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";

import type { Analysis, Finding } from "../src/api/types";
import { DocumentView } from "../src/document/DocumentView";
import { RiskReport } from "../src/document/RiskReport";
import { useAnalysis } from "../src/document/useAnalysis";
import { mockFetch } from "./helpers";

const TEXT = "§ 1. Kary\nNajemca zapłaci karę umowną 600 zł za dzień.";
const QUOTE = "zapłaci karę umowną 600 zł";

function finding(over: Partial<Finding> = {}): Finding {
  const start = TEXT.indexOf(QUOTE);
  return {
    id: 1,
    typ: "kara",
    teza: "Wysoka kara dzienna",
    cytat: QUOTE,
    fragment_id: "f001",
    start,
    end: start + QUOTE.length,
    poziom_ryzyka: "wysokie",
    uzasadnienie: "Kara rażąco wygórowana.",
    template_id: null,
    ...over,
  };
}

function analysis(over: Partial<Analysis> = {}): Analysis {
  return {
    id: 5,
    version_id: 1,
    status: "done",
    reason: null,
    turns: 3,
    cost_usd: 0.02,
    incomplete: false,
    official: false,
    quarantine: null,
    findings: [finding()],
    ...over,
  };
}

const FRAGMENTS = [{ id: "f001", label: "§ 1", start: 0, end: TEXT.length }];

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("contract text with <script> renders as literal text", () => {
  render(<DocumentView text={"<script>alert(1)</script>"} findings={[]} />);
  expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  expect(document.querySelector("script")).toBeNull();
});

test("agent text with markup renders as literal text", () => {
  const evil = finding({ teza: "<img src=x onerror=alert(1)>", uzasadnienie: "**pogrubione**" });
  render(<RiskReport analysis={analysis({ findings: [evil] })} fragments={FRAGMENTS} />);
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(screen.getByText("**pogrubione**")).toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
});

test("quote range is highlighted with finding ids", () => {
  render(<DocumentView text={TEXT} findings={[finding()]} />);
  const mark = document.querySelector("mark");
  expect(mark).toHaveTextContent(QUOTE);
  expect(mark).toHaveAttribute("data-finding-ids", "1");
});

test("clicking a highlight selects the finding in the report", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  render(<DocumentView text={TEXT} findings={[finding({ id: 9 })]} onSelect={onSelect} />);
  await user.click(screen.getByText(QUOTE));
  expect(onSelect).toHaveBeenCalledWith(9);

  render(<RiskReport analysis={analysis({ findings: [finding({ id: 9 })] })} fragments={FRAGMENTS} selectedId={9} />);
  expect(screen.getByRole("row", { selected: true })).toHaveTextContent("Wysoka kara dzienna");
});

test("report sorted by risk level and shows fragment label", () => {
  const findings = [
    finding({ id: 1, teza: "Teza niska", poziom_ryzyka: "niskie" }),
    finding({ id: 2, teza: "Teza bez poziomu", poziom_ryzyka: null, typ: "strona" }),
    finding({ id: 3, teza: "Teza wysoka", poziom_ryzyka: "wysokie" }),
    finding({ id: 4, teza: "Teza średnia", poziom_ryzyka: "średnie" }),
  ];
  render(<RiskReport analysis={analysis({ findings })} fragments={FRAGMENTS} />);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows.map((r) => within(r).getAllByRole("cell")[1].textContent)).toEqual([
    "Teza wysoka",
    "Teza średnia",
    "Teza niska",
    "Teza bez poziomu",
  ]);
  expect(within(rows[0]).getByText("§ 1")).toBeInTheDocument();
});

test("quarantine banner hides findings", () => {
  render(
    <RiskReport
      analysis={analysis({ status: "quarantined", quarantine: { action_id: 4, status: "oczekuje" } })}
      fragments={FRAGMENTS}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent(/kwarantann/i);
  expect(screen.queryByText("Wysoka kara dzienna")).toBeNull();
  expect(screen.queryByRole("table")).toBeNull();
});

test("incomplete analysis is marked as such", () => {
  render(<RiskReport analysis={analysis({ status: "budget_exceeded", incomplete: true })} fragments={FRAGMENTS} />);
  expect(screen.getByText(/niepełn/i)).toBeInTheDocument();
});

function Probe({ id }: { id: number }) {
  const { analysis: a } = useAnalysis(id);
  return <p>status: {a?.status ?? "-"}</p>;
}

test("polls analysis every 2 s until a final status", async () => {
  vi.useFakeTimers();
  const fetch = mockFetch([
    { path: "/api/analyses/5", body: analysis({ status: "queued", findings: [] }) },
    { path: "/api/analyses/5", body: analysis({ status: "running", findings: [] }) },
    { path: "/api/analyses/5", body: analysis({ status: "done" }) },
  ]);
  render(<Probe id={5} />);
  await act(async () => {});
  expect(screen.getByText("status: queued")).toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getByText("status: running")).toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getByText("status: done")).toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetch).toHaveBeenCalledTimes(3);
});

test("polling survives a transient error", async () => {
  vi.useFakeTimers();
  mockFetch([
    { path: "/api/analyses/5", body: analysis({ status: "running", findings: [] }) },
    { path: "/api/analyses/5", status: 502, body: { title: "Bad Gateway" } },
    { path: "/api/analyses/5", body: analysis({ status: "done" }) },
  ]);
  render(<Probe id={5} />);
  await act(async () => {});
  expect(screen.getByText("status: running")).toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getByText("status: done")).toBeInTheDocument();
});

test("switching analysis clears the previous report while loading", async () => {
  mockFetch([
    { path: "/api/analyses/5", body: analysis({ status: "done" }) },
    { path: "/api/analyses/6", status: 404, body: { title: "Nie znaleziono analizy.", request_id: "r" } },
  ]);
  const { rerender } = render(<Probe id={5} />);
  expect(await screen.findByText("status: done")).toBeInTheDocument();
  rerender(<Probe id={6} />);
  expect(screen.getByText("status: -")).toBeInTheDocument();
  await act(async () => {});
  expect(screen.getByText("status: -")).toBeInTheDocument();
});

test("classifier outage banner does not claim an injection was found", () => {
  render(
    <RiskReport
      analysis={analysis({
        status: "quarantined",
        reason: "klasyfikator_niedostępny",
        quarantine: { action_id: 4, status: "oczekuje" },
      })}
      fragments={FRAGMENTS}
    />,
  );
  const banner = screen.getByRole("alert");
  expect(banner).toHaveTextContent(/klasyfikator/i);
  expect(banner).not.toHaveTextContent(/wykryto/i);
});


test("repeated click on overlapping highlight cycles findings", async () => {
  const user = userEvent.setup();
  const start = TEXT.indexOf(QUOTE);
  const findings = [finding({ id: 1 }), finding({ id: 2, start, end: start + 7 })];
  function Harness() {
    const [selected, setSelected] = useState<number | null>(null);
    return (
      <>
        <DocumentView text={TEXT} findings={findings} selectedId={selected} onSelect={setSelected} />
        <output>{selected ?? "brak"}</output>
      </>
    );
  }
  render(<Harness />);
  const overlap = () => document.querySelector('mark[data-finding-ids="1 2"]') as HTMLElement;
  await user.click(overlap());
  expect(screen.getByRole("status")).toHaveTextContent("1");
  await user.click(overlap());
  expect(screen.getByRole("status")).toHaveTextContent("2");
  await user.click(overlap());
  expect(screen.getByRole("status")).toHaveTextContent("1");
});
