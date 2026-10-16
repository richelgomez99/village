import { useState } from "react";
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

/** First sentence, at most ~120 characters: a proposal post is a one-liner; the reasons live on the card's "why". */
export function oneLine(t: string): string {
  const first = (t.split(/(?<=[.!?])\s/)[0] ?? t).trim();
  return first.length > 120 ? `${first.slice(0, 117).trimEnd()}…` : first;
}

export interface ChatRow {
  id: string; kind: string; author: string; text: string; text_i18n?: Record<string, string>;
  refs?: { kind: string; id: string; label?: string }[]; source?: { kind: string; ref?: string }; at?: string; mention?: string | null;
  /** optimistic local row (not yet confirmed by Core) */
  pending?: boolean;
}

/** Ids never reach a phone (D18/D22): rule ids, ledger ids, trace ids. A chip label that carries one falls back to plain words. */
const ID_RE = /\b([RP]-[A-Z0-9]+(-[A-Z0-9]+)*|(ev|dc|inc|ver|prop|rel|tr|m)_[a-z0-9_]+)\b/;
const REF_WORDS: Record<string, string> = {
  event: "what happened", decision: "Village's reasoning", fact: "what Village knows", rule: "the family's rule", member: "their choice",
  incident: "why", verification: "the check", release: "receipt", proposal: "the proposal", trace: "details"
};
export function chipLabel(ref: { kind: string; label?: string }): string {
  const l = (ref.label ?? "").trim();
  if (l && !ID_RE.test(l)) return l;
  return REF_WORDS[ref.kind] ?? "source";
}

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

function Chips({ m }: { m: ChatRow }) {
  const refs = (m.refs ?? []).filter((r) => !(m.kind === "proposal" && r.kind === "proposal"));
  if (!refs.length) return null;
  return (
    <span className="chat-chips" data-test="chat-chips">
      {refs.slice(0, 4).map((r, i) => (
        <span key={`${r.kind}-${i}`} className="chat-chip" data-test="chat-chip" data-ref-kind={r.kind}>{chipLabel(r)}</span>
      ))}
    </span>
  );
}

/** One chat row, rendered by kind (D16): member · Village (sage, third person, source chips) · relayed (amber, Spanish + English)
 *  · proposal (title + one sentence + Approve · Not now for leaders) · receipt · nudge · answer (citation chips in words). */
export function ChatMessage({ m, elementId, allowApprove, compact = false }: { m: ChatRow; elementId: string; allowApprove: boolean; compact?: boolean }) {
  const ctx = useCtx();
  const pendingData = ctx.data["proposals:pending"];
  const pending = Array.isArray(pendingData) ? new Map((pendingData as { proposal_id: string; status: string; title?: unknown }[]).map((p) => [p.proposal_id, p])) : null;
  const village = m.author === "village" || m.author === "system";
  const body = m.text_i18n?.[ctx.lang] ?? m.text;
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
            <span className="chat-proposal-line">{oneLine(body)}</span>
          </span>
        ) : m.kind === "receipt" ? (
          <span className="chat-receipt" data-test="chat-receipt">✓ {body}</span>
        ) : (
          <span className="chat-text">{body}</span>
        )}
        {!compact ? <Chips m={m} /> : null}
        {allowApprove && pid && open && !compact ? (
          <span className="row" data-test="chat-proposal-actions">
            <button type="button" className="btn btn-primary" data-test="chat-proposal-approve" disabled={ctx.disabled || prop?.status === "verifying"} onClick={() => ctx.send({ name: "approve_proposal", arg: pid, element_id: elementId })}>{k("approve", ctx.lang)}</button>
            <button type="button" className="btn btn-soft" data-test="chat-proposal-reject" disabled={ctx.disabled} onClick={() => ctx.send({ name: "reject_proposal", arg: pid, element_id: elementId })}>{k("not_now", ctx.lang)}</button>
          </span>
        ) : null}
      </span>
    </li>
  );
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
  if (prefill && prefill !== seenPrefill) {
    setSeenPrefill(prefill);
    setDraft(prefill);
  }
  const serverTexts = new Set(rows.filter((r) => r.author === ctx.memberId).map((r) => r.text));
  const shown = [...rows, ...local.filter((l) => !serverTexts.has(l.text))].slice(-(props.limit ?? 50));
  const submit = async () => {
    const t = draft.trim();
    if (!t || ctx.disabled) return;
    const row: ChatRow = { id: `local_${Date.now()}`, kind: "chat", author: ctx.memberId ?? "me", text: t, refs: [], at: new Date(ctx.nowMs()).toISOString(), pending: true };
    setLocal((l) => [...l, row]);
    setDraft("");
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
        {shown.map((m) => <ChatMessage key={m.id} m={m} elementId={id} allowApprove={!!props.allow_approve} />)}
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
        {rows.slice(-2).map((m) => <ChatMessage key={m.id} m={m} elementId={chatId} allowApprove={false} compact />)}
      </ol>
      {rows.length === 0 ? <p className="muted">{k("nothing_yet", ctx.lang)}</p> : null}
      <button type="button" className="btn btn-link" data-test="chat-open" onClick={onOpen}>Open chat</button>
    </Card>
  );
}
