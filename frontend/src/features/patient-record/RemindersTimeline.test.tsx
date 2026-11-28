import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";
import { installSynthesis, removeSynthesis, voice } from "@/test/fakeSpeech";

const DAY3_KN = "ಕಣ್ಣಿನ ಹನಿ ಹಾಕುವ ಸಮಯ. ನಿಮ್ಮ ಕಣ್ಣು ಕೆಂಪಾಗಿದೆಯೇ ಅಥವಾ ನೋವಿದೆಯೇ? ಮೈಕ್ ಒತ್ತಿ ಹೇಳಿ.";

const home = {
  patient_name: "Ramesh",
  viewer: { type: "patient", name: "Ramesh" },
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
};

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

test("today's sent reminder plays by itself in Kannada and the play is recorded", async () => {
  const spoken = installSynthesis([voice("kn-IN")]);
  let played = false;
  const calls = fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home }),
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "GET /api/v1/patient/good/reminders/today": () => ({
      body: {
        recovery_day: 3,
        language: "kn",
        reminders: [{ day: 3, time: "09:00", text: DAY3_KN, state: "sent", message_id: "m-r3", played }],
      },
    }),
    "POST /api/v1/patient/good/messages/m-r3/played": () => {
      played = true;
      return { status: 204, body: null };
    },
  });
  open("/p/good");
  const card = await screen.findByRole("region", { name: "ಇಂದಿನ ಜ್ಞಾಪನೆ" });
  expect(within(card).getByText(DAY3_KN)).toBeInTheDocument();
  expect(within(card).getByText("09:00 ಕ್ಕೆ")).toBeInTheDocument();
  await waitFor(() => expect(spoken.some((s) => s.text.includes("ಕಣ್ಣಿನ ಹನಿ"))).toBe(true));
  await waitFor(() => expect(calls.some((c) => c.path.endsWith("/m-r3/played"))).toBe(true));
});

test("an upcoming reminder shows its time without playing", async () => {
  const spoken = installSynthesis([voice("kn-IN")]);
  fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home }),
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "GET /api/v1/patient/good/reminders/today": () => ({
      body: {
        recovery_day: 3,
        language: "kn",
        reminders: [{ day: 3, time: "09:00", text: DAY3_KN, state: "upcoming", message_id: null, played: false }],
      },
    }),
  });
  open("/p/good");
  const card = await screen.findByRole("region", { name: "ಇಂದಿನ ಜ್ಞಾಪನೆ" });
  expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  expect(spoken).toHaveLength(0);
});

const discharge = {
  id: "d-1",
  status: "understood",
  card: {
    patient_name: "Ramesh",
    age: 68,
    template_id: "t-1",
    template_name: "Cataract surgery",
    side: "right",
    language: "kn",
    carer_phone: null,
    extra_instructions: ["Diabetic so check sugar daily"],
  },
  unclear_fields: [],
  patient: { id: "p-1", name: "Ramesh", age: 68, preferred_language: "kn" },
  template_version: 1,
  discharged_on: "2026-11-26",
  recovery_day: 3,
  approved_at: "2026-11-26T05:00:00Z",
  created_at: "2026-11-26T04:50:00Z",
};

function doctorServer() {
  return fakeApi({
    "GET /api/v1/system/status": () => ({ body: { mode: "demo", providers: [] } }),
    "GET /api/v1/discharges/d-1": () => ({ body: discharge }),
    "GET /api/v1/reports": () => ({ body: [] }),
    "GET /api/v1/discharges": () => ({ body: [] }),
    "GET /api/v1/reminders/discharges/d-1": () => ({
      body: [
        { id: "j-3", day: 3, time: "09:00", text_en: "Time for your eye drops.", due_at: "2026-11-28T03:30:00Z", status: "done", message_id: "m-r3" },
        { id: "j-6", day: 6, time: "10:00", text_en: "Your eye check-up is tomorrow.", due_at: "2026-12-01T04:30:00Z", status: "pending", message_id: null },
      ],
    }),
    "GET /api/v1/timeline/discharges/d-1": () => ({
      body: {
        discharge_id: "d-1",
        patient_name: "Ramesh",
        status: "understood",
        entries: [
          { id: "e1", at: "2026-11-26T05:00:00Z", type: "discharge.approved", actor: "doctor", title: "Discharge approved; care card sent to patient and carer", detail: null, tone: "neutral", report_id: null },
          { id: "e2", at: "2026-11-26T05:10:00Z", type: "teachback.scored", actor: "patient", title: "Teach-back try 1 (patient): named 6 of 6 warning signs, understood", detail: null, tone: "good", report_id: null },
          { id: "e3", at: "2026-11-28T03:30:00Z", type: "reminder.due", actor: "system", title: "Reminder sent (day 3, 09:00)", detail: "Time for your eye drops.", tone: "neutral", report_id: null },
        ],
      },
    }),
    "POST /api/v1/demo/advance-day": () => ({
      body: { patients: [{ patient_name: "Ramesh", recovery_day: 3, reminders_sent: 1 }], reminders_sent: 1 },
    }),
  });
}

test("the patient record shows reminders and a timeline with times", async () => {
  doctorServer();
  open("/doctor/patients/d-1");
  expect(await screen.findByRole("heading", { name: /Ramesh/ })).toBeInTheDocument();
  const timeline = await screen.findByRole("list", { name: "Timeline" });
  const items = within(timeline).getAllByRole("listitem");
  expect(items.map((li) => li.querySelector("p.font-medium")?.textContent)).toEqual([
    "Discharge approved; care card sent to patient and carer",
    "Teach-back try 1 (patient): named 6 of 6 warning signs, understood",
    "Reminder sent (day 3, 09:00)",
  ]);
  expect(items.every((li) => li.querySelector("time"))).toBe(true);
  const reminders = screen.getByRole("list", { name: "Reminders" });
  expect(within(reminders).getByText("Sent")).toBeInTheDocument();
  expect(within(reminders).getByText("Upcoming")).toBeInTheDocument();
});

test("simulate next day reports the new day and reminders sent", async () => {
  const calls = doctorServer();
  open("/doctor");
  await userEvent.click(await screen.findByRole("button", { name: /Simulate next day/ }));
  expect(await screen.findByText("Ramesh: day 3. 1 reminder sent.")).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/demo/advance-day")).toBe(true);
});
