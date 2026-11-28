import type { ComponentType } from "react";

/**
 * Route-level code splitting. Each screen is downloaded only when it is opened, so a patient on
 * a low-end phone never loads the doctor's screens.
 *
 *   { path: "chat", lazy: page(() => import("./ChatPage"), (m) => m.ChatPage) }
 */
export function page<M>(load: () => Promise<M>, pick: (module: M) => ComponentType) {
  return async () => ({ Component: pick(await load()) });
}
