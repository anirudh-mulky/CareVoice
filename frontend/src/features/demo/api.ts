import { api, unwrap } from "@/shared/api/client";

export const advanceDay = () => unwrap(api.POST("/api/v1/demo/advance-day"));

export const resetDemo = () => unwrap(api.POST("/api/v1/demo/reset"));
