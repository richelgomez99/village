// D18 caption glossary: English for every Spanish string a projector surface can show.
// Sources, in order: live control{kind:"caption"} pairs (addCaption; the fake server registers its fixture lines the
// same way), the kit's own es/en string tables (reverse map), common elder-view copy, then patterns for templated lines.
import { tablesFor } from "./strings";

const live = new Map<string, string>();

const FIXED: Record<string, string> = {
  "Llamar a Village": "Call Village",
  "Necesito ayuda": "I need help",
  "Emergencia: 911": "Emergency: 911",
  "¿Aviso a su familia ahora?": "Tell your family now?",
  "Llame a Village: [NÚMERO]": "Call Village: [NUMBER]",
  "Village nunca pide dinero ni códigos.": "Village never asks for money or codes.",
  "Emergencia: llame al 911 primero.": "Emergency: call 911 first."
};

const PATTERNS: [RegExp, string][] = [
  [/^Esta noche cuida (.+)$/, "Tonight $1 is looking after her"],
  [/^Llamar a (.+)$/, "Call $1"],
  [/^Llamando a (.+)$/, "Calling $1"],
  [/^Hola, (.+)$/, "Hello, $1"],
  [/^Eres (.+) · (.+)$/, "You're $1 · $2"]
];

let reverse: Map<string, string> | null = null;
function kitReverse(): Map<string, string> {
  if (reverse) return reverse;
  reverse = new Map();
  const { es, en } = tablesFor();
  for (const key of Object.keys(en) as (keyof typeof en)[]) {
    const e = es[key];
    if (e && !e.includes("{") && e !== en[key]) reverse.set(e, en[key]);
  }
  return reverse;
}

export function addCaption(es: string, en: string) {
  if (es && en && es !== en) live.set(es.trim(), en.trim());
}

/** English line for a Spanish string, or null when it isn't known (callers then show nothing extra). */
export function captionFor(es: string): string | null {
  const t = es.trim();
  if (!t) return null;
  const hit = live.get(t) ?? FIXED[t] ?? kitReverse().get(t);
  if (hit) return hit;
  for (const [re, out] of PATTERNS) if (re.test(t)) return t.replace(re, out);
  return null;
}
