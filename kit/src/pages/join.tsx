import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "../theme/fonts.css";
import "../theme/floor.css";

function JoinPage() {
  const fake = new URLSearchParams(location.search).get("fake") ?? "marco";
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name) return;
    try {
      if (fake) {
        localStorage.setItem("member_token", `mt_${fake}`);
        location.href = `./?fake=${fake}`;
        return;
      }
      const response = await fetch("/auth/redeem", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ first_name: name, mobile: phone, ai_calls: consent }) });
      const data = await response.json();
      localStorage.setItem("member_token", data.member_token);
      location.href = "./";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Join failed");
    }
  };
  return (
    <main data-test="join-form" className="join">
      <form onSubmit={submit}>
        <h1 data-test="join-role">You're joining as {fake === "marco" ? "Marco" : "family"}</h1>
        <input data-test="join-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="First name" />
        <input data-test="join-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Mobile" />
        <label><input data-test="join-consent" type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> Village may call me with an AI assistant for urgent family checks.</label>
        <button data-test="join-submit" disabled={!name}>Join the family</button>
        <p data-test="join-error">{error}</p>
      </form>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<JoinPage />);
