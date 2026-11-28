import { api, unwrap } from "@/shared/api/client";

const path = (token: string) => ({ params: { path: { token } } });

export const getPatientHome = (token: string) => unwrap(api.GET("/api/v1/patient/{token}", path(token)));

export const getMessages = (token: string) => unwrap(api.GET("/api/v1/patient/{token}/messages", path(token)));

export const markPlayed = async (token: string, messageId: string) => {
  await api.POST("/api/v1/patient/{token}/messages/{message_id}/played", {
    params: { path: { token, message_id: messageId } },
  });
};

export const getDemoLinks = () => unwrap(api.GET("/api/v1/delivery/demo-links"));

export const getTeachback = (token: string) =>
  unwrap(api.GET("/api/v1/patient/{token}/teachback", path(token)));

export const answerTeachback = (token: string, transcript: string, language?: string) =>
  unwrap(api.POST("/api/v1/patient/{token}/teachback", { ...path(token), body: { transcript, language } }));

export const getTodayReminders = (token: string) =>
  unwrap(api.GET("/api/v1/patient/{token}/reminders/today", path(token)));

export const changeLanguage = (token: string, body: { language?: string; spoken?: string }) =>
  unwrap(api.PUT("/api/v1/patient/{token}/language", { ...path(token), body }));
