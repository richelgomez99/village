import React from "react";
import { createRoot } from "react-dom/client";
import { useLive } from "../live/useLive";
import "../theme/fonts.css";
import "../theme/floor.css";
import "../theme/a.css";

function ControlPage() {
  const live = useLive("control");
  return (
    <main data-test="control" className="control">
      <header>
        <button data-test="village-tab" data-village="v_reyes">Reyes</button>
        <span data-test="phones-counter" data-value="3">3 phones</span>
        <time data-test="demo-clock" data-now={live.now} data-offset="0">{live.now}</time>
        <button data-test="clock-warp">+30 min</button>
      </header>
      <section data-test="blueprint"><h2>What the agent heard</h2><div data-test="blueprint-person" data-member="m_carmen">Carmen · pills, money calls, whose turn</div><div data-test="blueprint-area" data-area="money">Money: verify Marco first</div><div data-test="blueprint-rule">R-MONEY-VERIFY</div></section>
      <section data-test="live-moment"><h2>No mande dinero todavía</h2><p className="caption">Do not send money yet.</p><span data-test="countdown" role="timer">0:35</span></section>
      <section data-test="gate-feed"><div data-test="gate-row" data-rule="R-MONEY-VERIFY" data-decision="verify_with_member">Check with Marco</div></section>
      <section data-test="decisions-log"><div data-test="decision-row">Money request in Marco's name → check with the real Marco.</div></section>
      <section data-test="ask-why"><input data-test="ask-why-input" /><button data-test="ask-why-send">Ask</button><p data-test="ask-why-answer"></p></section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<ControlPage />);
