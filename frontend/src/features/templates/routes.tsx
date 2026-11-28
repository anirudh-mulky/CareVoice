import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Mounted under /doctor by the doctor-dashboard routes. */
export const templateRoutes: RouteObject[] = [
  { path: "templates", lazy: page(() => import("./TemplatesPage"), (m) => m.TemplatesPage) },
  { path: "templates/:templateId", lazy: page(() => import("./TemplateDetailPage"), (m) => m.TemplateDetailPage) },
];
