import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ComparePage } from "../src/pages/ComparePage";
import { mockFetch } from "./helpers";

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

const COMPARISON = {
  id: 1,
  fragment_changes: [
    { label: "§ 2", kind: "zmieniony", old_text: "Kara 600 zł.", new_text: "Kara 900 zł." },
    { label: "§ 5", kind: "dodany", old_text: null, new_text: "<script>alert(1)</script>" },
  ],
  finding_changes: {
    nowe: [{ typ: "kara", label: "§ 2", cytat: "Kara 900 zł." }],
    ustąpiło: [{ typ: "kara", label: "§ 2", cytat: "Kara 600 zł." }],
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("compare shows changed fragment labels", async () => {
  const fetch = mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    { method: "POST", path: "/api/comparisons", status: 201, body: COMPARISON },
  ]);
  render(<ComparePage contractId={3} />);
  await screen.findByRole("heading", { name: /Najem lokalu/ });
  await userEvent.click(screen.getByRole("button", { name: "Porównaj" }));

  const changes = await screen.findByRole("region", { name: "Zmienione fragmenty" });
  expect(within(changes).getByText(/§ 2/)).toBeInTheDocument();
  expect(within(changes).getByText(/§ 5/)).toBeInTheDocument();
  expect(within(changes).getByText("Kara 600 zł.")).toBeInTheDocument();
  expect(within(changes).getByText("Kara 900 zł.")).toBeInTheDocument();
  expect(within(changes).getByText("<script>alert(1)</script>")).toBeInTheDocument();
  expect(document.querySelector("script")).toBeNull();

  const findings = screen.getByRole("region", { name: "Zmiany tez" });
  expect(within(findings).getByRole("list", { name: "Nowe tezy" })).toHaveTextContent("Kara 900 zł.");
  expect(within(findings).getByRole("list", { name: "Tezy, które ustąpiły" })).toHaveTextContent("Kara 600 zł.");

  const call = fetch.mock.calls.find(([url]) => url === "/api/comparisons");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ version_a: 10, version_b: 11 });
});

test("compare without finished analyses explains missing finding diff", async () => {
  mockFetch([
    { path: "/api/contracts/3", body: CONTRACT },
    {
      method: "POST",
      path: "/api/comparisons",
      status: 201,
      body: { ...COMPARISON, finding_changes: null },
    },
  ]);
  render(<ComparePage contractId={3} />);
  await screen.findByRole("heading", { name: /Najem lokalu/ });
  await userEvent.click(screen.getByRole("button", { name: "Porównaj" }));
  expect(await screen.findByText(/obie wersje muszą mieć zakończoną analizę/)).toBeInTheDocument();
});
