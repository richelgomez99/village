import { z } from "zod";

export const CONTRACT_VERSION = "1.3.2" as const;

const localized = z.union([z.string(), z.record(z.string(), z.string())]);

export const snapshotFrame = z.object({
  type: z.literal("snapshot"),
  contract_version: z.string().optional(),
  rev: z.number().int().min(0),
  village: z.string(),
  role: z.string(),
  member_id: z.string().nullable(),
  spec: z.unknown(),
  data: z.record(z.string(), z.unknown()),
  now: z.string(),
  identity: z
    .object({
      member_id: z.string().nullable(), name: z.string(), role: z.string(), village_name: z.string(),
      village_number: z.string().optional(), lang: z.string().optional(), view_as: z.boolean().optional()
    })
    .optional()
});
export type Identity = NonNullable<z.infer<typeof snapshotFrame>["identity"]>;
export const patchFrame = z.object({
  type: z.literal("patch"),
  rev: z.number().int(),
  base_rev: z.number().int(),
  role: z.string().optional(),
  ops: z.array(z.object({ op: z.enum(["add", "remove", "replace"]), path: z.string(), value: z.unknown().optional() })).min(1).max(24),
  proposal_id: z.string().optional(),
  highlight: z.array(z.string()).optional()
});
export const eventFrame = z.object({
  type: z.literal("event"),
  event: z.object({ id: z.string(), kind: z.string(), at: z.string(), payload: z.record(z.string(), z.unknown()).optional() }).passthrough(),
  data: z.record(z.string(), z.unknown()).optional()
});
export const promptFrame = z.object({
  type: z.literal("prompt"),
  verification_id: z.string(),
  question: localized,
  detail: localized,
  options: z.array(z.object({ id: z.enum(["yes", "no", "unsure"]), label: localized })).min(2).max(3),
  deadline: z.string(),
  closed: z.boolean().optional()
});
export const resultFrame = z.object({
  type: z.literal("result"),
  req_id: z.string(),
  ok: z.boolean(),
  decision: z.object({ say: z.object({ es: z.string(), en: z.string() }).optional() }).passthrough().optional(),
  event_id: z.string().optional(),
  error: z.string().optional()
});
export const controlFrame = z.object({ type: z.literal("control"), kind: z.string(), payload: z.record(z.string(), z.unknown()), at: z.string() });
export const chatFrame = z.object({ type: z.literal("chat"), village: z.string(), message: z.object({ id: z.string() }).passthrough() });
export const pongFrame = z.object({ type: z.literal("pong"), ts: z.number() });
export const errorFrame = z.object({ type: z.literal("error"), code: z.enum(["bad_token", "contract_mismatch", "bad_message", "not_allowed", "rate_limited"]), message: z.string() });

export const serverFrameSchema = z.discriminatedUnion("type", [
  snapshotFrame, patchFrame, eventFrame, promptFrame, resultFrame, controlFrame, chatFrame, pongFrame, errorFrame
]);

export type ServerFrame = z.infer<typeof serverFrameSchema>;
export type SnapshotFrame = z.infer<typeof snapshotFrame>;
export type PromptFrame = z.infer<typeof promptFrame>;
export type ControlFrame = z.infer<typeof controlFrame>;
export type ClientName = "kit" | "control" | "scan_page" | "test";

export interface ClientHello {
  type: "hello";
  contract_version: typeof CONTRACT_VERSION;
  village: string;
  member_token: string;
  last_rev?: number;
  client: ClientName;
  /** D21 View-as (contract 1.3.2 hello.view_as). */
  view_as?: string;
}
