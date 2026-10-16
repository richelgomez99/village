import { useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { text } from "../renderer/view";
import { k } from "../i18n/strings";
import { Bi, Card } from "./shared";

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

interface ChatRow { id: string; kind: string; author: string; text: string; text_i18n?: Record<string, string>; refs?: { kind: string; id: string }[] }

/** VillageChat (D16): the village group chat. Proposal posts carry inline Approve · Not now (approve_proposal /
 *  reject_proposal, arg = proposal_id) when allow_approve; once proposals:pending is known, only open ones keep the buttons. */
export function VillageChat({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const rows = Array.isArray(ctx.data[props.bind]) ? (ctx.data[props.bind] as ChatRow[]) : [];
  const pendingData = ctx.data["proposals:pending"];
  const pending = Array.isArray(pendingData) ? new Map((pendingData as { proposal_id: string; status: string }[]).map((p) => [p.proposal_id, p.status])) : null;
  return (
    <Card test="village-chat" title={props.title ? <Bi value={props.title} /> : undefined}>
      <ol className="chat">
        {rows.slice(-(props.limit ?? 50)).map((m) => {
          const pid = m.kind === "proposal" ? m.refs?.find((r) => r.kind === "proposal")?.id : undefined;
          const status = pid && pending ? pending.get(pid) : undefined;
          const open = !!pid && (pending === null || status !== undefined);
          return (
            <li key={m.id} data-kind={m.kind} data-author={m.author}>
              <strong>{m.author === "village" ? "Village" : m.author}</strong> {m.text_i18n?.[ctx.lang] ?? m.text}
              {props.allow_approve && pid && open ? (
                <span className="row" data-test="chat-proposal-actions">
                  <button type="button" className="btn btn-primary" data-test="chat-proposal-approve" disabled={ctx.disabled || status === "verifying"} onClick={() => ctx.send({ name: "approve_proposal", arg: pid, element_id: id })}>{k("approve", ctx.lang)}</button>
                  <button type="button" className="btn btn-soft" data-test="chat-proposal-reject" disabled={ctx.disabled} onClick={() => ctx.send({ name: "reject_proposal", arg: pid, element_id: id })}>{k("not_now", ctx.lang)}</button>
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
