import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";
import { removeSynthesis } from "@/test/fakeSpeech";

const QUESTION = "ನಿಮ್ಮ ಮಾತಿನಲ್ಲೇ ಹೇಳಿ: ಯಾವಾಗ ಆಸ್ಪತ್ರೆಗೆ ಮತ್ತೆ ಬರಬೇಕು?";
const VISION = { id: "rf_vision_loss", label: "ದೃಷ್ಟಿ ಇದ್ದಕ್ಕಿದ್ದಂತೆ ಕಡಿಮೆಯಾದರೆ ಅಥವಾ ಕಾಣಿಸದಿದ್ದರೆ" };
const RED = { id: "rf_redness", label: "ಕಣ್ಣು ಹೆಚ್ಚು ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ" };

const home = (status = "sent") => ({
  patient_name: "Ramesh",
  viewer: { type: "patient", name: "Ramesh" },
  language: "kn",
  hospital: { name: "CareVoice Demo Hospital", phone: "+91 90000 00000" },
  status,
  recovery_day: 1,
  card: {
    language: "kn",
    translated: true,
    title: "ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ",
    greeting: "Ramesh",
    red_flags_title: "ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಆದರೆ ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ",
    red_flags: [VISION.label, RED.label],
    medicines: [],
    dos: [],
    donts: [],
    extras: [],
    follow_up: null,
    labels: { medicines: "", do: "", dont: "", extras: "" },
  },
});
const state = { language: "kn", question: QUESTION, complete: false, tries_used: 0, max_tries: 2, discharge_status: "sent", last: null };
const result = (outcome: string, tryNumber: number, missed: (typeof VISION)[]) => ({
  try_number: tryNumber,
  max_tries: 2,
  outcome,
  passed: outcome === "understood",
  mentioned: missed.length ? [RED] : [RED, VISION],
  missed,
  reply: outcome === "try_again" ? `ಈ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳನ್ನೂ ನೆನಪಿಡಿ: ${VISION.label}.` : outcome === "understood" ? "ಚೆನ್ನಾಗಿದೆ." : "ಧನ್ಯವಾದ.",
  discharge_status: outcome === "try_again" ? "sent" : outcome,
});

function server(answers: ReturnType<typeof result>[], status = "sent") {
  let n = 0;
  return fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home(status) }),
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "GET /api/v1/patient/good/teachback": () => ({ body: state }),
    "POST /api/v1/patient/good/teachback": () => ({ body: answers[n++] }),
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

async function answer(text: string) {
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, text);
  await userEvent.click(screen.getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeSynthesis();
});

test("the home screen invites the patient to the teach-back", async () => {
  server([]);
  open("/p/good");
  const link = await screen.findByRole("link", { name: "ಪ್ರಶ್ನೆಗೆ ಉತ್ತರಿಸಿ" });
  expect(link).toHaveAttribute("href", "/p/good/teachback");
});

test("a partial answer re-explains the missed sign and asks again", async () => {
  const calls = server([result("try_again", 1, [VISION])]);
  open("/p/good/teachback");
  expect(await screen.findByRole("heading", { name: QUESTION })).toBeInTheDocument();
  expect(screen.getByText("2 ರಲ್ಲಿ 1ನೇ ಪ್ರಯತ್ನ")).toBeInTheDocument();

  await answer("kannu kempagidre bartini");
  const missed = await screen.findByRole("heading", { name: "ಇವುಗಳನ್ನೂ ನೆನಪಿಡಿ" });
  expect(within(missed.closest("section")!).getByText(VISION.label)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "ಈಗ ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ" })).toBeInTheDocument();
  expect(screen.getByText("2 ರಲ್ಲಿ 2ನೇ ಪ್ರಯತ್ನ")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ transcript: "kannu kempagidre bartini", language: "kn" });
});

test("a full answer on the second try shows understood", async () => {
  server([result("try_again", 1, [VISION]), result("understood", 2, [])]);
  open("/p/good/teachback");
  await answer("kempu");
  await screen.findByRole("heading", { name: "ಈಗ ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ" });
  await answer("kaanisuttilla");
  expect(await screen.findByRole("status")).toHaveTextContent("ನಿಮಗೆ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳು ಗೊತ್ತಿವೆ");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "ಆರೈಕೆ ಕಾರ್ಡ್‌ಗೆ ಹಿಂತಿರುಗಿ" })).toHaveAttribute("href", "/p/good");
});

test("two failures tell the patient the care team will follow up", async () => {
  server([result("try_again", 1, [VISION]), result("needs_followup", 2, [VISION])]);
  open("/p/good/teachback");
  await answer("gottilla");
  await screen.findByRole("heading", { name: "ಈಗ ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ" });
  await answer("gottilla");
  expect(await screen.findByRole("status")).toHaveTextContent("ನಿಮ್ಮ ಆರೈಕೆ ತಂಡ");
});

test("an understood patient sees a tick on the home screen, not the invitation", async () => {
  server([], "understood");
  open("/p/good");
  expect(await screen.findByText("ಚೆನ್ನಾಗಿದೆ. ನಿಮಗೆ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳು ಗೊತ್ತಿವೆ.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "ಪ್ರಶ್ನೆಗೆ ಉತ್ತರಿಸಿ" })).not.toBeInTheDocument();
});
