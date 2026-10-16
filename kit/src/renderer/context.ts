import { createContext, useContext } from "react";
import type { View } from "./view";

export interface ActionRequest {
  name: string;
  arg?: string;
  payload?: Record<string, unknown>;
  element_id?: string;
}

export interface ResultInfo {
  req_id: string;
  ok: boolean;
  say?: { es: string; en: string };
  error?: string;
}

export interface RenderCtx {
  view: View;
  data: Record<string, unknown>;
  lang: string;
  role: string;
  memberId: string | null;
  village: string;
  nowMs: () => number;
  /** true while viewing as someone else (D21) or in a read-only mirror. */
  disabled: boolean;
  highlight: Set<string>;
  /** last action result per element id (VerificationPrompt thanks state). */
  results: Record<string, ResultInfo | "pending">;
  send: (a: ActionRequest) => string;
  ack: (eventId: string, status?: "got_it" | "accepted" | "declined" | "not_needed") => void;
  /** D18: render an English caption under Spanish strings (projector / control surfaces). */
  captions: boolean;
}

const noop = () => "";
export const defaultCtx: RenderCtx = {
  view: { lang: "en", theme: "family", root: "s", elements: {} },
  data: {},
  lang: "en",
  role: "helper",
  memberId: null,
  village: "v_reyes",
  nowMs: () => Date.now(),
  disabled: false,
  highlight: new Set(),
  results: {},
  send: noop,
  ack: () => {},
  captions: false
};

export const Ctx = createContext<RenderCtx>(defaultCtx);
export const useCtx = () => useContext(Ctx);
