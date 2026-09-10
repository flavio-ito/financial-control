export type ApiErrorBody = {
  detail?: { code?: string; message?: string; field?: string; preview?: unknown };
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly detail?: ApiErrorBody["detail"],
  ) {
    super(message);
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(value: string): void {
  csrfToken = value;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!csrfToken && path !== "/api/v1/session/bootstrap") {
      throw new ApiError(403, "CSRF_REQUIRED", "Sessão ainda não inicializada.");
    }
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(
      response.status,
      body.detail?.code ?? "HTTP_ERROR",
      body.detail?.message ?? "Não foi possível concluir a operação.",
      body.detail,
    );
  }
  return (await response.json()) as T;
}

export async function apiDownload(path: string, init: RequestInit = {}): Promise<{ blob: Blob; filename: string }> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!csrfToken) throw new ApiError(403, "CSRF_REQUIRED", "Sessão ainda não inicializada.");
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(response.status, body.detail?.code ?? "HTTP_ERROR", body.detail?.message ?? "Não foi possível concluir a operação.", body.detail);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return { blob: await response.blob(), filename: match?.[1] ?? "financas.finbackup" };
}

async function initializeSessionOnce(): Promise<void> {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const bootstrap = hash.get("bootstrap");
  if (bootstrap) {
    const result = await apiFetch<{ csrf_token: string }>("/api/v1/session/bootstrap", {
      method: "POST",
      body: JSON.stringify({ token: bootstrap }),
    });
    setCsrfToken(result.csrf_token);
    history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    return;
  }
  const result = await apiFetch<{ csrf_token: string }>("/api/v1/session/csrf");
  setCsrfToken(result.csrf_token);
}

let sessionInitialization: Promise<void> | null = null;

export function initializeSession(): Promise<void> {
  if (!sessionInitialization) sessionInitialization = initializeSessionOnce();
  return sessionInitialization;
}

export function idempotencyHeaders(): HeadersInit {
  return { "Idempotency-Key": crypto.randomUUID() };
}
import type { paths } from "./schema";

export type ApiPaths = paths;
