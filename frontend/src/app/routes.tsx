import { Outlet, type RouteObject } from "react-router-dom";
import { ResetDemoButton } from "@/features/demo/ResetDemoButton";
import { devVoiceRoutes } from "@/features/dev-voice/routes";
import { doctorRoutes } from "@/features/doctor-dashboard/routes";
import { patientLinkRoutes, patientPickerRoutes } from "@/features/patient-home/routes";
import { rolePickerRoutes } from "@/features/role-picker/routes";
import { Layout } from "@/shared/Layout";
import { RouteLoading } from "@/shared/RouteLoading";
import { NotBuiltYetPage } from "@/shared/NotBuiltYetPage";

/** Each feature exports its routes. The main screen loads at once; other screens load on demand. */
const featureRoutes: RouteObject[] = [...rolePickerRoutes, ...doctorRoutes, ...patientPickerRoutes, ...devVoiceRoutes];

export const routes: RouteObject[] = [
  ...patientLinkRoutes,
  {
    path: "/",
    element: (
      <Layout actions={<ResetDemoButton />}>
        <Outlet />
      </Layout>
    ),
    hydrateFallbackElement: <RouteLoading />,
    children: [...featureRoutes, { path: "*", element: <NotBuiltYetPage /> }],
  },
];
