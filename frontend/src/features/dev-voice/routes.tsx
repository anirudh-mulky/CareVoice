import type { RouteObject } from "react-router-dom";
import { DevVoicePage } from "./DevVoicePage";

/** Hidden developer route; not linked from any screen. */
export const devVoiceRoutes: RouteObject[] = [{ path: "dev/voice", element: <DevVoicePage /> }];
