import { api, unwrap } from "@/shared/api/client";

const reportPath = (id: string) => ({ params: { path: { report_id: id } } });
const dischargePath = (id: string) => ({ params: { path: { discharge_id: id } } });

export const getActions = (reportId: string) => unwrap(api.GET("/api/v1/reports/{report_id}/actions", reportPath(reportId)));

export const approveRemedy = (reportId: string, minorIds: string[]) =>
  unwrap(api.POST("/api/v1/reports/{report_id}/remedy", { ...reportPath(reportId), body: { minor_ids: minorIds } }));

export const previewReply = (reportId: string, text: string) =>
  unwrap(api.POST("/api/v1/reports/{report_id}/reply/preview", { ...reportPath(reportId), body: { text } }));

export const sendReply = (reportId: string, text: string, key: string) =>
  unwrap(
    api.POST("/api/v1/reports/{report_id}/reply", {
      params: { path: { report_id: reportId }, header: { "idempotency-key": key } },
      body: { text },
    }),
  );

export const alertHandled = (dischargeId: string) =>
  unwrap(api.POST("/api/v1/discharges/{discharge_id}/alert/handled", dischargePath(dischargeId)));

export const closeEpisode = (dischargeId: string) =>
  unwrap(api.POST("/api/v1/discharges/{discharge_id}/close", dischargePath(dischargeId)));
