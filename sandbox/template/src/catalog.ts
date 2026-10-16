// Pure catalog + style tokens. Components (render.ts) and the generated floor tests
// both use styleFor(), so the tests check exactly what the phone renders.
import theme from "./village/theme.json";

export const CATALOG = [
  "Screen", "Stack", "Header", "Text", "BigButton", "Alert", "StatusGrid", "ContactCard", "SourceCard",
  "DoseTracker", "CareRota", "Timeline", "SymptomLog", "CallLog", "NeedBoard", "ResourceBoard",
  "VerifiedInfoFeed", "CheckIn", "Checklist", "ScamCheck", "IncidentCard", "LifeAreas",
  "VerificationPrompt", "HelperAnswer", "Proposal", "PillOrganizer", "VillageChat", "RefillCard", "TonightCard",
  "RightNow", "WhatVillageDid", "SinceYourTurn", "PlanBoard", "ScreenedCalls", "FactCard",
] as const;

export type ThemeName = "elder" | "family" | "dashboard";
export type Tone = keyof typeof theme.tones;
export type Props = Record<string, unknown>;

export interface Style {
  role: "headline" | "actionable" | "body" | "secondary";
  fontSize: number;
  minHeight: number;
  color: string;
  background: string;
  bar: string;
}

export const THEME = theme;

export function isCatalogType(type: string): boolean {
  return (CATALOG as readonly string[]).includes(type) || /^Custom[A-Z][A-Za-z0-9]{2,28}$/.test(type);
}

function toneOf(type: string, props: Props): Tone {
  const t = String(props.tone ?? (type === "ContactCard" && props.kind === "emergency" ? "danger" : "neutral"));
  return (t in theme.tones ? t : "neutral") as Tone;
}

/** Style of an element's primary text. role decides the floor that applies (D17). */
export function styleFor(type: string, props: Props, themeName: ThemeName): Style {
  const th = theme.themes[themeName];
  const tone = theme.tones[toneOf(type, props)];
  if (type === "Screen" || type === "Header") {
    return { role: "headline", fontSize: th.headline_px, minHeight: 0, color: th.text, background: th.bg, bar: theme.accent };
  }
  if (type === "BigButton" || type === "ContactCard" || type === "CheckIn" || type === "HelperAnswer" || type === "VerificationPrompt") {
    return { role: "actionable", fontSize: th.text_px, minHeight: th.button_px, color: tone.fg, background: tone.bg, bar: tone.bar };
  }
  if (type === "Text") {
    const size = props.size === "xl" ? th.headline_px : props.size === "l" ? th.text_px : th.min_px;
    return { role: props.size === "m" ? "secondary" : "body", fontSize: size, minHeight: 0, color: tone.fg, background: th.bg, bar: tone.bar };
  }
  return { role: "body", fontSize: th.text_px, minHeight: th.tap_px, color: th.text, background: theme.floor.surface, bar: tone.bar };
}

/** Secondary text inside a card (e.g. phone numbers, captions). Never below the theme minimum. */
export function secondaryPx(themeName: ThemeName): number {
  return theme.themes[themeName].min_px;
}
