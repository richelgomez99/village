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

export function VillageChat({ props }: CatalogProps) {
  const ctx = useCtx();
  const rows = Array.isArray(ctx.data[props.bind]) ? (ctx.data[props.bind] as any[]) : [];
  return (
    <Card test="village-chat" title={props.title ? <Bi value={props.title} /> : undefined}>
      <ol className="chat">
        {rows.slice(-(props.limit ?? 50)).map((m) => (
          <li key={m.id} data-kind={m.kind} data-author={m.author}><strong>{m.author === "village" ? "Village" : m.author}</strong> {m.text}</li>
        ))}
      </ol>
    </Card>
  );
}
