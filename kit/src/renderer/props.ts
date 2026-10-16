// Hand-written zod mirror of contracts/schemas/village_spec.schema.json#/$defs/props_* (contract 1.3.3).
// Strict objects = additionalProperties:false. Keep in sync with the contract; tests parse both fixtures.
import { z } from "zod";

const label = z.string().min(1).max(60);
const memberId = z.string().regex(/^[a-z]_[a-z0-9_]{1,40}$/);
const slot = z.string().regex(/^[a-z][a-z0-9_]{1,23}$/);
const slotList = z.array(slot).min(1).max(6);
const stringList = z.array(z.string().max(80)).max(24);
const memberList = z.array(memberId).max(24);
const hexColor = z.string().regex(/^#[0-9A-Fa-f]{6}$/);
const weekday = z.enum(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]);
const url = z.string().regex(/^https?:\/\//);
const phoneOrShort = z.string().regex(/^(\+[1-9][0-9]{6,14}|911|988|18002221222)$/);
const lifeAreaId = z.enum(["health", "money", "people", "home", "daily_living", "information"]);
const icon = z.enum(["pill", "sos", "phone", "check", "heart", "home", "help", "water", "bolt", "car", "shield", "question"]);
const buttonTone = z.enum(["ok", "info", "warn", "danger"]);
const textTone = z.enum(["neutral", "muted", "info", "ok", "warn", "danger"]);
export const actionName = z.enum([
  "log_dose", "need_help", "call_member", "call_number", "check_in_ok", "report_symptom", "report_need", "offer_resource",
  "check_rumor", "ack_alert", "swap_shift", "approve_match", "start_verification", "answer_verification", "ack_incident",
  "approve_proposal", "reject_proposal"
]);
const BIND_RE =
  /^(facts:[a-z_]+(\?[a-z_]+=[A-Za-z0-9_]+(&[a-z_]+=[A-Za-z0-9_]+)*)?|timeline:subject=[a-z]_[a-z0-9_]+|rota:(current|week)(\.(on_duty|backup))?(\?member=me)?|alerts:active(\?count)?|needs:(open|matched)(\?count)?|resources:available(\?count)?|claims:(topic=[a-z_]+)(\?count)?|checkins:(village|overdue)(\?count)?|calls:line=[a-z-]+|decisions:recent|member:[a-z]_[a-z0-9_]+|incidents:(open|all|subject=[a-z]_[a-z0-9_]+)(\?count)?|verifications:(mine|pending\?member=me)|proposals:pending(\?count)?|blueprint:life_areas|chat:village(\?count)?|prescriptions:current|rounds:latest|events:since_last_turn\?member=me|plan:[a-z0-9_]+|calls:screened|facts:history\?subject=[a-z]_[a-z0-9_]+&key=[a-z0-9_]+)$/;
const bind = z.string().regex(BIND_RE);
const eventKind = z.string().regex(/^[a-z_]+$/);
const s = z.strictObject;

export const propsByType = {
  Screen: s({ title: label, subtitle: label.optional(), read_aloud: z.boolean().optional() }),
  Stack: s({ direction: z.enum(["vertical", "horizontal"]).optional(), gap: z.enum(["s", "m", "l"]).optional(), title: label.optional() }),
  Header: s({ text: label, level: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional() }),
  Text: s({ text: z.string().min(1).max(280), size: z.enum(["m", "l", "xl"]).optional(), tone: textTone.optional() }),
  BigButton: s({
    label, action: actionName, action_arg: z.string().max(80).optional(), icon: icon.optional(), tone: buttonTone.optional(),
    confirm: z.boolean().optional(), confirm_text: z.string().max(120).optional(), speak: z.string().max(120).optional()
  }).superRefine((v, ctx) => {
    if (v.tone === "danger" && (v.confirm !== true || !v.confirm_text)) {
      ctx.addIssue({ code: "custom", message: "danger BigButton requires confirm:true and confirm_text" });
    }
  }),
  Alert: s({
    source: z.enum(["policy", "official", "coordinator"]), bind,
    severity_levels: z.array(z.enum(["danger", "warn", "info"])).optional(), dismissible: z.boolean().optional(),
    empty_text: z.string().max(80).optional(), show_escalation_status: z.boolean().optional(), show_countdown: z.boolean().optional()
  }),
  StatusGrid: s({ labels: stringList, binds: z.array(bind).max(24), title: label.optional() }).refine((v) => v.labels.length === v.binds.length, "labels/binds length mismatch"),
  ContactCard: s({
    name: label, kind: z.enum(["family", "clinician", "pharmacy", "emergency", "hotline", "utility", "volunteer"]),
    phone: phoneOrShort.optional(), member_id: memberId.optional(), bind: bind.optional(), label: label.optional(), big: z.boolean().optional()
  }).refine((v) => v.phone || v.member_id || v.bind, "ContactCard needs phone, member_id or bind"),
  SourceCard: s({ source_name: label, url, refresh_minutes: z.number().int().min(1).max(1440).optional(), bind: bind.optional() }),
  DoseTracker: s({
    subject: memberId, slots: slotList, bind, title: label.optional(), show_med_names: z.boolean().optional(),
    allow_log: z.boolean().optional(), big: z.boolean().optional()
  }),
  CareRota: s({
    bind, title: label.optional(), period: z.enum(["day", "week"]).optional(), highlight_current_user: z.boolean().optional(),
    allow_swap: z.boolean().optional(), show_backup: z.boolean().optional()
  }),
  Timeline: s({
    bind, title: label.optional(), subject: memberId.optional(), event_kinds: z.array(eventKind).max(24).optional(),
    show_superseded: z.boolean().optional(), show_provenance: z.boolean().optional(), limit: z.number().int().min(1).max(100).optional()
  }),
  SymptomLog: s({
    subject: memberId, fields: z.array(z.enum(["blood_pressure", "blood_sugar", "mood", "dizziness", "pain", "sleep", "free_text"])).min(1),
    bind, title: label.optional(), options: z.array(z.string().max(40)).max(6).optional(), allow_voice_entry: z.boolean().optional(), big: z.boolean().optional()
  }),
  CallLog: s({
    line_ids: z.array(z.enum(["mom-line", "block-line", "village-caller"])).min(1), bind, title: label.optional(),
    show_policy_decisions: z.boolean().optional(), limit: z.number().int().min(1).max(100).optional()
  }),
  NeedBoard: s({
    bind, priority_order: stringList, title: label.optional(), show_fields: stringList.optional(),
    redact_for_roles: stringList.optional(), allow_match: z.boolean().optional()
  }),
  ResourceBoard: s({ bind, resource_types: stringList.optional(), title: label.optional(), show_constraints: z.boolean().optional() }),
  VerifiedInfoFeed: s({
    bind, topics: stringList, title: label.optional(),
    trust_levels_shown: z.array(z.enum(["official", "verified_volunteer", "unverified_neighbor"])).optional(),
    hide_unverified_for_roles: stringList.optional()
  }),
  CheckIn: s({
    subjects: memberList, bind, title: label.optional(), interval_minutes: z.number().int().min(5).optional(),
    escalate_after_minutes: z.number().int().min(5).optional(), big: z.boolean().optional()
  }),
  Checklist: s({
    items: stringList, title: label.optional(), owners: z.array(z.string().regex(/^([a-z]_[a-z0-9_]{1,40})?$/)).max(24).optional(),
    recurring: z.boolean().optional(), bind: bind.optional()
  }),
  ScamCheck: s({
    label, choices_member_ids: z.array(memberId).min(1).max(3), bind: z.literal("verifications:mine"),
    other_label: label.optional(), speak: z.string().max(120).optional(), big: z.boolean().optional()
  }),
  IncidentCard: s({
    bind, title: label.optional(), subject: memberId.optional(), show_red_flags: z.boolean().optional(),
    show_verification: z.boolean().optional(), show_provenance: z.boolean().optional(), allow_ack: z.boolean().optional(),
    limit: z.number().int().min(1).max(20).optional()
  }),
  LifeAreas: s({
    bind: z.literal("blueprint:life_areas"), areas: z.array(lifeAreaId).min(1), title: label.optional(),
    show_rules: z.boolean().optional(), show_contacts: z.boolean().optional()
  }),
  VerificationPrompt: s({
    bind: z.literal("verifications:pending?member=me"), yes_label: label, no_label: label,
    question_template: z.string().max(160).optional(), show_countdown: z.boolean().optional()
  }),
  HelperAnswer: s({ question: label, bind, subject: memberId.optional(), show_status: z.boolean().optional(), show_next_shift: z.boolean().optional() }),
  Proposal: s({ bind, title: label.optional(), allow_approve: z.boolean().optional(), show_evidence: z.boolean().optional(), show_release_status: z.boolean().optional() }),
  PillOrganizer: s({
    subject: memberId, slots: slotList, lid_colors: z.array(hexColor).min(1).max(6), labels: z.array(z.string().max(20)).min(1).max(6),
    bind, title: label.optional(), days: z.array(weekday).optional(), show_today_only: z.boolean().optional()
  }).refine((v) => v.slots.length === v.lid_colors.length && v.slots.length === v.labels.length, "slots/lid_colors/labels length mismatch"),
  VillageChat: s({
    bind: z.literal("chat:village"), composer: z.boolean(), title: label.optional(), mention_label: z.string().max(20).optional(),
    allow_approve: z.boolean().optional(), limit: z.number().int().min(1).max(50).optional()
  }),
  // 1.3.3 (D22)
  RefillCard: s({
    bind: z.literal("prescriptions:current"), title: label.optional(), owner: label.optional(), day: label.optional(),
    show_superseded: z.boolean().optional(), show_schedule: z.boolean().optional(), show_source: z.boolean().optional()
  }),
  TonightCard: s({ bind: z.string().regex(/^rota:current\.(on_duty|backup)$/), title: label.optional(), template: z.string().max(60).optional() }),
  // 1.3.3 (UX-UPGRADE)
  RightNow: s({ bind, title: label.optional(), show_asks: z.boolean().optional() }),
  WhatVillageDid: s({ bind, title: label.optional(), max_rows: z.number().int().min(1).max(12).optional() }),
  SinceYourTurn: s({ bind, title: label.optional(), max_rows: z.number().int().min(1).max(6).optional() }),
  PlanBoard: s({ bind, title: label.optional(), date: z.string().max(40).optional(), allow_claim: z.boolean().optional() }),
  ScreenedCalls: s({ bind, title: label.optional(), max_rows: z.number().int().min(1).max(12).optional() }),
  FactCard: s({ bind, title: label.optional(), show_as_of: z.boolean().optional() })
} as const;

export type CatalogType = keyof typeof propsByType;
export const CONTRACT_TYPES = Object.keys(propsByType) as CatalogType[];

export function isCatalogType(type: string): type is CatalogType {
  return Object.prototype.hasOwnProperty.call(propsByType, type);
}

export function parseProps(type: string, props: unknown): { ok: true; data: Record<string, unknown> } | { ok: false; error: string } {
  if (!isCatalogType(type)) return { ok: false, error: `unknown type ${type}` };
  const res = (propsByType[type] as z.ZodTypeAny).safeParse(props ?? {});
  return res.success ? { ok: true, data: res.data as Record<string, unknown> } : { ok: false, error: res.error.issues.map((i) => i.message).join("; ") };
}
