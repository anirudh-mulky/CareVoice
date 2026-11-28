import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Child routes of /doctor. */
export const patientRecordRoutes: RouteObject[] = [
  { path: "patients/:dischargeId", lazy: page(() => import("./PatientRecordPage"), (m) => m.PatientRecordPage) },
];
