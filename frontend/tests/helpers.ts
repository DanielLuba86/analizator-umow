import { vi } from "vitest";

export type Route = {
  method?: string;
  path: string;
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
};

export function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const type = status >= 400 ? "application/problem+json" : "application/json";
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": type, ...headers },
  });
}

/** Mock `fetch`: każde wywołanie zużywa pierwszą pasującą trasę (metoda + ścieżka). */
export function mockFetch(routes: Route[]) {
  const queue = [...routes];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const i = queue.findIndex((r) => (r.method ?? "GET") === method && r.path === url);
    if (i < 0) throw new Error(`Nieoczekiwane żądanie: ${method} ${url}`);
    const [r] = queue.splice(i, 1);
    return json(r.status ?? 200, r.body ?? null, r.headers);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const ASYSTENT = { id: 1, login: "asystent", role: "asystent" };
export const PRAWNIK = { id: 2, login: "prawnik", role: "prawnik" };

export function problem(status: number, title: string, requestId: string) {
  return { type: "/problems/x", title, status, request_id: requestId };
}
