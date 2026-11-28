import { api, unwrap, type DischargeListItem } from "@/shared/api/client";

export type DischargeFilter = DischargeListItem["status"] | "all";

export const listDischarges = (status: DischargeFilter = "all", q = "") =>
  unwrap(
    api.GET("/api/v1/discharges", {
      params: { query: { ...(status !== "all" ? { status } : {}), ...(q.trim() ? { q: q.trim() } : {}) } },
    }),
  );
