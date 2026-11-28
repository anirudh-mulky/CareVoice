import { api, type DischargeCard, unwrap } from "@/shared/api/client";

export const extractDischarge = (transcript: string) =>
  unwrap(api.POST("/api/v1/discharges/extract", { body: { transcript } }));

export const dischargeTemplates = () => unwrap(api.GET("/api/v1/discharges/templates"));

export const createDraft = (card: DischargeCard) => unwrap(api.POST("/api/v1/discharges", { body: card }));

export const updateDraft = (id: string, card: DischargeCard) =>
  unwrap(api.PATCH("/api/v1/discharges/{discharge_id}", { params: { path: { discharge_id: id } }, body: card }));

export const approveDischarge = (id: string, idempotencyKey: string) =>
  unwrap(
    api.POST("/api/v1/discharges/{discharge_id}/approve", {
      params: { path: { discharge_id: id }, header: { "Idempotency-Key": idempotencyKey } },
    }),
  );

/** Fresh patient and carer links for an approved discharge. */
export const shareLinks = (id: string) =>
  unwrap(api.POST("/api/v1/delivery/discharges/{discharge_id}/links", { params: { path: { discharge_id: id } } }));
