import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "../src/App";
import { ApprovalsPage } from "../src/pages/ApprovalsPage";
import { ASYSTENT, PRAWNIK, mockFetch, problem } from "./helpers";

function action(id: number, typ: string, payload: Record<string, unknown>) {
  return {
    id,
    typ,
    analysis_id: 7,
    status: "oczekuje",
    payload,
    created_at: "2026-10-15T12:00:00+00:00",
    decided_by: null,
    decided_at: null,
    export_id: null,
  };
}

const PENDING = [
  action(1, "kwarantanna", { "powód": "wstrzyknięcie" }),
  action(2, "opinia", { zrodlo: "agent", uzasadnienie: "<b>Kara rażąco wygórowana</b>" }),
  action(3, "wzorzec", { zrodlo: "agent", uzasadnienie: "Klauzula do wzorca." }),
];

beforeEach(() => {
  window.location.hash = "#/contracts";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("approvals hidden for asystent", async () => {
  mockFetch([
    { path: "/api/auth/me", body: ASYSTENT },
    { path: "/api/contracts", body: [] },
  ]);
  render(<App />);
  expect(await screen.findByRole("link", { name: "Umowy" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Wnioski/ })).toBeNull();
});

test("approvals visible for prawnik", async () => {
  mockFetch([
    { path: "/api/auth/me", body: PRAWNIK },
    { path: "/api/contracts", body: [] },
  ]);
  render(<App />);
  expect(await screen.findByRole("link", { name: /Wnioski/ })).toHaveAttribute("href", "#/approvals");
});

test("approve calls decision endpoint and removes row", async () => {
  const fetch = mockFetch([
    { path: "/api/actions?status=oczekuje", body: PENDING },
    {
      method: "POST",
      path: "/api/actions/1/decision",
      body: { id: 1, status: "zatwierdzona", export_id: null },
    },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /kwarantanna/ });
  expect(within(row).getByText(/próbę wstrzyknięcia poleceń/)).toBeInTheDocument();
  await userEvent.click(within(row).getByRole("button", { name: "Zatwierdź" }));

  await waitFor(() => expect(screen.queryByRole("row", { name: /kwarantanna/ })).toBeNull());
  const call = fetch.mock.calls.find(([url]) => url === "/api/actions/1/decision");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ approve: true });
  expect(screen.getByRole("row", { name: /opinia/ })).toBeInTheDocument();
});

test("reject sends approve false", async () => {
  const fetch = mockFetch([
    { path: "/api/actions?status=oczekuje", body: PENDING },
    {
      method: "POST",
      path: "/api/actions/2/decision",
      body: { id: 2, status: "odrzucona", export_id: null },
    },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /opinia/ });
  expect(within(row).getByText(/<b>Kara rażąco wygórowana<\/b>/)).toBeInTheDocument();
  expect(row.querySelector("b")).toBeNull();
  await userEvent.click(within(row).getByRole("button", { name: "Odrzuć" }));
  await waitFor(() => expect(screen.queryByRole("row", { name: /opinia/ })).toBeNull());
  const call = fetch.mock.calls.find(([url]) => url === "/api/actions/2/decision");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ approve: false });
});

test("approving a template sends clause name and text", async () => {
  const fetch = mockFetch([
    { path: "/api/actions?status=oczekuje", body: PENDING },
    {
      method: "POST",
      path: "/api/actions/3/decision",
      body: { id: 3, status: "zatwierdzona", export_id: null },
    },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /wzorzec/ });
  await userEvent.type(within(row).getByLabelText("Nazwa klauzuli"), "Kara umowna");
  await userEvent.type(within(row).getByLabelText("Treść klauzuli"), "Kara umowna wynosi 0,1% dziennie.");
  await userEvent.click(within(row).getByRole("button", { name: "Zatwierdź" }));

  await waitFor(() => expect(screen.queryByRole("row", { name: /wzorzec/ })).toBeNull());
  const call = fetch.mock.calls.find(([url]) => url === "/api/actions/3/decision");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({
    approve: true,
    template: { nazwa_klauzuli: "Kara umowna", tresc: "Kara umowna wynosi 0,1% dziennie." },
  });
});

test("409 shows already decided message", async () => {
  mockFetch([
    { path: "/api/actions?status=oczekuje", body: PENDING },
    {
      method: "POST",
      path: "/api/actions/2/decision",
      status: 409,
      body: problem(409, "Wniosek został już rozstrzygnięty.", "rid-5"),
    },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /opinia/ });
  await userEvent.click(within(row).getByRole("button", { name: "Zatwierdź" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Wniosek został już rozstrzygnięty");
  expect(screen.queryByRole("row", { name: /opinia/ })).toBeNull();
});

test("hidden agent justification is not shown", async () => {
  mockFetch([
    { path: "/api/actions?status=oczekuje", body: [action(5, "opinia", { zrodlo: "agent", ukryte: true })] },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /opinia/ });
  expect(within(row).getByText(/ukryte do czasu zwolnienia raportu/)).toBeInTheDocument();
});

test("quarantine reasons are described in plain words", async () => {
  mockFetch([
    {
      path: "/api/actions?status=oczekuje",
      body: [
        action(8, "kwarantanna", { "powód": "klasyfikator_niedostępny" }),
        action(9, "kwarantanna", { "powód": "wstrzyknięcie" }),
      ],
    },
  ]);
  render(<ApprovalsPage />);
  expect(await screen.findByText(/klasyfikator wstrzyknięć był niedostępny/)).toBeInTheDocument();
  expect(screen.getByText(/wykryto możliwą próbę wstrzyknięcia/)).toBeInTheDocument();
  expect(screen.queryByText(/klasyfikator_niedostępny/)).toBeNull();
});

test("expired session returns to the login form", async () => {
  mockFetch([
    { path: "/api/auth/me", body: ASYSTENT },
    { path: "/api/contracts", status: 401, body: problem(401, "Wymagane zalogowanie.", "r-1") },
  ]);
  render(<App />);
  expect(await screen.findByRole("button", { name: "Zaloguj" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Wyloguj" })).toBeNull();
});

test("double click on approve sends one decision", async () => {
  const fetch = mockFetch([
    { path: "/api/actions?status=oczekuje", body: PENDING },
    {
      method: "POST",
      path: "/api/actions/1/decision",
      body: { id: 1, status: "zatwierdzona", export_id: null },
    },
  ]);
  render(<ApprovalsPage />);
  const row = await screen.findByRole("row", { name: /kwarantanna/ });
  await userEvent.dblClick(within(row).getByRole("button", { name: "Zatwierdź" }));
  await waitFor(() => expect(screen.queryByRole("row", { name: /kwarantanna/ })).toBeNull());
  expect(fetch.mock.calls.filter(([url]) => url === "/api/actions/1/decision")).toHaveLength(1);
});
