/** Minimal API client. Part 4 replaces the hand-written types with ones generated from OpenAPI. */
export const API_BASE = "/api/v1";

export type Health = { status: "ok"; mode: "demo" | "real"; version: string };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed with ${res.status}`);
  return (await res.json()) as T;
}

export const getHealth = () => apiGet<Health>("/health");
