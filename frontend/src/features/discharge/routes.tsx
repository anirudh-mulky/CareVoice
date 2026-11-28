import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Mounted under /doctor by the doctor-dashboard routes. */
export const dischargeRoutes: RouteObject[] = [
  { path: "discharge/new", lazy: page(() => import("./NewDischargePage"), (m) => m.NewDischargePage) },
];
