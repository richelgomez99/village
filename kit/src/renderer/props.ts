import { z } from "zod";

const loc = z.union([z.string(), z.record(z.string(), z.string())]);
const loose = z.object({}).passthrough();

export const propsByType: Record<string, z.ZodTypeAny> = {
  Screen: loose.extend({ title: loc, subtitle: loc.optional(), read_aloud: z.boolean().optional() }),
  Stack: loose,
  Header: loose.extend({ text: loc }),
  Text: loose.extend({ text: loc }),
  BigButton: loose
    .extend({
      label: loc,
      action: z.string(),
      tone: z.string().optional(),
      confirm: z.boolean().optional()
    })
    .superRefine((value, ctx) => {
      if (value.tone === "danger" && value.confirm !== true) {
        ctx.addIssue({ code: "custom", message: "danger BigButton requires confirm" });
      }
    }),
  Alert: loose.extend({ bind: z.string() }),
  StatusGrid: loose,
  ContactCard: loose.extend({ name: loc, kind: z.string().optional() }),
  SourceCard: loose,
  DoseTracker: loose.extend({ bind: z.string(), slots: z.array(z.string()).optional() }),
  CareRota: loose.extend({ bind: z.string() }),
  Timeline: loose.extend({ bind: z.string() }),
  SymptomLog: loose,
  CallLog: loose,
  NeedBoard: loose,
  ResourceBoard: loose,
  VerifiedInfoFeed: loose,
  CheckIn: loose,
  Checklist: loose,
  ScamCheck: loose,
  IncidentCard: loose.extend({ bind: z.string() }),
  LifeAreas: loose.extend({ bind: z.string() }),
  VerificationPrompt: loose.extend({ bind: z.string() }),
  HelperAnswer: loose.extend({ bind: z.string() }),
  Proposal: loose,
  PillOrganizer: loose,
  RefillCard: loose,
  VillageChat: loose
};

export function parseProps(type: string, props: unknown): Record<string, unknown> | null {
  const schema = propsByType[type] ?? loose;
  const parsed = schema.safeParse(props ?? {});
  return parsed.success ? (parsed.data as Record<string, unknown>) : null;
}
