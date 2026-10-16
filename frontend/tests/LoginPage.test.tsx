import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthProvider } from "../src/auth/AuthContext";
import { LoginPage } from "../src/pages/LoginPage";
import { ASYSTENT, deferred, json, mockFetch, problem } from "./helpers";

beforeEach(() => {
  window.location.hash = "#/login";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Login"), "asystent");
  await user.type(screen.getByLabelText("Hasło"), "tajne-haslo");
  await user.click(screen.getByRole("button", { name: "Zaloguj" }));
}

test("shows error with request id on 401", async () => {
  mockFetch([
    { path: "/api/auth/me", status: 401, body: problem(401, "Wymagane logowanie.", "r-0") },
    {
      method: "POST",
      path: "/api/auth/login",
      status: 401,
      body: problem(401, "Nieprawidłowy login lub hasło.", "abc123"),
    },
  ]);
  render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  );
  await fillAndSubmit();

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Nieprawidłowy login lub hasło.");
  expect(alert).toHaveTextContent("abc123");
  expect(window.location.hash).toBe("#/login");
});

test("redirects to contracts after login", async () => {
  const fetch = mockFetch([
    { path: "/api/auth/me", status: 401, body: problem(401, "Wymagane logowanie.", "r-0") },
    { method: "POST", path: "/api/auth/login", status: 204 },
    { path: "/api/auth/me", body: ASYSTENT },
  ]);
  render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  );
  await fillAndSubmit();

  await waitFor(() => expect(window.location.hash).toBe("#/contracts"));
  const login = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(login?.[1]?.credentials).toBe("same-origin");
  expect(JSON.parse(String(login?.[1]?.body))).toEqual({ login: "asystent", password: "tajne-haslo" });
});

test("second click while login is in flight is ignored", async () => {
  const pending = deferred();
  const routes = mockFetch([
    { path: "/api/auth/me", status: 401, body: problem(401, "Wymagane logowanie.", "r-0") },
    { path: "/api/auth/me", body: ASYSTENT },
  ]);
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "POST" ? pending.promise : routes(input, init),
  );
  vi.stubGlobal("fetch", fetch);
  render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  );
  await userEvent.type(await screen.findByLabelText("Login"), "asystent");
  await userEvent.type(screen.getByLabelText("Hasło"), "tajne-haslo");
  const button = screen.getByRole("button", { name: "Zaloguj" });
  fireEvent.submit(button.closest("form")!);
  fireEvent.submit(button.closest("form")!);
  pending.release(json(204, null));
  await waitFor(() => expect(window.location.hash).toBe("#/contracts"));
  expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
