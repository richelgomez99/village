import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";
import { vi } from "vitest";

configure({ testIdAttribute: "data-test" });

Object.defineProperty(window, "speechSynthesis", {
  value: { speak: vi.fn(), cancel: vi.fn() },
  configurable: true
});

// some Node/jsdom combos expose a broken global localStorage; give tests a working in-memory one
if (typeof globalThis.localStorage === "undefined" || typeof (globalThis.localStorage as Storage | undefined)?.getItem !== "function") {
  const m = new Map<string, string>();
  const store = {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => void m.set(k, String(v)),
    removeItem: (k: string) => void m.delete(k),
    clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null,
    get length() { return m.size; }
  };
  Object.defineProperty(globalThis, "localStorage", { value: store, configurable: true });
  Object.defineProperty(window, "localStorage", { value: store, configurable: true });
}
