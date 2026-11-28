import { useQuery } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import type { PatientHome } from "@/shared/api/client";
import { isLang, type Lang } from "@/shared/languages";
import { getPatientHome } from "./api";

export type PatientContext = { token: string; home: PatientHome; lang: Lang };

export function usePatientHome(token: string) {
  // Refreshes so the recovery day and status stay current while the app is open.
  return useQuery({
    queryKey: ["patient", token],
    queryFn: () => getPatientHome(token),
    retry: false,
    refetchInterval: 10_000,
  });
}

/** The patient's language as a UI language (English if we have no UI strings for it). */
export function uiLang(code: string | undefined): Lang {
  return code && isLang(code) ? code : "en";
}

export const usePatient = () => useOutletContext<PatientContext>();
