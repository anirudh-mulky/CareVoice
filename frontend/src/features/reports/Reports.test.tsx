import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";
import { removeSynthesis } from "@/test/fakeSpeech";

const RED_EYE = "Kannu tumba kempagide, novu ide.";
const READ_BACK = "ನೀವು ಹೇಳಿದ್ದು: ತುಂಬಾ ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?";

const home = (viewer = { type: "patient", name: "Ramesh" }) => ({
  patient_name: "Ramesh",
  viewer,
  language: "kn",
  hospital: { name: "CareVoice Demo Hospital", phone: "+91 90000 00000" },
  status: "understood",
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

const REPORT = {
  id: "r-1",
  discharge_id: "d-1",
  patient_name: "Ramesh",
  language: "kn",
  type: "alert",
  status: "new",
  reported_by: "patient",
  summary_en: "Patient reports redness, pain (described as: tumba) on recovery day 3.",
  recovery_day: 3,
  created_at: "2026-11-28T09:00:00Z",
};
const DETAIL = {
  ...REPORT,
  patient_age: 68,
  template_name: "Cataract surgery",
  discharge_status: "understood",
  transcript_native: RED_EYE,
  translation_en: "My eye is very red, and there is pain.",
  read_back_native: READ_BACK,
  stt_confidence: 0.82,
  audio_url: "/api/v1/reports/r-1/audio",
  confidence: "high",
  reasons: ["red_flag"],
  needs_review: false,
  symptoms: [
    { name_en: "redness", body_part: "eye", severity_words: "tumba", onset: null, duration: null },
    { name_en: "pain", body_part: null, severity_words: null, onset: null, duration: null },
  ],
  red_flags: [
    { id: "rf_eye_pain", label_en: "Increasing eye pain that painkillers do not relieve" },
    { id: "rf_redness", label_en: "Increasing redness of the eye" },
  ],
  minor_symptoms: [],
  suggested_remedies: [],
  medicines: [{ name: "Moxifloxacin 0.5% eye drops", instructions: "1 drop, 4 times a day, 7 days" }],
  extra_instructions: ["Diabetic so check sugar daily"],
};

function patientServer(answers: { outcome: string; message: string }[], viewer?: { type: string; name: string }) {
  let n = 0;
  return fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home(viewer) }),
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "POST /api/v1/patient/good/reports": () => ({
      status: 201,
      body: { report_id: `r-${n + 1}`, language: "kn", read_back: READ_BACK },
    }),
    "POST /api/v1/patient/good/reports/:id/confirm": () => ({ body: { report_id: `r-${n + 1}`, ...answers[n++] } }),
  });
}

function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

async function say(text: string) {
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, text);
  await userEvent.click(within(box.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeSynthesis();
});

test("the patient hears the read-back and yes sends the report", async () => {
  const calls = patientServer([{ outcome: "sent", message: "ಧನ್ಯವಾದ. ನಿಮ್ಮ ವೈದ್ಯರು ಇದನ್ನು ನೋಡುತ್ತಾರೆ." }]);
  open("/p/good/report");
  expect(await screen.findByRole("heading", { name: "ಏನು ತೊಂದರೆ ಎಂದು ಹೇಳಿ" })).toBeInTheDocument();
  await say(RED_EYE);

  expect(await screen.findByText(READ_BACK)).toBeInTheDocument();
  expect(calls.find((c) => c.path.endsWith("/reports"))?.body).toEqual({
    transcript: RED_EYE,
    language: "kn",
    stt_confidence: null,
  });
  await userEvent.click(screen.getByRole("button", { name: /ಹೌದು, ಕಳುಹಿಸಿ/ }));
  expect(await screen.findByRole("heading", { name: "ನಿಮ್ಮ ವೈದ್ಯರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ" })).toBeInTheDocument();
  expect(calls.find((c) => c.path.endsWith("/confirm"))?.body).toEqual({ answer: true });
});

test("saying no to the read-back asks the patient again", async () => {
  patientServer([{ outcome: "say_again", message: "ಕ್ಷಮಿಸಿ. ಏನು ತೊಂದರೆ ಎಂದು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ." }]);
  open("/p/good/report");
  await say(RED_EYE);
  await userEvent.click(await screen.findByRole("button", { name: /ಇಲ್ಲ, ಮತ್ತೆ ಹೇಳುತ್ತೇನೆ/ }));
  expect(await screen.findByRole("status")).toHaveTextContent("ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ");
  expect(screen.queryByText(READ_BACK)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /ಟೈಪ್ ಮಾಡಿ|ಒತ್ತಿ/ })).toBeInTheDocument();
});

test("an unclear spoken answer keeps the read-back and asks for a tap", async () => {
  patientServer([{ outcome: "unclear", message: "ದಯವಿಟ್ಟು ಹೌದು ಅಥವಾ ಇಲ್ಲ ಒತ್ತಿ." }]);
  open("/p/good/report");
  await say(RED_EYE);
  await screen.findByText(READ_BACK);
  await userEvent.click(screen.getByText("ಅಥವಾ ಹೌದು / ಇಲ್ಲ ಎಂದು ಹೇಳಿ"));
  const boxes = await screen.findAllByRole("textbox");
  await userEvent.type(boxes.at(-1)!, "hmm");
  await userEvent.click(within(boxes.at(-1)!.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
  expect(await screen.findByRole("status")).toHaveTextContent("ದಯವಿಟ್ಟು ಹೌದು ಅಥವಾ ಇಲ್ಲ ಒತ್ತಿ");
  expect(screen.getByText(READ_BACK)).toBeInTheDocument();
});

test("a carer is told they are reporting for the patient", async () => {
  patientServer([], { type: "carer", name: "Kiran" });
  open("/p/good/report");
  expect(await screen.findByText("ನೀವು Ramesh ಅವರ ಪರವಾಗಿ ಹೇಳುತ್ತಿದ್ದೀರಿ.")).toBeInTheDocument();
});

function doctorServer() {
  return fakeApi({
    "GET /api/v1/reports": () => ({ body: [REPORT] }),
    "GET /api/v1/reports/r-1": () => ({ body: DETAIL }),
    "PATCH /api/v1/reports/r-1": () => ({ body: { ...DETAIL, status: "seen" } }),
    "GET /api/v1/discharges": (_b, url) => ({
      body: [
        {
          id: "d-1",
          status: "understood",
          patient_name: "Ramesh",
          age: 68,
          language: "kn",
          template_name: "Cataract surgery",
          discharged_on: "2026-11-26",
          recovery_day: 3,
          approved_at: null,
          new_reports: 1,
          latest_report_id: "r-1",
          latest_report_type: "alert",
        },
      ].filter((d) => d.patient_name.toLowerCase().includes((url.searchParams.get("q") ?? "").toLowerCase())),
    }),
    "GET /api/v1/system/status": () => ({ body: { mode: "demo", providers: [] } }),
  });
}

test("the dashboard shows new reports first and searches patients", async () => {
  const calls = doctorServer();
  open("/doctor");
  const inbox = await screen.findByRole("list", { name: "New reports" });
  expect(within(inbox).getByText("Alert")).toBeInTheDocument();
  expect(within(inbox).getByRole("link")).toHaveAttribute("href", "/doctor/reports/r-1");
  expect(await screen.findByRole("link", { name: "1 new report" })).toBeInTheDocument();

  await userEvent.type(screen.getByRole("searchbox", { name: /search patients/i }), "zz");
  expect(await screen.findByText("No patients match.")).toBeInTheDocument();
  expect(calls.some((c) => c.path === "/api/v1/discharges")).toBe(true);
});

test("the report page shows English beside the Kannada words and marks it seen", async () => {
  const calls = doctorServer();
  open("/doctor/reports/r-1");
  expect(await screen.findByText(/My eye is very red, and there is pain/)).toBeInTheDocument();
  expect(screen.getByText(`“${RED_EYE}”`)).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Increasing redness of the eye");
  expect(screen.getByText("Day 3")).toBeInTheDocument();
  expect(screen.getByText("Moxifloxacin 0.5% eye drops")).toBeInTheDocument();
  expect(screen.getByLabelText("Original recording")).toHaveAttribute("src", "/api/v1/reports/r-1/audio");
  await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
});
