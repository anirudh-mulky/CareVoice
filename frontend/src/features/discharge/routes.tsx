import type { RouteObject } from "react-router-dom";
import { NewDischargePage } from "./NewDischargePage";

/** Mounted under /doctor by the doctor-dashboard routes. */
export const dischargeRoutes: RouteObject[] = [{ path: "discharge/new", element: <NewDischargePage /> }];
