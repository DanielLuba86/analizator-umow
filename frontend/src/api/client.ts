/** Błąd API z odpowiedzi problem+json; `title` to stały tekst z backendu. */
export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly requestId: string | null;

  constructor(status: number, title: string, requestId: string | null) {
    super(title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.requestId = requestId;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let title = `Błąd serwera (${res.status}).`;
  let requestId = res.headers.get("X-Request-ID");
  if ((res.headers.get("Content-Type") ?? "").includes("json")) {
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object") {
        const b = body as { title?: unknown; request_id?: unknown };
        if (typeof b.title === "string") title = b.title;
        if (typeof b.request_id === "string") requestId = b.request_id;
      }
    } catch {
      // ciało nie jest JSON-em — zostaje tytuł ogólny
    }
  }
  return new ApiError(res.status, title, requestId);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json, application/problem+json");
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
}

/** Komunikat dla użytkownika: tytuł błędu i identyfikator żądania do zgłoszenia. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    return e.requestId ? `${e.title} (identyfikator żądania: ${e.requestId})` : e.title;
  }
  return "Nie udało się połączyć z serwerem.";
}
