import { render, screen } from "@testing-library/react";

import App from "../src/App";
import { ASYSTENT, mockFetch } from "./helpers";

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

  test("asystent typing #/approvals sees no approvals", async () => {
    const fetch = mockFetch([{ path: "/api/auth/me", body: ASYSTENT }]);
    window.location.hash = "#/approvals";
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("tylko dla prawnika");
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/api/auth/me"]);
  });
});
