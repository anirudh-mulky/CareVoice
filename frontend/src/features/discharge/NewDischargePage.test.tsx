import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach } from "vitest";
import { fakeApi } from "@/test/fakeApi";
import { removeRecognition } from "@/test/fakeSpeech";
import { NewDischargePage } from "./NewDischargePage";

const CATARACT = { id: "t-cat", version: 1, name: "Cataract surgery", condition: "cataract" };
const card = (extra: string[]) => ({
  patient_name: "Ramesh",
  age: 68,
  template_id: "t-cat",
  template_name: "Cataract surgery",
  side: "right",
  language: "kn",
  carer_phone: null,
  extra_instructions: extra,
});
const out = (extra: string[], unclear: string[], status = "draft") => ({
  id: "d-1",
  status,
  card: card(extra),
  unclear_fields: unclear,
  patient: { id: "p-1", name: "Ramesh", age: 68, preferred_language: "kn" },
  template_version: 1,
  discharged_on: "2026-11-27",
  recovery_day: 1,
  approved_at: status === "sent" ? "2026-11-27T10:00:00Z" : null,
  created_at: "2026-11-27T10:00:00Z",
});

/** Unclear while any extra mentions drops without a dose, like the real server. */
const unclearOf = (extras: string[]) =>
  extras.flatMap((e, i) => (/drops/i.test(e) && !/\d/.test(e) ? [`extra_instructions[${i}]`] : []));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NewDischargePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function serverWith(extras: string[]) {
  let current = extras;
  return fakeApi({
    "GET /api/v1/discharges/templates": () => ({ body: [CATARACT] }),
    "POST /api/v1/discharges/extract": (body) => ({
      body: {
        transcript: (body as { transcript: string }).transcript,
        card: card(current),
        unclear_fields: unclearOf(current),
        matched_patient: { id: "p-1", name: "Ramesh", age: 68, preferred_language: "kn" },
        source: "rules",
        needs_review: false,
      },
    }),
    "POST /api/v1/discharges": (body) => {
      current = (body as { extra_instructions: string[] }).extra_instructions;
      return { status: 201, body: out(current, unclearOf(current)) };
    },
    "PATCH /api/v1/discharges/:id": (body) => {
      current = (body as { extra_instructions: string[] }).extra_instructions;
      return { body: out(current, unclearOf(current)) };
    },
    "POST /api/v1/discharges/:id/approve": () =>
      unclearOf(current).length
        ? { status: 422, body: { error: { code: "unclear_fields", message: "Fix", details: { unclear_fields: unclearOf(current) } } } }
        : { body: { outcome: "approved", discharge: out(current, [], "sent") } },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  removeRecognition();
});

async function dictate(text: string) {
  removeRecognition(); // no mic in tests: the type-instead box is open
  await userEvent.type(await screen.findByRole("textbox"), `${text}{Enter}`);
  await screen.findByText("Discharge card");
}

test("the Ramesh sentence fills the card and can be approved", async () => {
  const calls = serverWith(["Diabetic so check sugar daily"]);
  renderPage();
  await dictate("Ramesh, 68, cataract right eye, standard template, diabetic so check sugar daily, language Kannada.");

  expect(screen.getByLabelText("Patient name")).toHaveValue("Ramesh");
  expect(screen.getByLabelText("Age")).toHaveValue(68);
  expect(screen.getByLabelText("Template")).toHaveValue("t-cat");
  expect(screen.getByLabelText("Side")).toHaveValue("right");
  expect(screen.getByLabelText("Patient's language")).toHaveValue("kn");
  expect(screen.getByLabelText("Instruction 1")).toHaveValue("Diabetic so check sugar daily");

  const approve = screen.getByRole("button", { name: /approve and send/i });
  await waitFor(() => expect(approve).toBeEnabled());
  await userEvent.click(approve);
  expect(await screen.findByText("Discharge approved")).toBeInTheDocument();
  const approveCall = calls.find((c) => c.path.endsWith("/approve"));
  expect(approveCall?.headers.get("Idempotency-Key")).toBeTruthy();
});

test("an unclear dose turns yellow and blocks Approve until fixed", async () => {
  const calls = serverWith(["Add timolol drops"]);
  renderPage();
  await dictate("Ramesh, 68, cataract right eye, language Kannada, add timolol drops");

  const extra = screen.getByLabelText("Instruction 1");
  await waitFor(() => expect(extra.closest("[data-unclear]")).not.toBeNull());
  expect(screen.getByText("Say or type the exact dose and how often.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /approve and send/i })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("1 field needs checking");

  await userEvent.clear(extra);
  await userEvent.type(extra, "Timolol 1 drop twice daily");
  await waitFor(() => expect(screen.getByLabelText("Instruction 1").closest("[data-unclear]")).toBeNull(), { timeout: 3000 });
  const approve = screen.getByRole("button", { name: /approve and send/i });
  await waitFor(() => expect(approve).toBeEnabled());
  await userEvent.click(approve);
  expect(await screen.findByText("Discharge approved")).toBeInTheDocument();
  expect(calls.filter((c) => c.method === "PATCH").at(-1)?.body).toMatchObject({
    extra_instructions: ["Timolol 1 drop twice daily"],
  });
});

test("a double click on Approve sends one request", async () => {
  const calls = serverWith([]);
  renderPage();
  await dictate("Ramesh, 68, cataract right eye, language Kannada");
  const approve = screen.getByRole("button", { name: /approve and send/i });
  await waitFor(() => expect(approve).toBeEnabled());
  await userEvent.dblClick(approve);
  await screen.findByText("Discharge approved");
  expect(calls.filter((c) => c.path.endsWith("/approve"))).toHaveLength(1);
});
