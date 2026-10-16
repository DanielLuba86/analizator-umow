import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ContractPage } from "../src/pages/ContractPage";
import { deferred, json, mockFetch, problem } from "./helpers";

const TEXT = "§ 1. Kary\nNajemca zapłaci karę umowną 600 zł za dzień.";
const QUOTE = "zapłaci karę umowną 600 zł";
const START = TEXT.indexOf(QUOTE);

const CONTRACT = {
  id: 3,
  title: "Najem lokalu",
  kind: "najem",
  source: "kontrahent",
  versions: [
    { id: 10, nr: 1, created_at: "2026-10-15T10:00:00+00:00" },
    { id: 11, nr: 2, created_at: "2026-10-15T11:00:00+00:00" },
  ],
};

function version(analyses: unknown[] = []) {
  return {
    id: 11,
    contract_id: 3,
    nr: 2,
    text: TEXT,
    fragments: [{ id: "f001", label: "§ 1", start: 0, end: TEXT.length }],
    analyses,
  };
}

const REPORT = {
  id: 7,
  version_id: 11,
  status: "done",
  reason: null,
  agent_reason: null,
  turns: 2,
  cost_usd: 0.01,
  incomplete: false,
  official: false,
  quarantine: null,
  findings: [
    {
      id: 1,
      typ: "kara",
      teza: "Wysoka kara dzienna",
      cytat: QUOTE,
      fragment_id: "f001",
      start: START,
      end: START + QUOTE.length,
      poziom_ryzyka: "wysokie",
      uzasadnienie: "Rażąco wygórowana.",
      template_id: null,
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("shows latest version and starts an analysis", async () => {
  const fetch = mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version() },
    { method: "POST", path: "/api/versions/11/analyses", status: 202, body: { analysis_id: 7 } },
    { path: "/api/versions/11", body: version([{ id: 7, status: "queued", started_at: "x" }]) },
    { path: "/api/analyses/7", body: REPORT },
    { path: "/api/actions?analysis_id=7", body: [] },
  ]);
  render(<ContractPage contractId={3} />);

  expect(await screen.findByRole("heading", { name: "Najem lokalu" })).toBeInTheDocument();
  expect(await screen.findByTestId("loaded-version")).toHaveTextContent("Wersja 2");
  await userEvent.click(await screen.findByRole("button", { name: "Uruchom analizę" }));

  expect(await screen.findByText("Wysoka kara dzienna")).toBeInTheDocument();
  expect(document.querySelector("mark")).toHaveTextContent(QUOTE);
  expect(screen.getByRole("option", { name: "#7 — zakończona" })).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/versions/11/analyses", expect.objectContaining({ method: "POST" }));
});

test("409 on start shows the server message", async () => {
  mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version() },
    {
      method: "POST",
      path: "/api/versions/11/analyses",
      status: 409,
      body: problem(409, "Dla tej wersji trwa już analiza.", "rid-9"),
    },
  ]);
  render(<ContractPage contractId={3} />);
  await userEvent.click(await screen.findByRole("button", { name: "Uruchom analizę" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Dla tej wersji trwa już analiza.");
});

test("requests an export for a finished analysis", async () => {
  const fetch = mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version([{ id: 7, status: "done", started_at: "x" }]) },
    { path: "/api/analyses/7", body: REPORT },
    { path: "/api/actions?analysis_id=7", body: [] },
    { method: "POST", path: "/api/analyses/7/actions", status: 201, body: { action_id: 4 } },
    {
      path: "/api/actions?analysis_id=7",
      body: [
        {
          id: 4,
          typ: "eksport",
          analysis_id: 7,
          status: "oczekuje",
          payload: { zrodlo: "uzytkownik" },
          created_at: "2026-10-15T12:00:00+00:00",
          decided_by: null,
          decided_at: null,
          export_id: null,
        },
      ],
    },
  ]);
  render(<ContractPage contractId={3} />);
  await userEvent.click(await screen.findByRole("button", { name: "Wnioskuj o eksport" }));

  expect(await screen.findByText(/eksport — oczekuje/)).toBeInTheDocument();
  const post = fetch.mock.calls.find(([url]) => url === "/api/analyses/7/actions");
  expect(JSON.parse(String(post?.[1]?.body))).toEqual({ typ: "eksport" });
  expect(screen.queryByRole("link", { name: /Pobierz/ })).not.toBeInTheDocument();
});

test("approved export offers JSON and PDF downloads", async () => {
  mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version([{ id: 7, status: "done", started_at: "x" }]) },
    { path: "/api/analyses/7", body: REPORT },
    {
      path: "/api/actions?analysis_id=7",
      body: [
        {
          id: 4,
          typ: "eksport",
          analysis_id: 7,
          status: "zatwierdzona",
          payload: { zrodlo: "uzytkownik" },
          created_at: "2026-10-15T12:00:00+00:00",
          decided_by: 2,
          decided_at: "2026-10-15T13:00:00+00:00",
          export_id: 9,
        },
      ],
    },
  ]);
  render(<ContractPage contractId={3} />);

  const json = await screen.findByRole("link", { name: "Pobierz eksport (JSON)" });
  expect(json).toHaveAttribute("href", "/api/exports/9");
  const pdf = screen.getByRole("link", { name: "Pobierz PDF" });
  expect(pdf).toHaveAttribute("href", "/api/exports/9/pdf");
  expect(pdf).toHaveAttribute("download");
});


const QUARANTINED = {
  ...REPORT,
  status: "quarantined",
  reason: "wstrzyknięcie",
  findings: [],
  quarantine: { action_id: 5, status: "oczekuje" },
};
const RELEASED = { ...REPORT, quarantine: { action_id: 5, status: "zatwierdzona" } };

test("quarantine banner has refresh button that reloads analysis", async () => {
  mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version([{ id: 7, status: "quarantined", started_at: "x" }]) },
    { path: "/api/analyses/7", body: QUARANTINED },
    { path: "/api/analyses/7", body: RELEASED },
    { path: "/api/actions?analysis_id=7", body: [] },
  ]);
  render(<ContractPage contractId={3} />);
  expect(await screen.findByText(/Analiza jest w kwarantannie/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Odśwież" }));
  expect(await screen.findByText("Wysoka kara dzienna")).toBeInTheDocument();
  expect(screen.queryByText(/Analiza jest w kwarantannie/)).not.toBeInTheDocument();
});

test("analysis error is announced", async () => {
  mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version([{ id: 7, status: "done", started_at: "x" }]) },
    { path: "/api/analyses/7", status: 404, body: problem(404, "Nie znaleziono analizy.", "r-1") },
  ]);
  render(<ContractPage contractId={3} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Nie znaleziono analizy.");
});

test("second click while start is in flight is ignored", async () => {
  const pending = deferred();
  const routes = mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { path: "/api/versions/11", body: version() },
    { path: "/api/versions/11", body: version([{ id: 7, status: "done", started_at: "x" }]) },
    { path: "/api/analyses/7", body: REPORT },
    { path: "/api/actions?analysis_id=7", body: [] },
  ]);
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "POST" ? pending.promise : routes(input, init),
  );
  vi.stubGlobal("fetch", fetch);
  render(<ContractPage contractId={3} />);
  const button = await screen.findByRole("button", { name: "Uruchom analizę" });
  fireEvent.click(button);
  fireEvent.click(button);
  pending.release(json(202, { analysis_id: 7 }));
  expect(await screen.findByText("Wysoka kara dzienna")).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
