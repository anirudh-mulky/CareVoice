import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";
import { installSynthesis, removeSynthesis, voice } from "@/test/fakeSpeech";

const CARD = {
  language: "kn",
  translated: true,
  title: "ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ",
  greeting: "Ramesh, ನಿಮ್ಮ ಕಣ್ಣಿನ ಪೊರೆ ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ ನಂತರದ ಆರೈಕೆ ಮಾಹಿತಿ ಇಲ್ಲಿದೆ.",
  red_flags_title: "ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಆದರೆ ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ",
  red_flags: ["ದೃಷ್ಟಿ ಇದ್ದಕ್ಕಿದ್ದಂತೆ ಕಡಿಮೆಯಾದರೆ ಅಥವಾ ಕಾಣಿಸದಿದ್ದರೆ", "ಕಣ್ಣು ಹೆಚ್ಚು ಕೆಂಪಾಗುತ್ತಿದ್ದರೆ"],
  medicines: [{ name: "Moxifloxacin 0.5% eye drops", instructions: "ದಿನಕ್ಕೆ 4 ಬಾರಿ, 1 ಹನಿ, 7 ದಿನ" }],
  dos: ["ಹೊರಗೆ ಹೋಗುವಾಗ ಕಪ್ಪು ಕನ್ನಡಕ ಧರಿಸಿ"],
  donts: ["ಆಪರೇಷನ್ ಆದ ಕಣ್ಣನ್ನು ಉಜ್ಜಬೇಡಿ ಅಥವಾ ಒತ್ತಬೇಡಿ"],
  extras: [{ text: "Diabetic so check sugar daily", translated: false }],
  follow_up: "7ನೇ ದಿನ ತಪಾಸಣೆಗೆ ಬನ್ನಿ",
  labels: { medicines: "ನಿಮ್ಮ ಔಷಧಿಗಳು", do: "ಹೀಗೆ ಮಾಡಿ", dont: "ಹೀಗೆ ಮಾಡಬೇಡಿ", extras: "ನಿಮ್ಮ ವೈದ್ಯರು ಇದನ್ನೂ ಹೇಳಿದ್ದಾರೆ" },
};
const home = (viewer: { type: string; name: string }, card = CARD) => ({
  patient_name: "Ramesh",
  viewer,
  language: card.language,
  hospital: { name: "CareVoice Demo Hospital", phone: "+91 90000 00000" },
  status: "sent",
  recovery_day: 3,
  card,
});
const NOTE = {
  id: "m-1",
  direction: "to_patient",
  kind: "instructions",
  text: "Ramesh, ನಿಮ್ಮ ಆರೈಕೆ ಮಾಹಿತಿ. ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಆದರೆ ಇಂದೇ ಆಸ್ಪತ್ರೆಗೆ ಬನ್ನಿ.",
  text_en: "Ramesh, your care card.",
  language: "kn",
  audio_url: null,
  played_at: null,
  created_at: "2026-11-27T10:00:00Z",
};

function server(viewer = { type: "patient", name: "Ramesh" }, card = CARD) {
  return fakeApi({
    "GET /api/v1/patient/good": () => ({ body: home(viewer, card) }),
    "GET /api/v1/patient/good/messages": () => ({ body: [NOTE] }),
    "POST /api/v1/patient/good/messages/:id/played": () => ({ status: 204, body: null }),
    "GET /api/v1/patient/bad": () => ({
      status: 404,
      body: { error: { code: "link_invalid", message: "This link is not valid any more." } },
    }),
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

afterEach(() => {
  vi.unstubAllGlobals();
  removeSynthesis();
});

test("the patient link shows the Kannada card with red flags first", async () => {
  server();
  open("/p/good");
  const redFlags = await screen.findByRole("heading", { name: CARD.red_flags_title });
  const headings = screen.getAllByRole("heading").map((h) => h.textContent);
  expect(headings.indexOf(CARD.red_flags_title)).toBeLessThan(headings.indexOf("ನಿಮ್ಮ ಔಷಧಿಗಳು"));
  expect(within(redFlags.closest("section")!).getByText(CARD.red_flags[0]!)).toBeInTheDocument();
  expect(screen.getByText("ಚೇತರಿಕೆಯ 3ನೇ ದಿನ")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /ಆಸ್ಪತ್ರೆಗೆ ಕರೆ ಮಾಡಿ/ })).toHaveAttribute("href", "tel:+919000000000");
  expect(screen.getByText("ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ (ಇನ್ನೂ ಅನುವಾದವಾಗಿಲ್ಲ)")).toBeInTheDocument();
  expect(screen.getByText(/ಈ ಆ್ಯಪ್ ನಿಮ್ಮ ವೈದ್ಯರಿಗೆ ಬದಲಿಯಲ್ಲ/)).toBeInTheDocument();
});

test("the care card plays aloud in Kannada and the play is recorded", async () => {
  const spoken = installSynthesis([voice("kn-IN")]);
  const calls = server();
  open("/p/good");
  await screen.findByText("ನಿಮ್ಮ ಆರೈಕೆ ಮಾಹಿತಿ ಕೇಳಿ");
  const player = screen.getByText("ನಿಮ್ಮ ಆರೈಕೆ ಮಾಹಿತಿ ಕೇಳಿ").parentElement!;
  await userEvent.click(within(player).getByRole("button", { name: "ಕೇಳಿ" }));
  await waitFor(() => expect(spoken.length).toBeGreaterThan(0));
  expect(spoken.every((s) => s.lang === "kn-IN")).toBe(true);
  await waitFor(() => expect(calls.some((c) => c.path.endsWith("/m-1/played"))).toBe(true));
});

test("the carer's link shows the same card, marked as the carer view", async () => {
  server({ type: "carer", name: "Kiran" });
  open("/p/good");
  expect(await screen.findByText("ಆರೈಕೆದಾರರ ನೋಟ: Ramesh ಅವರ ಆರೈಕೆ ಮಾಹಿತಿ")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: CARD.red_flags_title })).toBeInTheDocument();
});

test("an expired link explains what to do", async () => {
  server();
  open("/p/bad");
  expect(await screen.findByRole("alert")).toHaveTextContent("Please call the hospital");
});

test("the chat shows the care team's voice note", async () => {
  server();
  open("/p/good/chat");
  expect(await screen.findByText(NOTE.text)).toBeInTheDocument();
  expect(screen.getByText("ನಿಮ್ಮ ಆರೈಕೆ ತಂಡ")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ಕೇಳಿ" })).toBeInTheDocument();
});

test("an untranslated card says it is shown in English", async () => {
  server({ type: "patient", name: "Kavya" }, { ...CARD, language: "en", translated: false });
  open("/p/good");
  expect(await screen.findByRole("note")).toHaveTextContent("Not yet translated into your language");
});
