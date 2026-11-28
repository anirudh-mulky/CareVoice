import { api, unwrap } from "@/shared/api/client";

const dischargePath = (id: string) => ({ params: { path: { discharge_id: id } } });

export const getDischarge = (id: string) => unwrap(api.GET("/api/v1/discharges/{discharge_id}", dischargePath(id)));

export const getTimeline = (id: string) => unwrap(api.GET("/api/v1/timeline/discharges/{discharge_id}", dischargePath(id)));

export const getReminders = (id: string) => unwrap(api.GET("/api/v1/reminders/discharges/{discharge_id}", dischargePath(id)));

export const getEpisodeReports = (id: string) =>
  unwrap(api.GET("/api/v1/reports", { params: { query: { discharge_id: id } } }));
