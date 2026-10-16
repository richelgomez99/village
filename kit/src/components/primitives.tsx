import { useRef, useState } from "react";
import type { CatalogProps } from "../renderer/catalog";
import { useCtx } from "../renderer/context";
import { k } from "../i18n/strings";
import { Bi, ConfirmSheet, Icon, ReadAloud, memberName } from "./shared";

export function Screen({ props, children }: CatalogProps) {
  const ref = useRef<HTMLElement | null>(null);
  return (
    <main className="screen" data-test="screen" ref={ref}>
      <header className="screen-head">
        <h1 className="screen-title"><Bi value={props.title} /></h1>
        {props.subtitle ? <p className="screen-sub"><Bi value={props.subtitle} /></p> : null}
        <ReadAloud target={ref} />
      </header>
      <div className="screen-body">{children}</div>
    </main>
  );
}

export function Stack({ props, children }: CatalogProps) {
  return (
    <div className={`stack stack-${props.direction ?? "vertical"} gap-${props.gap ?? "m"}`} data-test="stack">
      {props.title ? <h2 className="card-title"><Bi value={props.title} /></h2> : null}
      {children}
    </div>
  );
}

export function Header({ props }: CatalogProps) {
  const level = props.level ?? 2;
  const Tag = (`h${Math.min(3, level + 1)}`) as "h2" | "h3";
  return <Tag className={`header header-${level}`} data-test="header"><Bi value={props.text} /></Tag>;
}

export function Text({ props }: CatalogProps) {
  return (
    <p className={`text text-${props.size ?? "m"} tone-${props.tone ?? "neutral"}`} data-test="text">
      <Bi value={props.text} />
    </p>
  );
}

const CALL_ACTIONS = new Set(["call_member", "call_number"]);

export function BigButton({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const [confirming, setConfirming] = useState(false);
  const tone = props.tone ?? "info";
  const fire = () => {
    setConfirming(false);
    ctx.send({ name: props.action, arg: props.action_arg, element_id: id });
  };
  const onClick = () => {
    if (ctx.disabled) return;
    if (props.confirm) setConfirming(true);
    else fire();
  };
  const label = (
    <>
      <Icon name={props.icon} />
      <span className="bigbutton-label"><Bi value={props.label} /></span>
    </>
  );
  // calls are real tel: links (iOS Safari ignores programmatic dialing); the action still goes to Core for the log
  if (CALL_ACTIONS.has(props.action) && !props.confirm) {
    const tel = ctx.phoneFor?.(props.action_arg ?? "") ?? null;
    if (tel && !ctx.disabled) {
      return (
        <a className={`bigbutton tone-${tone}`} data-test="bigbutton" data-action={props.action} data-tone={tone} href={`tel:${tel}`} onClick={() => ctx.send({ name: props.action, arg: props.action_arg, element_id: id })}>
          {label}
        </a>
      );
    }
    return (
      <button type="button" className={`bigbutton tone-${tone}`} data-test="bigbutton" data-action={props.action} data-tone={tone} data-no-number={tel || ctx.disabled ? undefined : "true"} disabled>
        {label}
        {!tel && !ctx.disabled ? <span className="no-number small" data-test="no-number">{k("no_number", ctx.lang)}</span> : null}
      </button>
    );
  }
  return (
    <>
      <button
        type="button"
        className={`bigbutton tone-${tone}`}
        data-test="bigbutton"
        data-action={props.action}
        data-tone={tone}
        disabled={ctx.disabled}
        onClick={onClick}
      >
        {label}
      </button>
      {confirming ? <ConfirmSheet text={props.confirm_text ?? props.label} onYes={fire} onNo={() => setConfirming(false)} /> : null}
    </>
  );
}

export function ContactCard({ id, props }: CatalogProps) {
  const ctx = useCtx();
  const bound = props.bind ? (ctx.data[props.bind] as { name?: string; phone?: string } | undefined) : undefined;
  const phone: string | undefined = props.phone ?? bound?.phone ?? (props.member_id ? ctx.phoneFor?.(props.member_id) ?? undefined : undefined);
  const name = props.name ?? bound?.name ?? memberName(props.member_id, ctx.data);
  const onClick = (e: React.MouseEvent) => {
    if (ctx.disabled) {
      e.preventDefault();
      return;
    }
    if (!phone) {
      e.preventDefault();
      return;
    }
    if (props.member_id) ctx.send({ name: "call_member", arg: props.member_id, element_id: id });
  };
  return (
    <a
      className={`contact kind-${props.kind}${props.big ? " big" : ""}`}
      data-test="contact-card"
      data-kind={props.kind}
      href={phone && !ctx.disabled ? `tel:${phone}` : undefined}
      aria-disabled={ctx.disabled || !phone}
      data-no-number={phone ? undefined : "true"}
      onClick={onClick}
    >
      <Icon name={props.kind === "emergency" ? "sos" : "phone"} />
      <span className="contact-name"><Bi value={props.label ?? name} /></span>
      {!phone ? <span className="no-number small" data-test="no-number">{k("no_number", ctx.lang)}</span> : null}
      {phone && props.label !== phone && !String(props.label ?? "").includes(phone) ? <span className="contact-phone">{phone}</span> : null}
    </a>
  );
}

export function StatusGrid({ props }: CatalogProps) {
  const ctx = useCtx();
  return (
    <section className="card" data-test="status-grid">
      {props.title ? <h2 className="card-title"><Bi value={props.title} /></h2> : null}
      <dl className="status-grid">
        {(props.labels as string[]).map((label, i) => {
          const v = ctx.data[props.binds[i]];
          return (
            <div key={label} className="status-cell" data-bind={props.binds[i]}>
              <dt>{label}</dt>
              <dd data-say="">{typeof v === "number" ? v : "—"}</dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
