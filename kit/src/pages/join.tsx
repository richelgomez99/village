import { useState } from "react";
import { createRoot } from "react-dom/client";
import "../theme/fonts.css";
import "../theme/floor.css";

const TOKEN_KEY = "village_member_token";
function storeVillage(v: string) {
  try {
    localStorage.setItem("village_id", v);
  } catch {
    /* the app URL from Core carries it too */
  }
}
function store(v: string) {
  try {
    localStorage.setItem(TOKEN_KEY, v);
  } catch {
    /* private mode: the httpOnly cookie from Core still identifies the member */
  }
}

/** Join + AI-call consent → POST /auth/redeem {invite, first_name, phone?, consent{ai_calls, text_version}} (openapi redeemInvite); token to storage; URL scrubbed. */
export function JoinPage({ search = location.search, hash = location.hash, fetchImpl = fetch, go = (u: string) => location.assign(u) }: {
  search?: string; hash?: string; fetchImpl?: typeof fetch; go?: (u: string) => void;
}) {
  const p = new URLSearchParams(search);
  const fake = p.get("fake");
  const invite = new URLSearchParams(hash.replace(/^#/, "")).get("i") ?? p.get("i") ?? "";
  const as = p.get("as") ?? "";
  const village = p.get("vn") ?? "";
  const care = p.get("care") ?? "the person you care for";
  const [name, setName] = useState(as);
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (typeof history !== "undefined" && invite) history.replaceState(null, "", location.pathname + (fake ? `?fake=${fake}` : ""));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!name.trim() && !fake) || busy) return;
    setBusy(true);
    setError("");
    try {
      if (fake) {
        store(`mt_${fake}_offline_demo`);
        go(`./?fake=${fake}`);
        return;
      }
      const res = await fetchImpl("/auth/redeem", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          invite,
          first_name: name.trim(),
          ...(/^\+[1-9][0-9]{6,14}$/.test(phone.replace(/[\s()-]/g, "")) ? { phone: phone.replace(/[\s()-]/g, "") } : {}),
          consent: { ai_calls: consent, text_version: "join_v1" }
        })
      });
      if (!res.ok) throw new Error(res.status === 409 ? "This invite was already used. Ask your coordinator for a new one." : `Join failed (${res.status})`);
      const data = await res.json();
      if (data.member_token) store(data.member_token);
      if (data.village) storeVillage(data.village);
      go(data.app_url ?? "./");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Join failed");
      setBusy(false);
    }
  };
  return (
    <main data-test="join-form" className="app join">
      <form onSubmit={submit} className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <h1 className="screen-title" data-test="join-role">{as ? `Join as ${as}` : village ? `Join ${village}` : "Join your village"}</h1>
        <label>First name<br /><input data-test="join-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" style={{ minHeight: 48, width: "100%" }} /></label>
        <label>Mobile, e.g. +1 555 555 0101 (optional)<br /><input data-test="join-phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" style={{ minHeight: 48, width: "100%" }} /></label>
        <label style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <input data-test="join-consent" type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ width: 28, height: 28 }} />
          <span>Village may call me with an AI assistant when someone uses my name to ask {care} for money. It always says it's an AI. I can turn this off anytime.</span>
        </label>
        <button className="btn btn-primary btn-xl" data-test="join-submit" disabled={!name.trim() || busy}>Join the family</button>
        {error ? <p data-test="join-error" role="alert" className="chip">{error}</p> : null}
        <p className="small muted">Without the box ticked you still get the app and in-app checks; Village won't phone you.</p>
      </form>
    </main>
  );
}

if (typeof document !== "undefined" && document.getElementById("root")) createRoot(document.getElementById("root")!).render(<JoinPage />);
