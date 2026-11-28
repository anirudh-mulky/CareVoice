import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Child routes of the patient link (/p/:token/...). */
export const reportPatientRoutes: RouteObject[] = [
  { path: "report", lazy: page(() => import("./PatientReportPage"), (m) => m.PatientReportPage) },
];

/** Child routes of /doctor. */
export const reportDoctorRoutes: RouteObject[] = [
  { path: "reports/:reportId", lazy: page(() => import("./DoctorReportPage"), (m) => m.DoctorReportPage) },
];
