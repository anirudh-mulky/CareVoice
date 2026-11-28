import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { routes } from "@/app/routes";
import { fakeApi } from "@/test/fakeApi";

const health = () => ({ body: { status: "ok", mode: "demo", version: "0.1.0" } });

function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("the header's Reset demo button restores the seed data after confirming", async () => {
  const calls = fakeApi({
    "GET /api/v1/health": health,
    "POST /api/v1/demo/reset": () => ({ body: { counts: { patients: 3 } } }),
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  open("/");

  await userEvent.click(screen.getByRole("button", { name: /Reset demo/ }));

  expect(await screen.findByText("Demo data restored.")).toBeInTheDocument();
  expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/demo/reset")).toBe(true);
});

test("cancelling the confirmation sends nothing", async () => {
  const calls = fakeApi({ "GET /api/v1/health": health });
  vi.spyOn(window, "confirm").mockReturnValue(false);
  open("/");

  await userEvent.click(screen.getByRole("button", { name: /Reset demo/ }));

  expect(calls.some((c) => c.path === "/api/v1/demo/reset")).toBe(false);
});

test("says so when the server has demo endpoints turned off", async () => {
  fakeApi({ "GET /api/v1/health": health }); // no reset route: the fake answers 404
  vi.spyOn(window, "confirm").mockReturnValue(true);
  open("/");

  await userEvent.click(screen.getByRole("button", { name: /Reset demo/ }));

  expect(await screen.findByText("Reset is turned off on this server.")).toBeInTheDocument();
});

test("the patient's own link has no reset button", async () => {
  fakeApi({ "GET /api/v1/health": health });
  open("/p/some-token");

  await screen.findByRole("contentinfo");
  expect(screen.queryByRole("button", { name: /Reset demo/ })).not.toBeInTheDocument();
});
