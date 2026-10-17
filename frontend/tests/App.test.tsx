import { render, screen, within } from "@testing-library/react";

import App from "../src/App";
import { ASYSTENT, PRAWNIK, mockFetch } from "./helpers";

test("renders app title", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Analizator umów" })).toBeInTheDocument();
});

describe("routing for a logged-in user", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.location.hash = "";
  });

  test("unknown route shows not found", async () => {
    mockFetch([{ path: "/api/auth/me", body: ASYSTENT }]);
    window.location.hash = "#/nie-ma-takiej-strony";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Nie znaleziono strony" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wróć do listy umów" })).toHaveAttribute("href", "#/contracts");
  });

  test("main navigation marks the current page", async () => {
    mockFetch([
      { path: "/api/auth/me", body: PRAWNIK },
      { path: "/api/actions?status=oczekuje", body: [] },
    ]);
    window.location.hash = "#/approvals";
    render(<App />);
    const nav = await screen.findByRole("navigation", { name: "Główna" });
    expect(within(nav).getByRole("link", { name: "Wnioski do zatwierdzenia" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Umowy" })).not.toHaveAttribute("aria-current");
  });

  test("asystent typing #/approvals sees no approvals", async () => {
    const fetch = mockFetch([{ path: "/api/auth/me", body: ASYSTENT }]);
    window.location.hash = "#/approvals";
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("tylko dla prawnika");
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/api/auth/me"]);
  });
});
