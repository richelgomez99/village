import { createContext, useContext } from "react";
import type { View } from "./view";
import type { ApiConfig } from "../control/api";

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
  /** tel: number for a call target (member id, "village", or a literal number); null = no number known. */
  phoneFor?: (target: string) => string | null;
  /** REST access for read-only lookups inside components (fact history); absent = those affordances hide. */
  api?: ApiConfig;
  /** tabbed member app: jump to the Chat tab, optionally with a composer prefill ("@Village can someone swap Friday?"). */
  openChat?: (prefill?: string, opts?: { send?: boolean }) => void;
  /** set with chatDraft: VillageChat sends the draft at once (Swap → "@Village can someone cover Friday for me?") */
  chatAutoSend?: boolean;
  /** composer prefill handed to VillageChat by openChat */
  chatDraft?: string;
  /** VillageChat is the full-height Chat tab panel */
  chatFull?: boolean;
  /** Home's attention group: list only what is still open (acknowledged incidents live on their area tab) */
  openOnly?: boolean;
}

const LITERAL_PHONE = /^(\+[1-9][0-9]{6,14}|911|988|18002221222)$/;

/** Phone lookup from resolved data: literal numbers, member:<id>.phone, any bv_person with that id, and the Village line. */
export function makePhoneFor(data: Record<string, unknown>, villageNumber?: string | null): (target: string) => string | null {
  return (target: string) => {
    if (!target) return null;
    if (LITERAL_PHONE.test(target)) return target;
    if (target === "village") return villageNumber ?? null;
    const m = data[`member:${target}`] as { phone?: string } | null | undefined;
    if (m?.phone) return m.phone;
    for (const v of Object.values(data)) {
      const p = v as { member_id?: string; phone?: string } | null;
      if (p && typeof p === "object" && !Array.isArray(p) && p.member_id === target && p.phone) return p.phone;
    }
    return null;
  };
}

const noop = () => "";
export const defaultCtx: RenderCtx = {
  view: { lang: "en", theme: "family", root: "s", elements: {} },
  data: {},
  lang: "en",
  role: "helper",
  memberId: null,
  village: "",
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
