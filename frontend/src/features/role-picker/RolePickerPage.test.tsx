import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { routes } from "@/app/routes";

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("main screen offers the doctor and patient roles", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ status: "ok", mode: "demo", version: "0.1.0" })),
  );
  renderAt("/");
  expect(screen.getByRole("link", { name: /I'm a doctor/ })).toHaveAttribute("href", "/doctor");
  expect(screen.getByRole("link", { name: /I'm a patient/ })).toHaveAttribute("href", "/patient");
  expect(await screen.findByText(/Demo mode/)).toBeInTheDocument();
});

test("unknown screens show a placeholder, not a blank page", () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({})));
  renderAt("/somewhere-not-built");
  expect(screen.getByText(/on its way/)).toBeInTheDocument();
});
