import { api, unwrap } from "@/shared/api/client";

export const listTemplates = () => unwrap(api.GET("/api/v1/templates"));

export const getTemplate = (id: string, version?: number) =>
  unwrap(api.GET("/api/v1/templates/{template_id}", { params: { path: { template_id: id }, query: { version } } }));
