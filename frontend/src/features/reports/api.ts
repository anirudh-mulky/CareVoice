import { api, unwrap } from "@/shared/api/client";
import type { Recording } from "@/shared/Recorder";

const tokenPath = (token: string) => ({ params: { path: { token } } });

// --- Patient ------------------------------------------------------------------------------

export const createReport = (token: string, transcript: string, language: string, sttConfidence?: number | null) =>
  unwrap(
    api.POST("/api/v1/patient/{token}/reports", {
      ...tokenPath(token),
      body: { transcript, language, stt_confidence: sttConfidence ?? null },
    }),
  );

export const createIconReport = (token: string, icons: string[], language: string) =>
  unwrap(api.POST("/api/v1/patient/{token}/reports", { ...tokenPath(token), body: { transcript: "", icons, language } }));

export const confirmReport = (token: string, reportId: string, body: { answer?: boolean; transcript?: string }) =>
  unwrap(
    api.POST("/api/v1/patient/{token}/reports/{report_id}/confirm", {
      params: { path: { token, report_id: reportId } },
      body,
    }),
  );

/** Keep the recording for the doctor. Best effort: the report works without it. */
export async function uploadAudio(token: string, reportId: string, recording: Recording): Promise<void> {
  try {
    await globalThis.fetch(`/api/v1/patient/${token}/reports/${reportId}/audio`, {
      method: "PUT",
      headers: { "content-type": recording.mimeType || "audio/webm" },
      body: recording.blob,
    });
  } catch {
    // The doctor still gets the transcript.
  }
}

// --- Doctor -------------------------------------------------------------------------------

export const listReports = (status?: "new" | "seen") =>
  unwrap(api.GET("/api/v1/reports", { params: { query: status ? { status } : {} } }));

export const getReport = (id: string) =>
  unwrap(api.GET("/api/v1/reports/{report_id}", { params: { path: { report_id: id } } }));

export const markSeen = (id: string) =>
  unwrap(api.PATCH("/api/v1/reports/{report_id}", { params: { path: { report_id: id } }, body: { status: "seen" } }));
