/**
 * Typed API client. Paths, params and responses come from src/shared/api/schema.d.ts,
 * generated from the backend's OpenAPI schema (`make types`), so the two never drift.
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({
  // Same origin: the API and the app are served together on :3000 (Vite proxies /api in dev).
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  // Look fetch up per call so it can be swapped (tests, offline queue later).
  fetch: (request: Request) => globalThis.fetch(request),
});

export type Schemas = components["schemas"];
export type SystemStatus = Schemas["SystemStatus"];
export type ProviderStatus = Schemas["ProviderStatus"];
export type DischargeCard = Schemas["DischargeCard-Input"];
export type DischargeOut = Schemas["DischargeOut"];
export type DischargeListItem = Schemas["DischargeListItem"];
export type ExtractResponse = Schemas["ExtractResponse"];
export type TemplateOption = Schemas["TemplateOption"];
export type TemplateSummary = Schemas["TemplateSummary"];
export type TemplateOut = Schemas["TemplateOut"];
export type PatientHome = Schemas["PatientHome"];
export type CareCard = Schemas["CareCard"];
export type ChatMessage = Schemas["ChatMessage"];
export type PatientLink = Schemas["PatientLink"];
export type DemoPatientLink = Schemas["DemoPatientLink"];
export type TeachbackState = Schemas["TeachbackState"];
export type TeachbackResult = Schemas["TeachbackResult"];
export type ReadBack = Schemas["ReadBack"];
export type ConfirmOut = Schemas["ConfirmOut"];
export type ReportListItem = Schemas["ReportListItem"];
export type ReportDetail = Schemas["ReportDetail"];
export type ReportActions = Schemas["ReportActions"];
export type ReplyPreview = Schemas["ReplyPreview"];
export type TodayReminders = Schemas["TodayReminders"];
export type ScheduledReminder = Schemas["ScheduledReminder"];
export type Timeline = Schemas["Timeline"];
export type AdvanceResult = Schemas["AdvanceResult"];

export type Health = { status: "ok"; mode: "demo" | "real"; version: string };

type ErrorBody = { error?: { code?: string; message?: string; details?: unknown } };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code: string = "http_error",
    public readonly details: unknown = null,
  ) {
    super(message);
  }
}

/** Unwrap an openapi-fetch result: return data or throw ApiError with the server's code. */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;
  if (error !== undefined || data === undefined) {
    const body = (error ?? {}) as ErrorBody;
    throw new ApiError(
      response.status,
      body.error?.message ?? `Request failed (${response.status})`,
      body.error?.code,
      body.error?.details ?? null,
    );
  }
  return data;
}

export const getHealth = async (): Promise<Health> =>
  (await unwrap(api.GET("/api/v1/health"))) as Health;

export const getSystemStatus = (): Promise<SystemStatus> => unwrap(api.GET("/api/v1/system/status"));
