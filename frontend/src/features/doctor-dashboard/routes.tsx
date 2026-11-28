import type { RouteObject } from "react-router-dom";
import { dischargeRoutes } from "@/features/discharge/routes";
import { patientRecordRoutes } from "@/features/patient-record/routes";
import { reportDoctorRoutes } from "@/features/reports/routes";
import { templateRoutes } from "@/features/templates/routes";
import { DoctorHomePage } from "./DoctorHomePage";
import { DoctorLayout } from "./DoctorLayout";

export const doctorRoutes: RouteObject[] = [
  {
    path: "doctor",
    element: <DoctorLayout />,
    children: [{ index: true, element: <DoctorHomePage /> }, ...dischargeRoutes, ...templateRoutes, ...reportDoctorRoutes, ...patientRecordRoutes],
  },
];
