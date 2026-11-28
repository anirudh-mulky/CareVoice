import type { RouteObject } from "react-router-dom";
import { TemplateDetailPage } from "./TemplateDetailPage";
import { TemplatesPage } from "./TemplatesPage";

/** Mounted under /doctor by the doctor-dashboard routes. */
export const templateRoutes: RouteObject[] = [
  { path: "templates", element: <TemplatesPage /> },
  { path: "templates/:templateId", element: <TemplateDetailPage /> },
];
