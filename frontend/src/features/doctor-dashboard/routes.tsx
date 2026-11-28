import type { RouteObject } from "react-router-dom";
import { dischargeRoutes } from "@/features/discharge/routes";
import { patientRecordRoutes } from "@/features/patient-record/routes";
import { reportDoctorRoutes } from "@/features/reports/routes";
import { templateRoutes } from "@/features/templates/routes";
import { page } from "@/shared/lazyRoute";

export const doctorRoutes: RouteObject[] = [
  {
    path: "doctor",
    lazy: page(() => import("./DoctorLayout"), (m) => m.DoctorLayout),
    children: [
      { index: true, lazy: page(() => import("./DoctorHomePage"), (m) => m.DoctorHomePage) },
      ...dischargeRoutes,
      ...templateRoutes,
      ...reportDoctorRoutes,
      ...patientRecordRoutes,
    ],
  },
];
