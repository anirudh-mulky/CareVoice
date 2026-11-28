import type { RouteObject } from "react-router-dom";
import { ChatPage } from "@/features/chat/ChatPage";
import { reportPatientRoutes } from "@/features/reports/routes";
import { teachbackPatientRoutes } from "@/features/teachback/routes";
import { PatientHomePage } from "./PatientHomePage";
import { PatientLayout } from "./PatientLayout";
import { PatientPickerPage } from "./PatientPickerPage";

/** /p/:token is the patient's own link: its own layout, outside the staff shell. */
export const patientLinkRoutes: RouteObject[] = [
  {
    path: "/p/:token",
    element: <PatientLayout />,
    children: [
      { index: true, element: <PatientHomePage /> },
      { path: "chat", element: <ChatPage /> },
      ...teachbackPatientRoutes,
      ...reportPatientRoutes,
    ],
  },
];

/** "I'm a patient" on the main screen (demo patient picker). */
export const patientPickerRoutes: RouteObject[] = [{ path: "patient", element: <PatientPickerPage /> }];
