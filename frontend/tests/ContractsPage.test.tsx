import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ContractsPage } from "../src/pages/ContractsPage";
import { mockFetch } from "./helpers";

beforeEach(() => {
  window.location.hash = "#/contracts";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("lists contracts with links", async () => {
  mockFetch([
    {
      path: "/api/contracts",
      body: [{ id: 3, title: "Najem lokalu", kind: "najem", source: "kontrahent", versions: 2 }],
    },
  ]);
  render(<ContractsPage />);
  expect(await screen.findByRole("link", { name: "Najem lokalu" })).toHaveAttribute("href", "#/contracts/3");
});

test("creates a contract and opens it", async () => {
  const fetch = mockFetch([
    { path: "/api/contracts", body: [] },
    { method: "POST", path: "/api/contracts", status: 201, body: { id: 8, version_id: 20 } },
  ]);
  render(<ContractsPage />);
  await userEvent.type(await screen.findByLabelText("Tytuł"), "Dostawa mebli");
  await userEvent.selectOptions(screen.getByLabelText("Rodzaj"), "dostawa");
  await userEvent.selectOptions(screen.getByLabelText("Źródło"), "wewnętrzna");
  await userEvent.type(screen.getByLabelText("Tekst umowy"), "§ 1. Przedmiot dostawy.");
  await userEvent.click(screen.getByRole("button", { name: "Dodaj umowę" }));

  await waitFor(() => expect(window.location.hash).toBe("#/contracts/8"));
  const call = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({
    title: "Dostawa mebli",
    kind: "dostawa",
    source: "wewnętrzna",
    text: "§ 1. Przedmiot dostawy.",
  });
});
