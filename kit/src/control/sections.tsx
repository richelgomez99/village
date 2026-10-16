// ROOM-10: the arc pills navigate Ana's view of a village. Build = the intake (what Village asked, what she and others
// answered, coverage, gaps, "Add a detail"). Run = today (the live room, unchanged). Rebuild = suggestions and history
// (GET /villages/{id}/proposals: pending · applied · declined, then the options each proposal weighed, then "Suggest a
// change" in chat). Everything shown comes from the scene or Core; nothing is invented. Village-agnostic (D30).
import { useEffect, useState, type FormEvent } from "react";
import type { ApiConfig } from "./api";
import { apiRequest } from "./api";
import { displayName, type SceneState } from "./scene";

export type Section = "build" | "run" | "rebuild";

function txt(v: any): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  return String(v.en ?? v.es ?? Object.values(v)[0] ?? "");
}

function personName(spec: any, id: string | null | undefined): string {
  if (!id) return "";
  if (id === "control") return "the Control Room";
  const p = (spec?.blueprint?.people ?? []).find((x: any) => x.id === id);
  return p ? displayName(p, spec) : id;
}

function when(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
}

function Box({ test, title, children }: { test: string; title: string; children: React.ReactNode }) {
  return (
    <section className="region nav-box" data-test={test}>
      <h2 className="region-title">{title}</h2>
      {children}
    </section>
  );
}

function SendLine({ test, label, placeholder, onSend, hint }: { test: string; label: string; placeholder: string; onSend: (t: string) => Promise<string>; hint?: string }) {
  const [val, setVal] = useState("");
  const [state, setState] = useState<{ busy: boolean; msg: string; err: boolean }>({ busy: false, msg: "", err: false });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const t = val.trim();
    if (!t || state.busy) return;
    setState({ busy: true, msg: "", err: false });
    try {
      const msg = await onSend(t);
      setVal("");
      setState({ busy: false, msg, err: false });
    } catch (x) {
      setState({ busy: false, msg: `Core said no (${(x as Error).message})`, err: true });
    }
  };
  return (
    <form className="nav-send" data-test={test} onSubmit={submit}>
      <label className="small muted">{label}</label>
      <div className="nav-send-row">
        <input value={val} onChange={(e) => setVal(e.target.value)} placeholder={placeholder} aria-label={label} data-test={`${test}-input`} />
        <button type="submit" className="btn btn-primary" disabled={state.busy || !val.trim()} data-test={`${test}-send`}>{state.busy ? "Sending…" : "Send"}</button>
      </div>
      {hint ? <p className="small muted">{hint}</p> : null}
      {state.msg ? <p className={`small ${state.err ? "warn" : "mint"}`} data-test={`${test}-result`} role="status">{state.msg}</p> : null}
    </form>
  );
}

/* ---------------- Build = the intake ---------------- */

const ORIGIN: Record<string, string> = { follow_up: "from a follow-up answer", data: "from the village's records", answer: "from an answer", member: "from another member" };

export function BuildSection({ scene, onAddDetail, live }: { scene: SceneState; onAddDetail: (text: string) => Promise<any>; live: boolean }) {
  const spec = scene.spec;
  const desc = spec?.blueprint?.description;
  const needs: any[] = spec?.blueprint?.needs ?? scene.blueprint.stages.needs ?? [];
  const fromOthers = needs.filter((n) => n.origin && n.origin !== "description");
  const willBuild = scene.blocks.flatMap((b) => b.willBuild.map((w, i) => ({ ...w, key: `${b.id}_${i}` })));
  return (
    <div className="nav-section" data-test="section-build" data-live={live ? "1" : "0"}>
      <Box test="build-intake" title="Your intake">
        {desc?.text ? (
          <blockquote className="intake-desc" data-test="intake-description">
            “{desc.text}” <span className="muted small">· {personName(spec, desc.speaker) || "you"}</span>
          </blockquote>
        ) : null}
        {scene.coverage ? <p className="intake-meter" data-test="intake-coverage">{scene.coverage.value} of {scene.coverage.of} covered</p> : null}
        {scene.gaps.length ? <p className="small" data-test="intake-gaps">Still missing: {scene.gaps.join(", ")}</p> : null}
        {scene.transcript.length ? (
          <ol className="intake-transcript" data-test="intake-transcript">
            {scene.transcript.map((l) => (
              <li key={l.id} data-who={l.who} data-test="intake-line"><b>{l.who === "village" ? "Village" : personName(spec, spec?.village?.coordinator_id) || "You"}:</b> {l.text}</li>
            ))}
          </ol>
        ) : !desc?.text ? <p className="empty muted">No intake recorded for this village yet.</p> : null}
      </Box>
      {willBuild.length ? (
        <Box test="build-willbuild" title="What your answers built">
          <ul>{willBuild.map((w) => <li key={w.key} data-test="will-build"><b>{w.person}</b> · {w.component}{w.reason ? <span className="muted"> · because {w.reason}</span> : null}</li>)}</ul>
        </Box>
      ) : null}
      {needs.length ? (
        <Box test="build-needs" title="What Village understood">
          <ul>
            {needs.map((n) => (
              <li key={n.id} data-test="intake-need" data-origin={n.origin ?? ""}>
                {txt(n.text)}
                {(n.subject_member_ids ?? []).length ? <span className="muted small"> · {(n.subject_member_ids as string[]).map((m) => personName(spec, m)).join(", ")}</span> : null}
              </li>
            ))}
          </ul>
        </Box>
      ) : null}
      <Box test="build-others" title="Added after your first words">
        {fromOthers.length ? (
          <ul>{fromOthers.map((n) => <li key={n.id} data-test="other-answer">{txt(n.text)} <span className="muted small">· {ORIGIN[n.origin] ?? `from ${n.origin}`}</span></li>)}</ul>
        ) : (
          <p className="empty muted small">Nothing added since the first description.</p>
        )}
      </Box>
      <SendLine
        test="add-detail"
        label="Add a detail"
        placeholder="e.g. Her pharmacy changed to the one on 37th Ave"
        hint={live ? "Goes to the founding conversation that's open now." : "The founding is finished; Core decides whether it can still take a detail."}
        onSend={async (t) => {
          let r: any;
          try {
            r = await onAddDetail(t);
          } catch (x) {
            if ((x as Error).message === "404") throw new Error("404: no founding conversation is open for this village, so the detail wasn't taken");
            throw x;
          }
          const m = r?.meter ? ` · ${r.meter.covered ?? r.meter.value ?? ""}` : "";
          return r?.next_question ? `Village heard it${m}. Next: ${r.next_question}` : "Village heard it.";
        }}
      />
    </div>
  );
}

/* ---------------- Rebuild = suggestions and history ---------------- */

const PENDING = new Set(["proposed", "ready", "verifying", "approved"]);

export function useProposals(api: ApiConfig, village: string, tick: unknown): { rows: any[]; options: Record<string, any>; error: string | null; reload: () => void } {
  const [rows, setRows] = useState<any[]>([]);
  const [options, setOptions] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    if (api.fake) {
      setRows([]);
      return;
    }
    apiRequest(api, "GET", `/villages/${encodeURIComponent(village)}/proposals`).then(
      async (r: any) => {
        if (!live) return;
        const ps: any[] = Array.isArray(r?.proposals) ? r.proposals : [];
        setRows(ps);
        setError(null);
        const got: Record<string, any> = {};
        await Promise.all(ps.map(async (p) => {
          try {
            const d: any = await apiRequest(api, "GET", `/villages/${encodeURIComponent(village)}/proposals/${encodeURIComponent(p.id)}`);
            if (d?.options) got[p.id] = d.options;
          } catch { /* options are optional */ }
        }));
        if (live) setOptions(got);
      },
      (e) => live && setError(String(e?.message ?? e))
    );
    return () => { live = false; };
  }, [api, village, tick, n]);
  return { rows, options, error, reload: () => setN((x) => x + 1) };
}

export function RebuildSection({ spec, rows, options, error, onDecide, onReceipt, onSuggest }: {
  spec: any; rows: any[]; options: Record<string, any>; error: string | null;
  onDecide: (pid: string, action: "approve" | "reject") => Promise<void>;
  onReceipt: (releaseId: string) => void;
  onSuggest: (text: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const pending = rows.filter((p) => PENDING.has(p.status));
  const applied = rows.filter((p) => p.status === "applied");
  const declined = rows.filter((p) => p.status === "rejected" || p.status === "failed");
  const decide = async (pid: string, a: "approve" | "reject") => {
    setBusy(pid);
    try { await onDecide(pid, a); } finally { setBusy(null); }
  };
  const weighed = rows.filter((p) => options[p.id]?.candidates?.length);
  return (
    <div className="nav-section" data-test="section-rebuild">
      {error ? <p className="small warn nav-wide" data-test="proposals-error">Couldn't read proposals from Core ({error}).</p> : null}
      <Box test="rebuild-pending" title="Waiting for your yes">
        {pending.length ? (
          <ul>
            {pending.map((p) => (
              <li key={p.id} data-test="pending-proposal" data-status={p.status}>
                <b>{txt(p.title)}</b>
                {txt(p.rationale) ? <p className="small">{txt(p.rationale)}</p> : null}
                {(p.changes ?? []).length ? <ul className="small">{p.changes.map((c: any, i: number) => <li key={i}>{txt(c?.text ?? c?.label ?? c)}</li>)}</ul> : null}
                {p.status === "proposed" || p.status === "ready" ? (
                  <div className="proposal-actions">
                    <button type="button" className="btn btn-primary" data-test="proposal-approve" disabled={busy === p.id} onClick={() => decide(p.id, "approve")}>Approve</button>
                    <button type="button" className="btn btn-link" data-test="proposal-reject" disabled={busy === p.id} onClick={() => decide(p.id, "reject")}>Not now</button>
                  </div>
                ) : <p className="small muted">Approved{p.approved_by ? ` by ${personName(spec, p.approved_by)}` : ""} · building</p>}
              </li>
            ))}
          </ul>
        ) : <p className="empty muted small">Nothing waiting.</p>}
      </Box>
      <Box test="rebuild-applied" title="Changes made">
        {applied.length ? (
          <ul>
            {applied.map((p) => (
              <li key={p.id} data-test="applied-proposal">
                <b>{txt(p.title)}</b> <span className="muted small">· {when(p.approved_at ?? p.created_at)}{p.approved_by ? ` · approved by ${personName(spec, p.approved_by)}` : ""}{p.target_rev ? ` · rev ${p.target_rev}` : ""}</span>
                {p.release_id ? <> {" "}<button type="button" className="btn btn-link small" data-test="applied-receipt" onClick={() => onReceipt(p.release_id)}>Receipt</button></> : null}
              </li>
            ))}
          </ul>
        ) : <p className="empty muted small">No changes yet.</p>}
      </Box>
      <Box test="rebuild-declined" title="Declined or didn't ship">
        {declined.length ? (
          <ul>{declined.map((p) => <li key={p.id} data-test="declined-proposal"><b>{txt(p.title)}</b> <span className="muted small">· {p.status === "failed" ? "didn't pass the release checks" : `declined${p.rejected_by ? ` by ${personName(spec, p.rejected_by)}` : ""}`}{p.rejected_at ? ` · ${when(p.rejected_at)}` : ""}</span></li>)}</ul>
        ) : <p className="empty muted small">Nothing declined.</p>}
      </Box>
      <Box test="rebuild-weighed" title="What Village weighed">
        {weighed.length ? weighed.map((p) => (
          <div key={p.id} data-test="weighed-proposal">
            <p><b>{txt(p.title)}</b></p>
            <ul>
              {options[p.id].candidates.map((c: any) => (
                <li key={c.key} data-test="weighed-option" data-chosen={c.chosen ? "1" : "0"}>
                  {c.chosen ? "✓ " : ""}<b>{c.name}</b>{c.what_changes ? ` · ${c.what_changes}` : ""}{c.reason ? <span className="muted small"> · {c.reason}</span> : null}
                </li>
              ))}
            </ul>
            {options[p.id].reasons ? <p className="small muted">{options[p.id].reasons}</p> : null}
          </div>
        )) : <p className="empty muted small">No options recorded yet.</p>}
      </Box>
      <SendLine
        test="suggest-change"
        label="Suggest a change"
        placeholder="e.g. Marco can't do Thursdays anymore"
        hint="Posted to the village chat as you. Village drafts a proposal; nothing changes until you approve it."
        onSend={async (t) => {
          await onSuggest(t);
          return "Posted to the chat. A proposal appears above if Village drafts one.";
        }}
      />
    </div>
  );
}
