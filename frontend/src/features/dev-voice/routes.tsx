import type { RouteObject } from "react-router-dom";
import { page } from "@/shared/lazyRoute";

/** Hidden developer route; not linked from any screen. */
export const devVoiceRoutes: RouteObject[] = [
  { path: "dev/voice", lazy: page(() => import("./DevVoicePage"), (m) => m.DevVoicePage) },
];
