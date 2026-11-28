/** Route fetch() calls to handlers by "METHOD /path" for component tests. */
import { vi } from "vitest";

type Handler = (body: unknown, url: URL) => { status?: number; body: unknown };

export function fakeApi(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; body: unknown; headers: Headers }[] = [];
  const fetchMock = vi.fn(async (input: Request | string) => {
    const request = typeof input === "string" ? new Request(input) : input;
    const url = new URL(request.url);
    const text = request.method === "GET" ? "" : await request.text();
    const body = text ? JSON.parse(text) : undefined;
    calls.push({ method: request.method, path: url.pathname, body, headers: request.headers });
    const key = Object.keys(routes).find((k) => {
      const [method, pattern] = k.split(" ");
      const re = new RegExp(`^${(pattern ?? "").replace(/:\w+/g, "[^/]+")}$`);
      return method === request.method && re.test(url.pathname);
    });
    if (!key) return Response.json({ error: { code: "not_found", message: "no route" } }, { status: 404 });
    const res = routes[key]!(body, url);
    if (res.status === 204) return new Response(null, { status: 204 });
    return Response.json(res.body, { status: res.status ?? 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}
