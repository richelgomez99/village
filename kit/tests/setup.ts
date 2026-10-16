import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";
import { vi } from "vitest";

configure({ testIdAttribute: "data-test" });

Object.defineProperty(window, "speechSynthesis", {
  value: { speak: vi.fn(), cancel: vi.fn() },
  configurable: true
});
