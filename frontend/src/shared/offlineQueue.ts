/**
 * Outbox for things said while offline (spec: "Queue the recording in IndexedDB and retry").
 * IndexedDB keeps the audio too; where it is missing, localStorage keeps the text only.
 */

export type QueuedReport = {
  id: string;
  token: string;
  transcript: string;
  language: string;
  confidence: number | null;
  audio?: Blob;
  mimeType?: string;
  createdAt: number;
};

const DB_NAME = "carevoice";
const STORE = "outbox";
const LOCAL_KEY = "carevoice.outbox";

function openDb(): Promise<IDBDatabase | null> {
  if (!("indexedDB" in globalThis) || !globalThis.indexedDB) return Promise.resolve(null);
  return new Promise((resolve) => {
    const req = globalThis.indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(null);
  });
}

function tx<T>(db: IDBDatabase, mode: IDBTransactionMode, work: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = work(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function readLocal(): QueuedReport[] {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) ?? "[]") as QueuedReport[];
  } catch {
    return [];
  }
}

export async function enqueue(item: Omit<QueuedReport, "id" | "createdAt">): Promise<void> {
  const full: QueuedReport = { ...item, id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()), createdAt: Date.now() };
  const db = await openDb();
  if (db) {
    await tx(db, "readwrite", (s) => s.put(full));
    return;
  }
  const textOnly: QueuedReport = { ...full, audio: undefined }; // localStorage cannot hold audio
  localStorage.setItem(LOCAL_KEY, JSON.stringify([...readLocal(), textOnly]));
}

export async function pending(token: string): Promise<QueuedReport[]> {
  const db = await openDb();
  const all = db ? await tx<QueuedReport[]>(db, "readonly", (s) => s.getAll()) : readLocal();
  return all.filter((q) => q.token === token).sort((a, b) => a.createdAt - b.createdAt);
}

export async function remove(id: string): Promise<void> {
  const db = await openDb();
  if (db) {
    await tx(db, "readwrite", (s) => s.delete(id));
    return;
  }
  localStorage.setItem(LOCAL_KEY, JSON.stringify(readLocal().filter((q) => q.id !== id)));
}

/** fetch() rejects with a TypeError when there is no network; the browser may also know. */
export function isOffline(err: unknown): boolean {
  return err instanceof TypeError || (typeof navigator !== "undefined" && navigator.onLine === false);
}
