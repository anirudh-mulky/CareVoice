import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";
import { removeSynthesis } from "@/test/fakeSpeech";

const ITCH_KN = "ಕಣ್ಣು ಗುಣವಾಗುವಾಗ ಸ್ವಲ್ಪ ತುರಿಕೆ ಸಾಮಾನ್ಯ.";
const SAFETY_KN = "ನೀವು ಹೇಳಿದ್ದು ಮುಖ್ಯವಾದ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣ ಆಗಿರಬಹುದು. ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ.";

const detail = (type: string) => ({
  id: "r-1",
  discharge_id: "d-1",
  patient_name: "Ramesh",
  language: "kn",
  type,
  status: "seen",
  reported_by: "patient",
  summary_en: "Patient reports itching.",
  recovery_day: 3,
  created_at: "2026-11-28T09:00:00Z",
  patient_age: 68,
  template_name: "Cataract surgery",
  discharge_status: type === "alert" ? "alert" : "sent",
  transcript_native: "kannu turike ide",
  translation_en: null,
  read_back_native: null,
  stt_confidence: null,
  audio_url: null,
  confidence: "high",
  reasons: [],
  needs_review: false,
  symptoms: [],
  red_flags: [],
  minor_symptoms: [],
  suggested_remedies: [],
  medicines: [],
  extra_instructions: [],
});

const actions = (type: string, over: Record<string, unknown> = {}) => ({
  report_id: "r-1",
  discharge_id: "d-1",
  report_type: type,
  report_status: "seen",
  discharge_status: type === "alert" ? "alert" : "sent",
  language: "kn",
  can_send_remedy: type !== "alert",
  can_handle_alert: type === "alert",
  can_close: true,
  remedy_options: [
    {
      minor_id: "ms_itching",
      symptom_en: "Mild itching or a gritty feeling",
      remedy_en: "Mild itching is common while the eye heals.",
      remedy_native: ITCH_KN,
      translated: true,
      suggested: true,
    },
    {
      minor_id: "ms_watering",
      symptom_en: "Watering eye",
      remedy_en: "Some watering is normal.",
      remedy_native: "ಸ್ವಲ್ಪ ನೀರು ಬರುವುದು ಸಾಮಾನ್ಯ.",
      translated: true,
      suggested: false,
    },
  ],
  quick_replies: [{ id: "visit_today", text_en: "Please come to the hospital today." }],
  sent: [],
  ...over,
});

const sentMsg = (kind: string, text: string) => ({
  id: `m-${kind}`,
  kind,
  text_native: text,
  text_en: "english",
  language: "kn",
  created_at: "2026-11-28T09:05:00Z",
});

function doctor(type: string) {
  let state = actions(type);
  const result = (status: string) => ({ outcome: "sent", message: null, discharge_status: status, report_status: "seen" });
  const calls = fakeApi({
    "GET /api/v1/reports/r-1": () => ({ body: detail(type) }),
    "GET /api/v1/reports/r-1/actions": () => ({ body: state }),
    "POST /api/v1/reports/r-1/remedy": () => {
      state = actions(type, { can_send_remedy: false, report_status: "remedy_sent", sent: [sentMsg("remedy", ITCH_KN)] });
      return { body: result("sent") };
    },
    "POST /api/v1/reports/r-1/reply/preview": (body) => {
      const text = (body as { text: string }).text;
      const known = text === "Please come to the hospital today.";
      return { body: { language: "kn", text_native: known ? "ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ." : text, translated: known } };
    },
    "POST /api/v1/reports/r-1/reply": () => {
      state = actions(type, { sent: [sentMsg("doctor_reply", "ನಿಮ್ಮ ವೈದ್ಯರು ಹೇಳುತ್ತಾರೆ: ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ.")] });
      return { body: result("sent") };
    },
    "POST /api/v1/discharges/d-1/alert/handled": () => {
      state = actions(type, { can_handle_alert: false, discharge_status: "sent" });
      return { body: { outcome: "handled", message: null, discharge_status: "sent", report_status: null } };
    },
    "POST /api/v1/discharges/d-1/close": () => {
      state = actions(type, { can_close: false, can_send_remedy: false, discharge_status: "closed" });
      return { body: { outcome: "closed", message: null, discharge_status: "closed", report_status: null } };
    },
    "GET /api/v1/system/status": () => ({ body: { mode: "demo", providers: [] } }),
  });
  return calls;
}

function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeSynthesis();
});

test("the doctor approves the template's remedy and sees the Kannada text sent", async () => {
  const calls = doctor("minor");
  open("/doctor/reports/r-1");
  const matched = await screen.findByRole("checkbox", { name: /Mild itching/ });
  expect(matched).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Watering eye/ })).not.toBeChecked();
  expect(screen.getByText(`Patient gets: ${ITCH_KN}`)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /Approve and send remedy/ }));
  const sent = await screen.findByRole("list", { name: "Sent to the patient" });
  expect(within(sent).getByText(ITCH_KN)).toBeInTheDocument();
  expect(calls.find((c) => c.path.endsWith("/remedy"))?.body).toEqual({ minor_ids: ["ms_itching"] });
  expect(screen.queryByRole("button", { name: /Approve and send remedy/ })).not.toBeInTheDocument();
});

test("a quick reply shows the Kannada preview and is sent once with a key", async () => {
  const calls = doctor("general");
  open("/doctor/reports/r-1");
  await userEvent.click(await screen.findByRole("button", { name: "Please come to the hospital today." }));
  expect(await screen.findByText("ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Send reply/ }));
  await screen.findByRole("list", { name: "Sent to the patient" });
  const send = calls.find((c) => c.path.endsWith("/reply"));
  expect(send?.body).toEqual({ text: "Please come to the hospital today." });
  expect(send?.headers.get("idempotency-key")).toBeTruthy();
});

test("free text the demo cannot translate warns that it goes in English", async () => {
  doctor("general");
  open("/doctor/reports/r-1");
  await userEvent.type(await screen.findByRole("textbox", { name: "Your reply" }), "Thursday at 10 is fine");
  expect(await screen.findByText(/the patient will get it in English/)).toBeInTheDocument();
});

test("an alert offers no remedy, and can be marked handled", async () => {
  const calls = doctor("alert");
  open("/doctor/reports/r-1");
  await userEvent.click(await screen.findByRole("button", { name: /Mark alert handled/ }));
  await waitFor(() => expect(calls.some((c) => c.path.endsWith("/alert/handled"))).toBe(true));
  await waitFor(() => expect(screen.queryByRole("button", { name: /Mark alert handled/ })).not.toBeInTheDocument());
  expect(screen.queryByRole("button", { name: /Approve and send remedy/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Remedies are not offered for alerts/)).toBeInTheDocument();
});

test("closing the episode asks first", async () => {
  const calls = doctor("general");
  open("/doctor/reports/r-1");
  await userEvent.click(await screen.findByRole("button", { name: /Close care episode/ }));
  expect(calls.some((c) => c.path.endsWith("/close"))).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Yes, close it" }));
  expect(await screen.findByText(/This care episode is closed/)).toBeInTheDocument();
});

// --- Patient side ---------------------------------------------------------------------------

const home = (status: string) => ({
  patient_name: "Ramesh",
  viewer: { type: "patient", name: "Ramesh" },
  language: "kn",
  hospital: { name: "CareVoice Demo Hospital", phone: "+91 90000 00000" },
  status,
  recovery_day: 3,
  card: {
    language: "kn",
    translated: true,
    title: "ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ",
    greeting: "Ramesh",
    red_flags_title: "ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಆದರೆ ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ",
    red_flags: ["ಕಣ್ಣು ಹೆಚ್ಚು ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ"],
    medicines: [],
    dos: [],
    donts: [],
    extras: [],
    follow_up: null,
    labels: { medicines: "", do: "", dont: "", extras: "" },
  },
});
const chatMsg = (id: string, kind: string, text: string) => ({
  id,
  direction: "to_patient",
  kind,
  text,
  text_en: null,
  language: "kn",
  audio_url: null,
  played_at: null,
  created_at: "2026-11-28T09:05:00Z",
});

test("during an alert the patient home shows the safety message first", async () => {
  fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home("alert") }),
    "GET /api/v1/patient/good/messages": () => ({ body: [chatMsg("m-1", "safety", SAFETY_KN)] }),
  });
  open("/p/good");
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent("ದಯವಿಟ್ಟು ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ");
  expect(await within(banner).findByText(SAFETY_KN)).toBeInTheDocument();
});

test("a new remedy or reply is announced on the home screen", async () => {
  fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home("sent") }),
    "GET /api/v1/patient/good/messages": () => ({ body: [chatMsg("m-2", "remedy", ITCH_KN)] }),
  });
  open("/p/good");
  expect(await screen.findByRole("link", { name: /ನಿಮ್ಮ ವೈದ್ಯರಿಂದ ಹೊಸ ಸಂದೇಶ/ })).toHaveAttribute("href", "/p/good/chat");
});

test("right after a red-flag report the patient sees the safety message", async () => {
  let confirmed = false;
  fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home("sent") }),
    "GET /api/v1/patient/good/messages": () => ({ body: confirmed ? [chatMsg("m-9", "safety", SAFETY_KN)] : [] }),
    "POST /api/v1/patient/good/reports": () => ({
      status: 201,
      body: { report_id: "r-1", language: "kn", read_back: "ನೀವು ಹೇಳಿದ್ದು: ತುಂಬಾ ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?" },
    }),
    "POST /api/v1/patient/good/reports/r-1/confirm": () => {
      confirmed = true;
      return { body: { report_id: "r-1", outcome: "sent", message: "ಧನ್ಯವಾದ." } };
    },
  });
  open("/p/good/report");
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, "Kannu tumba kempagide, novu ide.");
  await userEvent.click(within(box.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
  await userEvent.click(await screen.findByRole("button", { name: /ಹೌದು, ಕಳುಹಿಸಿ/ }));
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent(SAFETY_KN);
});
