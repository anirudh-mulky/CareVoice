import type { RouteObject } from "react-router-dom";
import { TeachbackPage } from "./TeachbackPage";

/** Child routes of the patient link (/p/:token/...). */
export const teachbackPatientRoutes: RouteObject[] = [{ path: "teachback", element: <TeachbackPage /> }];
