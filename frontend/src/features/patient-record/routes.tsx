import type { RouteObject } from "react-router-dom";
import { PatientRecordPage } from "./PatientRecordPage";

/** Child routes of /doctor. */
export const patientRecordRoutes: RouteObject[] = [{ path: "patients/:dischargeId", element: <PatientRecordPage /> }];
