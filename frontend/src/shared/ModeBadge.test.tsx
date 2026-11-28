import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach } from "vitest";
import { fakeApi } from "@/test/fakeApi";
import { ModeBadge } from "./ModeBadge";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModeBadge />
    </QueryClientProvider>,
  );
}

const status = (over: object) => () => ({
  body: { mode: "demo", key_not_set: false, providers: [], channels: [], modules: [], ...over },
});

afterEach(() => vi.unstubAllGlobals());

test("demo mode with no keys asked for says so", async () => {
  fakeApi({
    "GET /api/v1/health": () => ({ body: { status: "ok", mode: "demo", version: "0.1.0" } }),
    "GET /api/v1/system/status": status({}),
  });
  show();
  expect(await screen.findByText(/Demo mode · no keys needed/)).toBeInTheDocument();
});

test("real mode without a key shows Key not set, naming the provider", async () => {
  fakeApi({
    "GET /api/v1/health": () => ({ body: { status: "ok", mode: "real", version: "0.1.0" } }),
    "GET /api/v1/system/status": status({
      key_not_set: true,
      providers: [
        { kind: "stt", requested: "sarvam", active: "demo", mode: "demo", status: "key_not_set", detail: "" },
        { kind: "llm", requested: "anthropic", active: "anthropic", mode: "real", status: "ok", detail: "" },
      ],
    }),
  });
  show();
  const badge = await screen.findByText(/Key not set, using demo mode/);
  expect(badge).toHaveAttribute("title", "No key for: stt (sarvam)");
  expect(screen.queryByText(/Live providers/)).not.toBeInTheDocument();
});

test("an unexpected status reply falls back to the health badge instead of crashing", async () => {
  fakeApi({
    "GET /api/v1/health": () => ({ body: { status: "ok", mode: "demo", version: "0.1.0" } }),
    "GET /api/v1/system/status": () => ({ body: { status: "ok" } }),
  });
  show();
  expect(await screen.findByText(/Demo mode · no keys needed/)).toBeInTheDocument();
});

test("real mode with every key set shows live providers", async () => {
  fakeApi({
    "GET /api/v1/health": () => ({ body: { status: "ok", mode: "real", version: "0.1.0" } }),
    "GET /api/v1/system/status": status({
      mode: "real",
      providers: [{ kind: "llm", requested: "anthropic", active: "anthropic", mode: "real", status: "ok", detail: "" }],
    }),
  });
  show();
  expect(await screen.findByText(/Live providers/)).toBeInTheDocument();
});

test("real mode with every provider still on the browser is shown as demo mode", async () => {
  fakeApi({
    "GET /api/v1/health": () => ({ body: { status: "ok", mode: "real", version: "0.1.0" } }),
    "GET /api/v1/system/status": status({
      mode: "real",
      providers: [{ kind: "stt", requested: "browser", active: "demo", mode: "demo", status: "ok", detail: "" }],
    }),
  });
  show();
  expect(await screen.findByText(/Demo mode · no keys needed/)).toBeInTheDocument();
  expect(screen.queryByText(/Live providers/)).not.toBeInTheDocument();
});
