import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Child routes of the patient link (/p/:token/...). */
export const teachbackPatientRoutes: RouteObject[] = [
  { path: "teachback", lazy: page(() => import("./TeachbackPage"), (m) => m.TeachbackPage) },
];
