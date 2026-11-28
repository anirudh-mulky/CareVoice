import type { RouteObject } from "react-router-dom";
import { reportPatientRoutes } from "@/features/reports/routes";
import { teachbackPatientRoutes } from "@/features/teachback/routes";
import { page } from "@/shared/lazyRoute";
import { RouteLoading } from "@/shared/RouteLoading";

/** /p/:token is the patient's own link: its own layout, outside the staff shell. */
export const patientLinkRoutes: RouteObject[] = [
  {
    path: "/p/:token",
    lazy: page(() => import("./PatientLayout"), (m) => m.PatientLayout),
    hydrateFallbackElement: <RouteLoading />,
    children: [
      { index: true, lazy: page(() => import("./PatientHomePage"), (m) => m.PatientHomePage) },
      { path: "chat", lazy: page(() => import("@/features/chat/ChatPage"), (m) => m.ChatPage) },
      ...teachbackPatientRoutes,
      ...reportPatientRoutes,
    ],
  },
];

/** "I'm a patient" on the main screen (demo patient picker). */
export const patientPickerRoutes: RouteObject[] = [
  { path: "patient", lazy: page(() => import("./PatientPickerPage"), (m) => m.PatientPickerPage) },
];
