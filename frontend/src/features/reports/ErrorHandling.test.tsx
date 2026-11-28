/** Part 11: each patient-side row of the error-handling table, triggered on purpose. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { VoiceInput } from "@/shared/VoiceInput";
import { fakeApi } from "@/test/fakeApi";
import { installRecognition, removeRecognition, removeSynthesis } from "@/test/fakeSpeech";

const READ_BACK = "ನೀವು ಹೇಳಿದ್ದು: ಕೆಂಪು ಮತ್ತು ನೋವು. ಇದು ಸರಿಯೇ?";

const home = (language = "kn") => ({
  patient_name: "Ramesh",
  viewer: { type: "patient", name: "Ramesh" },
  language,
  hospital: { name: "CareVoice Demo Hospital", phone: "+91 90000 00000" },
  status: "understood",
  recovery_day: 3,
  card: {
    language,
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

type Routes = Parameters<typeof fakeApi>[0];

function server(extra: Routes = {}) {
  return fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home() }),
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "GET /api/v1/patient/good/reminders/today": () => ({ body: { recovery_day: 3, language: "kn", reminders: [] } }),
    "GET /api/v1/system/status": () => ({ body: { mode: "demo", key_not_set: false, providers: [], channels: [], modules: [] } }),
    "POST /api/v1/patient/good/reports": () => ({ status: 201, body: { report_id: "r-1", language: "kn", read_back: READ_BACK, suggested_language: null } }),
    ...extra,
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

async function speakOnce(start = "ಒತ್ತಿ ಮಾತನಾಡಿ", stop = "ನಿಲ್ಲಿಸಲು ಒತ್ತಿ") {
  await userEvent.click(screen.getByRole("button", { name: start }));
  await userEvent.click(await screen.findByRole("button", { name: stop }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeSynthesis();
  removeRecognition();
  localStorage.clear();
});

test("two failed tries show the symptom icons and Call hospital", async () => {
  installRecognition([{ kind: "error", error: "no-speech" }]);
  const calls = server();
  open("/p/good/report");
  await screen.findByRole("heading", { name: "ಏನು ತೊಂದರೆ ಎಂದು ಹೇಳಿ" });
  await speakOnce();
  expect(await screen.findByRole("alert")).toHaveTextContent("ಕೇಳಿಸಲಿಲ್ಲ");
  expect(screen.queryByRole("region", { name: "ಅಥವಾ ತೊಂದರೆಯನ್ನು ಒತ್ತಿ" })).not.toBeInTheDocument();

  await speakOnce();
  const icons = await screen.findByRole("region", { name: "ಅಥವಾ ತೊಂದರೆಯನ್ನು ಒತ್ತಿ" });
  expect(within(icons).getByRole("link", { name: /ಆಸ್ಪತ್ರೆಗೆ ಕರೆ ಮಾಡಿ/ })).toHaveAttribute("href", "tel:+919000000000");
  expect(screen.getByRole("textbox")).toBeInTheDocument(); // type instead opens too

  await userEvent.click(within(icons).getByRole("button", { name: /ಕೆಂಪು/ }));
  await userEvent.click(within(icons).getByRole("button", { name: /ನೋವು/ }));
  await userEvent.click(within(icons).getByRole("button", { name: "ಕಳುಹಿಸಿ" }));
  expect(await screen.findByText(READ_BACK)).toBeInTheDocument();
  expect(calls.find((c) => c.path.endsWith("/reports"))?.body).toEqual({
    transcript: "",
    icons: ["redness", "pain"],
    language: "kn",
  });
});

test("a noisy, low-confidence result is asked again once, then sent", async () => {
  installRecognition([{ kind: "result", text: "kannu kempagide", confidence: 0.3 }]);
  const onText = vi.fn();
  render(<VoiceInput lang="kn" onText={onText} record={false} minConfidence={0.6} />);
  await speakOnce();
  expect(await screen.findByRole("alert")).toHaveTextContent("ಕೇಳಿಸಲಿಲ್ಲ");
  expect(onText).not.toHaveBeenCalled();
  await speakOnce();
  await waitFor(() => expect(onText).toHaveBeenCalled());
  expect(onText.mock.calls[0]?.[1].result.confidence).toBe(0.3); // the server escalates it
});

test("saying no twice to the read-back offers the icons", async () => {
  removeRecognition();
  server({
    "POST /api/v1/patient/good/reports/r-1/confirm": () => ({
      body: { report_id: "r-1", outcome: "say_again", message: "ಕ್ಷಮಿಸಿ. ಏನು ತೊಂದರೆ ಎಂದು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ." },
    }),
  });
  open("/p/good/report");
  for (let i = 0; i < 2; i++) {
    const box = await screen.findByRole("textbox");
    await userEvent.type(box, "kannu kempagide");
    await userEvent.click(within(box.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
    await userEvent.click(await screen.findByRole("button", { name: /ಇಲ್ಲ, ಮತ್ತೆ ಹೇಳುತ್ತೇನೆ/ }));
    await screen.findByRole("status");
  }
  // Without browser speech the icons are already offered; after two "no"s they stay, once.
  expect(await screen.findAllByRole("region", { name: "ಅಥವಾ ತೊಂದರೆಯನ್ನು ಒತ್ತಿ" })).toHaveLength(1);
});

test("speaking another language reads back in it and offers to switch", async () => {
  removeRecognition();
  const calls = server({
    "POST /api/v1/patient/good/reports": () => ({
      status: 201,
      body: { report_id: "r-1", language: "hi", read_back: "आपने बताया: लाली और दर्द। क्या यह सही है?", suggested_language: "hi" },
    }),
    "PUT /api/v1/patient/good/language": () => ({ body: { language: "hi" } }),
  });
  open("/p/good/report");
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, "आँख लाल है");
  await userEvent.click(within(box.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
  expect(await screen.findByText("आपने बताया: लाली और दर्द। क्या यह सही है?")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /हिंदी ಬಳಸಿ/ }));
  await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ language: "hi" }));
});

test("offline: what was said is saved, and sent when the network returns", async () => {
  removeRecognition();
  let online = false;
  server({
    "POST /api/v1/patient/good/reports": () => {
      if (!online) throw new TypeError("Failed to fetch");
      return { status: 201, body: { report_id: "r-1", language: "kn", read_back: READ_BACK, suggested_language: null } };
    },
  });
  open("/p/good/report");
  const box = await screen.findByRole("textbox");
  await userEvent.type(box, "kannu kempagide, novu ide");
  await userEvent.click(within(box.closest("form")!).getByRole("button", { name: /ಕಳುಹಿಸಿ/ }));
  expect(await screen.findByText(/ಇಂಟರ್ನೆಟ್ ಇಲ್ಲ/)).toBeInTheDocument();
  expect(JSON.parse(localStorage.getItem("carevoice.outbox") ?? "[]")).toHaveLength(1);

  online = true;
  window.dispatchEvent(new Event("online"));
  expect(await screen.findByText(READ_BACK)).toBeInTheDocument();
  expect(JSON.parse(localStorage.getItem("carevoice.outbox") ?? "[]")).toHaveLength(0);
});

test("the language button switches by tap or by voice", async () => {
  installRecognition([{ kind: "result", text: "Tamil" }]);
  const calls = server({ "PUT /api/v1/patient/good/language": (body) => ({ body: { language: (body as { language?: string }).language ?? "ta" } }) });
  open("/p/good");
  await userEvent.click(await screen.findByRole("button", { name: "ಭಾಷೆ" }));
  await userEvent.click(within(screen.getByRole("group", { name: "ಭಾಷೆ" })).getByRole("button", { name: "हिंदी" }));
  await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ language: "hi" }));

  await userEvent.click(screen.getByRole("button", { name: "ಭಾಷೆ" }));
  await userEvent.click(screen.getByText("ಅಥವಾ ನಿಮ್ಮ ಭಾಷೆಯನ್ನು ಹೇಳಿ"));
  await speakOnce();
  await waitFor(() => expect(calls.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ spoken: "Tamil" }));
});

test("real mode without speech keys shows the basic voice mode banner", async () => {
  server({
    "GET /api/v1/system/status": () => ({
      body: {
        mode: "real",
        key_not_set: true,
        providers: [{ kind: "stt", requested: "sarvam", active: "demo", mode: "demo", status: "key_not_set", detail: "" }],
        channels: [],
        modules: [],
      },
    }),
  });
  open("/p/good");
  expect(await screen.findByText("ಮೂಲ ಧ್ವನಿ ವಿಧಾನದಲ್ಲಿ ನಡೆಯುತ್ತಿದೆ. ಧ್ವನಿ ಬೇರೆ ರೀತಿ ಕೇಳಿಸಬಹುದು.")).toBeInTheDocument();
});

test("no network on opening the link: a kind message and a retry, not 'link invalid'", async () => {
  let up = false;
  fakeApi({
    "GET /api/v1/patient/good": () => {
      if (!up) throw new TypeError("Failed to fetch");
      return { body: home() };
    },
    "GET /api/v1/patient/good/messages": () => ({ body: [] }),
    "GET /api/v1/patient/good/reminders/today": () => ({ body: { recovery_day: 3, language: "kn", reminders: [] } }),
    "GET /api/v1/system/status": () => ({ body: { mode: "demo", key_not_set: false, providers: [], channels: [], modules: [] } }),
  });
  open("/p/good");
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Cannot reach the hospital right now");
  expect(alert).not.toHaveTextContent("not working any more");
  up = true;
  await userEvent.click(within(alert).getByRole("button", { name: /Try again/ }));
  expect(await screen.findByRole("heading", { name: "Ramesh" })).toBeInTheDocument();
});
