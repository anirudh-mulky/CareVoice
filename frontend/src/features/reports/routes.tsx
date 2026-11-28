import type { RouteObject } from "react-router-dom";
import { DoctorReportPage } from "./DoctorReportPage";
import { PatientReportPage } from "./PatientReportPage";

/** Child routes of the patient link (/p/:token/...). */
export const reportPatientRoutes: RouteObject[] = [{ path: "report", element: <PatientReportPage /> }];

/** Child routes of /doctor. */
export const reportDoctorRoutes: RouteObject[] = [{ path: "reports/:reportId", element: <DoctorReportPage /> }];
