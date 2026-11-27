import { Outlet, type RouteObject } from "react-router-dom";
import { rolePickerRoutes } from "@/features/role-picker/routes";
import { Layout } from "@/shared/Layout";
import { NotBuiltYetPage } from "@/shared/NotBuiltYetPage";

/** Each feature exports its routes; add them here as build parts land. */
const featureRoutes: RouteObject[] = [...rolePickerRoutes];

export const routes: RouteObject[] = [
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
