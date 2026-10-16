import { useEffect, useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { Bi, Card, memberName } from "./shared";
import { fmtTime } from "../util/time";
import type { ApiConfig } from "../control/api";

/** V0 renderer for block-village boards (NeedBoard, ResourceBoard, …): title + bound rows. Full versions are T031. */
export function GenericBoard({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const el = ctx.view.elements[id];
  const v = props.bind ? ctx.data[props.bind] : undefined;
  const rows = Array.isArray(v) ? v : [];
  const title = props.title ?? props.source_name;
  return (
    <Card test="board" title={title ? <Bi value={title} /> : undefined} extra={{ "data-board": el?.type }}>
      {typeof v === "number" ? <p className="big-line">{v}</p> : null}
      {rows.length ? (
        <ul className="board-rows">
          {rows.slice(0, 12).map((r: any, i) => (
            <li key={r?.id ?? i}>{text(r?.text ?? r?.title ?? r?.label ?? r?.name ?? "", ctx.lang)}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{props.url ? <a href={props.url}>{props.url}</a> : k("nothing_yet", ctx.lang)}</p>
      )}
    </Card>
  );
}

export function Checklist({ props }: CatalogProps) {
  const [done, setDone] = useState<Set<number>>(new Set());
  return (
    <Card test="checklist" title={props.title ? <Bi value={props.title} /> : undefined}>
      <ul className="checklist">
        {(props.items as string[]).map((item, i) => (
          <li key={item}>
            <label>
              <input type="checkbox" checked={done.has(i)} onChange={() => setDone((d) => { const n = new Set(d); n.has(i) ? n.delete(i) : n.add(i); return n; })} /> {item}
            </label>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Chat author: "Village" for village/system posts, else the member's name from their record (never the raw id). */
export function authorName(author: string, data: Record<string, unknown>): string {
  if (!author || author === "village" || author === "system") return "Village";
  return memberName(author, data);
}

/** First sentence; past 140 characters, cut at a word boundary and add "…". Never mid-word. */
export function oneLine(t: string): string {
  const first = (t.split(/(?<=[.!?])\s/)[0] ?? t).trim();
  return clip(first, 140);
}

/** The first whole sentence(s): a proposal post is never cut mid-sentence (the reasons live on the card). */
export function sentences(t: string, n = 1): string {
  const parts = t.split(/(?<=[.!?])\s+/);
  return parts.slice(0, n).join(" ").trim();
}

export function clip(t: string, max = 140): string {
  if (t.length <= max) return t;
  const cut = t.slice(0, max + 1);
  const sp = cut.lastIndexOf(" ");
  return `${(sp > max * 0.5 ? cut.slice(0, sp) : t.slice(0, max)).replace(/[\s,;:·-]+$/, "")}…`;
}

export interface ChatRow {
  id: string; kind: string; author: string; text: string; text_i18n?: Record<string, string>;
  refs?: { kind: string; id: string; label?: string }[]; source?: { kind: string; ref?: string }; source_label?: unknown; at?: string; mention?: string | null;
  reply_to?: string | null; answer?: string; ask_status?: string; demo?: boolean;
  /** optimistic local row (not yet confirmed by Core) */
  pending?: boolean;
}

/** Ids never reach a phone (D18/D22): rule ids, ledger ids, trace ids. A chip label that carries one falls back to plain words. */
const ID_RE = /\b([RP]-[A-Z0-9]+(-[A-Z0-9]+)*|(ev|dc|inc|ver|prop|rel|tr|m)_[a-z0-9_]+)\b|[A-Za-z][:_][A-Za-z0-9]/;
const REF_WORDS: Record<string, string> = {
  event: "what happened", decision: "Village's reasoning", fact: "what Village knows", rule: "the family's rule", member: "their choice",
  incident: "why", verification: "the check", release: "receipt", proposal: "the proposal", trace: "details"
};
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function chipLabel(ref: { kind: string; id?: string; label?: string }, todayMMDD?: string): string {
  const l = (ref.label ?? "").trim();
  if (l && !ID_RE.test(l)) return l;
  // ledger ids carry their date: ev_1009_1921_money → "her call · Oct 9" / "today's call"
  const m = /^ev_(\d{2})(\d{2})_\d{4}_([a-z_]+)/.exec(ref.id ?? "");
  if (ref.kind === "event" && m) {
    const callish = /money|call|ver|pattern|incident|ask/.test(m[3]);
    if (todayMMDD && `${m[1]}${m[2]}` === todayMMDD) return callish ? "today's call" : "today";
    const when = `${MON[Number(m[1]) - 1] ?? ""} ${Number(m[2])}`.trim();
    return callish ? `her call · ${when}` : `what happened · ${when}`;
  }
  return REF_WORDS[ref.kind] ?? "source";
}

function isDemoRef(r: { kind: string; id: string; label?: string }): boolean {
  return /^demo$/i.test(r.label ?? "") || r.id === "demo";
}
/** Demo-actor posts ("[demo] …" or a demo flag in refs) carry a small "demo" tag. */
export function demoOf(m: ChatRow): { demo: boolean; text: string } {
  const t = m.text_i18n?.en ?? m.text;
  const tagged = /^\s*\[demo\]\s*/i.test(m.text) || !!m.demo || (m.refs ?? []).some(isDemoRef);
  return { demo: tagged, text: t };
}
const stripDemo = (t: string) => t.replace(/^\s*\[demo\]\s*/i, "");

interface AskRef { kind: string; id: string; member?: string; label?: string; answered?: string | null; answer?: string; status?: string }
/** Each asked member's answer: the ref's own answer/status, else Village's later reply naming them ("X's still on", "covers"). */
export function askChips(m: ChatRow, rows: ChatRow[], data: Record<string, unknown>): { member: string; text: string; answer: "yes" | "no" | null }[] {
  const refs = (m.refs ?? []).filter((r) => r.kind === "ask" && (r as AskRef).member) as AskRef[];
  const later = rows.filter((r) => r.author === "village" && r.at && m.at && Date.parse(r.at) > Date.parse(m.at));
  return refs.map((r) => {
    const name = memberName(r.member!, data);
    const own = (r.answered ?? r.answer ?? r.status ?? "").toLowerCase();
    let ans: "yes" | "no" | null = own === "yes" ? "yes" : own === "no" ? "no" : null;
    if (!ans) {
      for (const x of later) {
        const names = (x.refs ?? []).some((y) => y.kind === "member" && y.id === r.member);
        if (names && /covers|still on|can do/i.test(x.text)) { ans = "yes"; break; }
        if (new RegExp(`${name}[^.]*can'?t|can'?t[^.]*${name}`, "i").test(x.text)) { ans = "no"; break; }
      }
    }
    return { member: r.member!, answer: ans, text: ans ? `${name}: ${ans === "yes" ? "can do" : "can't"}` : `asked ${name}` };
  });
}
/** Nudges that only repeat a parent message's ask refs are not shown as their own bubbles. */
export function coveredNudge(m: ChatRow, rows: ChatRow[]): boolean {
  if (m.kind !== "nudge") return false;
  const who = m.refs?.find((r) => r.kind === "member")?.id;
  if (!who || !m.at) return false;
  return rows.some((p) => p !== m && p.at && Date.parse(p.at) <= Date.parse(m.at!) + 60_000 && Date.parse(p.at) >= Date.parse(m.at!) - 120_000 && (p.refs ?? []).some((r) => r.kind === "ask" && (r as AskRef).member === who));
}

/** D39: a Village nudge addressed to a member (refs {kind: member}) is an ask with Yes · Can't on that member's phone. */
export function askOf(m: ChatRow): { addressee: string; askId: string } | null {
  if (m.kind !== "nudge" || (m.author !== "village" && m.author !== "system")) return null;
  const who = m.refs?.find((r) => r.kind === "member")?.id;
  if (!who) return null;
  const askRef = m.refs?.find((r) => /^ask_/.test(r.id));
  return { addressee: who, askId: askRef?.id ?? m.id };
}

/** The ask's answer: the message's own answer/ask_status, else a later reply from the addressee. */
function askAnswer(m: ChatRow, addressee: string, rows: ChatRow[]): "yes" | "no" | null {
  const own = (m.answer ?? m.ask_status ?? "").toLowerCase();
  if (["yes", "accepted", "can_do", "yes_can"].includes(own)) return "yes";
  if (["no", "declined", "cant", "can't"].includes(own)) return "no";
  const reply = rows.find((r) => r.reply_to === m.id && r.author === addressee);
  if (!reply) return null;
  return /^(no|can'?t|cannot)/i.test(reply.text.trim()) ? "no" : "yes";
}

const UNDO_RE = /\s*Undo within 10 ?s\.?/i;

/** Relayed from a call: a Village post whose source is a phone call and that carries the caller's Spanish words. */
function isRelayed(m: ChatRow): boolean {
  return m.author === "village" && !!m.text_i18n?.es && !!m.source && ["call", "phone_line", "voice"].includes(m.source.kind);
}

function msgTime(iso: string | undefined): string {
  return iso ? fmtTime(iso, "en") : "";
}

function VillageMark() {
  return <span className="village-mark" aria-hidden="true">V</span>;
}

const RAW = /[A-Za-z][:_][A-Za-z0-9]/;
const CALL_KINDS = new Set(["call", "phone_line", "voice"]);
function Chips({ m }: { m: ChatRow }) {
  const ctx = useCtx();
  const names = new Set(Object.entries(ctx.data).filter(([k]) => k.startsWith("member:")).flatMap(([, v]) => { const n = (v as { name?: string } | null)?.name; return n ? [n, n.split(" ")[0]] : []; }));
  // D39: no evidence chips that are just a name; no demo flags as chips (they get their own tag)
  const refs = (m.refs ?? []).filter((r) => !(m.kind === "proposal" && r.kind === "proposal") && r.kind !== "member" && r.kind !== "ask" && !names.has((r.label ?? "").trim()) && !isDemoRef(r));
  const today = new Intl.DateTimeFormat("en-US", { month: "2-digit", day: "2-digit", timeZone: "America/New_York" }).format(new Date(ctx.nowMs())).replace("/", "");
  const seen = new Set<string>();
  const chips = refs.map((r) => ({ r, label: chipLabel(r, today) })).filter(({ label }) => (seen.has(label) ? false : (seen.add(label), true)));
  const srcLabel = m.source_label ? text(m.source_label, ctx.lang) : m.author === "village" && m.source && CALL_KINDS.has(m.source.kind) ? "from her check-in call" : "";
  if (!chips.length && !srcLabel) return null;
  return (
    <span className="chat-chips" data-test="chat-chips">
      {srcLabel && !RAW.test(srcLabel) ? <span className="chat-chip" data-test="chat-chip" data-ref-kind="source">{srcLabel}</span> : null}
      {chips.filter(({ label }) => label !== srcLabel).slice(0, 4).map(({ r, label }, i) => (
        <span key={`${r.kind}-${i}`} className="chat-chip" data-test="chat-chip" data-ref-kind={r.kind}>{label}</span>
      ))}
    </span>
  );
}

/** One chat row, rendered by kind (D16): member · Village (sage, third person, source chips) · relayed (amber, Spanish + English)
 *  · proposal (title + one sentence + Approve · Not now for leaders) · receipt · nudge · answer (citation chips in words). */
/** D39 · KIT-MEMBERS-6: only the member whose role decides (the spec's coordinator) gets Approve / Not now. */
export function canDecide(ctx: { role: string; memberId: string | null }, prop?: { coordinator_id?: string; approver?: string } | null): boolean {
  const id = prop?.approver ?? prop?.coordinator_id;
  return id ? id === ctx.memberId : ctx.role === "coordinator";
}

/** who decides, by id: the proposal's own approver / coordinator, else the member row whose role is coordinator */
export function deciderId(data: Record<string, unknown>, prop?: { coordinator_id?: string; approver?: string; decided_by?: string } | null): string | null {
  const own = prop?.decided_by ?? prop?.approver ?? prop?.coordinator_id;
  if (own) return own;
  for (const [key, v] of Object.entries(data)) {
    const r = v as { role?: string; member_id?: string } | null;
    if (key.startsWith("member:") && r?.role === "coordinator") return r.member_id ?? key.slice(7);
  }
  return null;
}

/** the status line a non-deciding member sees under a proposal post: "Ana is deciding" → "Approved by Ana · built → live" */
export function proposalStatusLine(pid: string, rows: ChatRow[], data: Record<string, unknown>, prop?: { status?: string; coordinator_id?: string; approver?: string; decided_by?: string } | null): string {
  const who = deciderId(data, prop);
  const name = who ? memberName(who, data) : "";
  const live = prop?.status === "applied" || rows.some((r) => r.kind === "receipt" && (r.refs ?? []).some((x) => x.kind === "proposal" && x.id === pid));
  if (live) return `Approved${name ? ` by ${name}` : ""} · built → live`;
  if (prop?.status === "rejected") return `Not now${name ? ` · ${name}` : ""}`;
  if (prop?.status === "verifying" || prop?.status === "approved") return `Approved${name ? ` by ${name}` : ""} · building`;
  return name ? `${name} is deciding` : "Waiting for a yes";
}

export function ChatMessage({ m, elementId, allowApprove, compact = false, rows = [] }: { m: ChatRow; elementId: string; allowApprove: boolean; compact?: boolean; rows?: ChatRow[] }) {
  const ctx = useCtx();
  const [localAnswer, setLocalAnswer] = useState<"yes" | "no" | null>(null);
  const ask = askOf(m);
  const demo = demoOf(m).demo;
  // a receipt's "Undo within 10 s" expires to "Kept." (re-render once at the deadline)
  const undoAge = m.at ? ctx.nowMs() - Date.parse(m.at) : Infinity;
  const hasUndo = m.kind === "receipt" && UNDO_RE.test(m.text_i18n?.[ctx.lang] ?? m.text);
  const [, tick] = useState(0);
  useEffect(() => {
    if (!hasUndo || undoAge >= 10_000) return;
    const t = setTimeout(() => tick((x) => x + 1), 10_000 - undoAge + 50);
    return () => clearTimeout(t);
  }, [hasUndo, undoAge]);
  const pendingData = ctx.data["proposals:pending"];
  const pending = Array.isArray(pendingData) ? new Map((pendingData as { proposal_id: string; status: string; title?: unknown }[]).map((p) => [p.proposal_id, p])) : null;
  const village = m.author === "village" || m.author === "system";
  let body = stripDemo(m.text_i18n?.[ctx.lang] ?? m.text);
  if (hasUndo) body = undoAge >= 60_000 ? body.replace(UNDO_RE, "") : undoAge >= 10_000 ? body.replace(UNDO_RE, " Kept.") : body;
  const relayed = isRelayed(m);
  const kind = relayed ? "relayed" : m.kind;
  const pid = m.kind === "proposal" ? m.refs?.find((r) => r.kind === "proposal")?.id : undefined;
  const prop = pid && pending ? pending.get(pid) : undefined;
  const open = !!pid && (pending === null || prop !== undefined);
  const mine = !!ctx.memberId && m.author === ctx.memberId;
  return (
    <li
      className={`chat-msg chat-${kind}${village ? " chat-village" : " chat-member"}${mine ? " chat-mine" : ""}`}
      data-kind={m.kind} data-render={kind} data-author={m.author} data-test="chat-row" data-pending={m.pending ? "true" : undefined}
    >
      <span className="chat-meta">
        {village ? <VillageMark /> : null}
        <strong data-test="chat-author">{authorName(m.author, ctx.data)}</strong>
        {m.at ? <time className="chat-time">{msgTime(m.at)}</time> : null}
        {m.pending ? <span className="chat-time"> · sending</span> : null}
        {demo ? <span className="chat-demo" data-test="chat-demo">demo</span> : null}
      </span>
      <span className="chat-bubble">
        {kind === "relayed" ? (
          <>
            <q className="chat-quote" lang="es">{m.text_i18n!.es}</q>
            <span className="chat-en" lang="en">{m.text_i18n!.en ?? m.text}</span>
          </>
        ) : m.kind === "proposal" ? (
          <span className="chat-proposal" data-test="chat-proposal">
            {prop?.title ? <span className="chat-proposal-title"><Bi value={prop.title} /></span> : null}
            <span className="chat-proposal-line">{sentences(body)}</span>
          </span>
        ) : m.kind === "receipt" ? (
          <span className="chat-receipt" data-test="chat-receipt">✓ {body}</span>
        ) : (
          <span className="chat-text">{body}</span>
        )}
        {!compact ? <Chips m={m} /> : null}
        {(m.refs ?? []).some((r) => r.kind === "ask") ? (
          <span className="chat-ask-chips" data-test="ask-chips">
            {askChips(m, rows, ctx.data).map((c) => <span key={c.member} className="chat-chip" data-test="ask-chip" data-answer={c.answer ?? "waiting"}>{c.text}</span>)}
          </span>
        ) : null}
        {ask ? (() => {
          const ans = localAnswer ?? askAnswer(m, ask.addressee, rows);
          const name = memberName(ask.addressee, ctx.data);
          if (ctx.memberId === ask.addressee && !ans && !compact) {
            const answer = (a: "yes" | "no") => { setLocalAnswer(a); ctx.send({ name: "answer_ask", arg: ask.askId, payload: { ask_id: ask.askId, answer: a }, element_id: elementId }); };
            return (
              <span className="row chat-ask" data-test="chat-ask">
                <button type="button" className="btn btn-primary" data-test="ask-yes" disabled={ctx.disabled} onClick={() => answer("yes")}>Yes</button>
                <button type="button" className="btn btn-soft" data-test="ask-no" disabled={ctx.disabled} onClick={() => answer("no")}>Can't</button>
              </span>
            );
          }
          return <span className="chat-ask-status small muted" data-test="ask-status">{ans ? `${ctx.memberId === ask.addressee ? "You" : name}: ${ans === "yes" ? "can do" : "can't"}` : `waiting for ${name}…`}</span>;
        })() : null}
        {pid && !compact && !(allowApprove && open && canDecide(ctx, prop as never)) ? (
          <span className="chat-ask-status small muted" data-test="proposal-status">{proposalStatusLine(pid, rows, ctx.data, prop as never)}</span>
        ) : null}
        {allowApprove && pid && open && !compact && canDecide(ctx, prop as never) ? (
          <span className="row" data-test="chat-proposal-actions">
            <button type="button" className="btn btn-primary" data-test="chat-proposal-approve" disabled={ctx.disabled || prop?.status === "verifying"} onClick={() => ctx.send({ name: "approve_proposal", arg: pid, element_id: elementId })}>{k("approve", ctx.lang)}</button>
            <button type="button" className="btn btn-soft" data-test="chat-proposal-reject" disabled={ctx.disabled} onClick={() => ctx.send({ name: "reject_proposal", arg: pid, element_id: elementId })}>{k("not_now", ctx.lang)}</button>
          </span>
        ) : null}
      </span>
    </li>
  );
}

/** Oldest first by `at` (stable for equal times; rows without a time keep their place at the end). */
export function byTime(rows: ChatRow[]): ChatRow[] {
  return rows.map((r, i) => [r, i] as const).sort(([a, i], [b, j]) => {
    // a message still sending is the newest by definition (device clocks drift)
    const ta = a.pending || !a.at ? Number.POSITIVE_INFINITY : Date.parse(a.at);
    const tb = b.pending || !b.at ? Number.POSITIVE_INFINITY : Date.parse(b.at);
    return ta === tb ? i - j : ta - tb;
  }).map(([r]) => r);
}

/** POST /villages/{id}/messages as the member (contracts/openapi.yaml postMessage). Offline (fake) = local only. */
export async function postChat(api: ApiConfig | undefined, village: string, textValue: string): Promise<ChatRow | null> {
  if (!api || api.fake || !api.token) return null;
  const f = api.fetchImpl ?? fetch;
  const res = await f(`${api.base}/villages/${encodeURIComponent(village)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${api.token}` },
    body: JSON.stringify({ text: textValue, mention: /@village/i.test(textValue) ? "village" : null, client_ts: new Date().toISOString() })
  });
  if (!res.ok) throw new Error(String(res.status));
  const j = (await res.json()) as { message?: ChatRow };
  return j.message ?? null;
}

/** VillageChat (D16): the village group chat. Proposal posts carry inline Approve · Not now (approve_proposal /
 *  reject_proposal, arg = proposal_id) when allow_approve; once proposals:pending is known, only open ones keep the buttons. */
export function VillageChat({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const rows = Array.isArray(ctx.data[props.bind]) ? (ctx.data[props.bind] as ChatRow[]) : [];
  const [local, setLocal] = useState<ChatRow[]>([]);
  const [draft, setDraft] = useState<string>("");
  const [failed, setFailed] = useState(false);
  const mention = props.mention_label ?? "@Village";
  // an outside prefill (Swap my night) lands in the composer once
  const prefill = ctx.chatDraft ?? "";
  const [seenPrefill, setSeenPrefill] = useState("");
  const [sendNow, setSendNow] = useState<string | null>(null);
  if (prefill && prefill !== seenPrefill) {
    setSeenPrefill(prefill);
    if (ctx.chatAutoSend) setSendNow(prefill);
    else setDraft(prefill);
  }
  const serverTexts = new Set(rows.filter((r) => r.author === ctx.memberId).map((r) => r.text));
  const shown = byTime([...rows, ...local.filter((l) => !serverTexts.has(l.text))]).slice(-(props.limit ?? 50));
  useEffect(() => {
    if (sendNow) {
      const t = sendNow;
      setSendNow(null);
      void submit(t);
    }
  }, [sendNow]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async (override?: string) => {
    const t = (override ?? draft).trim();
    if (!t || ctx.disabled) return;
    const row: ChatRow = { id: `local_${Date.now()}`, kind: "chat", author: ctx.memberId ?? "me", text: t, refs: [], at: new Date(ctx.nowMs()).toISOString(), pending: true };
    setLocal((l) => [...l, row]);
    if (override === undefined) setDraft("");
    setFailed(false);
    try {
      const saved = await postChat(ctx.api, ctx.village, t);
      setLocal((l) => l.map((x) => (x.id === row.id ? { ...(saved ?? row), pending: false } : x)));
    } catch {
      setFailed(true);
      setLocal((l) => l.map((x) => (x.id === row.id ? { ...x, pending: false } : x)));
    }
  };
  return (
    <Card test="village-chat" title={props.title ? <Bi value={props.title} /> : undefined} extra={{ "data-full": ctx.chatFull ? "true" : undefined }}>
      <ol className="chat">
        {shown.filter((m) => !coveredNudge(m, shown)).map((m) => <ChatMessage key={m.id} m={m} elementId={id} allowApprove={!!props.allow_approve} rows={shown} />)}
      </ol>
      {shown.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
      {props.composer ? (
        <form className="chat-composer" data-test="chat-composer" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <button type="button" className="chat-mention" data-test="chat-mention" disabled={ctx.disabled} onClick={() => setDraft((d) => (d.toLowerCase().startsWith(mention.toLowerCase()) ? d : `${mention} ${d}`))}>{mention}</button>
          <input className="chat-input" data-test="chat-input" value={draft} disabled={ctx.disabled} onChange={(e) => setDraft(e.target.value)} placeholder={`${mention} why…`} aria-label="Message" />
          <button type="submit" className="btn btn-primary chat-send" data-test="chat-send" disabled={ctx.disabled || !draft.trim()}>Send</button>
        </form>
      ) : null}
      {failed ? <p className="small muted" data-test="chat-failed">Couldn't send. Check the connection and try again.</p> : null}
    </Card>
  );
}

/** Home's chat preview: the last two messages, compact, and a way into the Chat tab. */
export function ChatPreview({ chatId, onOpen }: { chatId: string; onOpen: () => void }) {
  const ctx = useCtx();
  const el = ctx.view.elements[chatId];
  const rows = el && Array.isArray(ctx.data[el.props.bind as string]) ? (ctx.data[el.props.bind as string] as ChatRow[]) : [];
  return (
    <Card test="chat-preview" title={el?.props.title ? <Bi value={el.props.title} /> : "Chat"}>
      <ol className="chat chat-compact">
        {byTime(rows).slice(-2).map((m) => <ChatMessage key={m.id} m={m} elementId={chatId} allowApprove={false} compact rows={rows} />)}
      </ol>
      {rows.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
      <button type="button" className="btn btn-link" data-test="chat-open" onClick={onOpen}>Open chat</button>
    </Card>
  );
}
