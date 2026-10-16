import React from "react";
import { createRoot } from "react-dom/client";
import { Renderer } from "./renderer/Renderer";
import { useLive } from "./live/useLive";
import "./theme/fonts.css";
import "./theme/floor.css";
import "./theme/village.css";

function App() {
  const live = useLive("kit");
  const unknown = new Set<string>();
  const role = live.role;
  document.documentElement.lang = live.view?.lang ?? "en";
  document.documentElement.dir = live.view?.dir ?? "ltr";

  return (
    <div data-test="app" data-role={role} data-rev={live.rev} data-theme={live.view?.theme ?? "family"} data-lang={live.view?.lang ?? "en"} data-dir={live.view?.dir ?? "ltr"}>
      <div data-test="ws-status" data-state={live.status === "open" ? "open" : live.status} data-attempt={live.attempt}>{live.status}</div>
      {live.status !== "open" ? <div data-test="reconnect-strip">{live.lastError ?? "Reconnecting..."}</div> : null}
      {live.view ? <Renderer view={live.view} data={live.data} lang={live.view.lang} role={role} send={live.send} unknown={unknown} /> : <p>Building {role}'s app...</p>}
      {live.prompt ? <PromptOverlay prompt={live.prompt} send={live.send} lang={live.view?.lang ?? "en"} /> : null}
    </div>
  );
}

function PromptOverlay({ prompt, send, lang }: { prompt: any; send: any; lang: string }) {
  const text = (v: any) => (typeof v === "string" ? v : v?.[lang] ?? v?.en ?? "");
  const answer = (value: "yes" | "no") => send("answer_verification", { verification_id: prompt.verification_id, answer: value }, "prompt-overlay");
  return (
    <div data-test="prompt-overlay" data-verification-id={prompt.verification_id} role="dialog" aria-modal="true" className="prompt">
      <p data-test="prompt-banner">Village is calling you · AI assistant</p>
      <h2>{text(prompt.question)}</h2>
      {prompt.detail ? <p>{text(prompt.detail)}</p> : null}
      <button data-test="verify-no" onClick={() => answer("no")}>{text(prompt.options?.find((o: any) => o.id === "no")?.label) || "That wasn't me"}</button>
      <button data-test="verify-yes" onClick={() => answer("yes")}>{text(prompt.options?.find((o: any) => o.id === "yes")?.label) || "Yes, it was me"}</button>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
