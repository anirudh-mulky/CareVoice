import { Outlet, type RouteObject } from "react-router-dom";
import { devVoiceRoutes } from "@/features/dev-voice/routes";
import { doctorRoutes } from "@/features/doctor-dashboard/routes";
import { patientLinkRoutes, patientPickerRoutes } from "@/features/patient-home/routes";
import { rolePickerRoutes } from "@/features/role-picker/routes";
import { Layout } from "@/shared/Layout";
import { NotBuiltYetPage } from "@/shared/NotBuiltYetPage";

/** Each feature exports its routes; add them here as build parts land. */
const featureRoutes: RouteObject[] = [...rolePickerRoutes, ...doctorRoutes, ...patientPickerRoutes, ...devVoiceRoutes];

export const routes: RouteObject[] = [
  ...patientLinkRoutes,
  {
    path: "/",
    element: (
      <Layout>
        <Outlet />
      </Layout>
    ),
    children: [...featureRoutes, { path: "*", element: <NotBuiltYetPage /> }],
  },
];
