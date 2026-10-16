# Village: Winning Execution Playbook (Daytona HackSprint #6, NYC, Oct 16 2026)

How the day works: hacking runs 10:00–15:30. **Devpost locks at 15:30.** Judges pick 8 finalists **from the Devpost page alone**, and finalists pitch at 16:00 (3 min talk + 2 min Q&A). Each criterion is worth 25: Impact, Technical, Creativity, Presentation. Partner Best Use prizes are judged across **all** teams. That last point means the Devpost page has to win partner prizes even if you don't make the final 8.

---

## 0. What past Daytona HackSprint winners have in common

These are from the Devpost pages I fetched:

| Project | Prize | What worked on the page |
|---|---|---|
| **ChaosAgent** (SF Nov '25) | 1st + Best Use of Daytona | Tagline is one sentence with an analogy everyone knows ("like Netflix's Chaos Monkey, for agents"). Sandbox isolation is **the point** of the product, not just where it runs. |
| **PolySandbox** (SF Oct '25) | 2nd + Best Use of Daytona | It names the sponsor in the tagline and has a one-line slogan: "one click → any sandbox → consistent results." |
| **Katena** (SF Jul '26, w/ Braintrust) | Best Use of Daytona | **A measured number in the second sentence:** "24 planted exploits: 22 caught (91.7%), 0 false positives." It scopes the claim honestly ("it's a linter, not a proof"). It also tags the observability sponsor (Braintrust) in Built With. |
| **VoiceSRE** (SF Jul '26) | Best Use of ElevenLabs | The tagline describes the whole loop: "phone call → diagnose → patch in sandbox → PR while you stay on the line." The demo link is the first line of the page. |

**What to copy:**
1. Write a tagline with a verb that covers the whole loop.
2. Put a **number** near the top.
3. Make the sandbox load-bearing, not decorative.
4. Name every sponsor in Built With **and** in its own section.
5. Scope your claims honestly. Judges trust "we measured X" more than "revolutionary."

Seibel's rule applies here too: two sentences plus one concrete example, and "80% accurate, 100% understandable."

---

## 1. Devpost first-round optimization (the 60-second scan)

A judge scrolling ~46 projects does four things in order: reads the **title + tagline**, looks at the **thumbnail**, watches the first **15–20 seconds of video**, and skims the **headings**. Optimize each one for that.

- **Thumbnail (gallery image 1, 3:2, 1200×800):** a phone mockup of Mom's role view next to Marco's phone with an "ESCALATION: double dose blocked" banner. Big text: "Software made for one family." No logos collage.
- **Gallery (4–5 images):**
  1. Hero (as above)
  2. Architecture diagram
  3. Per-role screens side by side (Mom / Ana / Marco) to show it's generative and not a template
  4. Arize trace + eval scores
  5. SurrealDB memory timeline showing supersession
- **Video (≤ 2:00, YouTube unlisted).** Captions burned in, because judges watch muted. Second by second:
  - **0:00–0:08 Hook.** Black card: "Mom just took her blood thinner. Then she called to take it again." Cut to Marco's phone ringing.
  - **0:08–0:20 One-liner.** "Village builds software for one group. Describe your family by voice and an agent builds your family's app."
  - **0:20–0:45 Build.** Ana's voice description, then the agent reasoning panel, then the Daytona sandbox building. Speed up 4× and label it "4× speed, real build."
  - **0:45–1:10 Live loop.** Mom calls "I took my blue pill," and three phones update (split screen).
  - **1:10–1:30 Safeguard.** Second call. The gate blocks it, Marco's phone rings, and the dialogue is captioned.
  - **1:30–1:45 Proof.** SurrealDB timeline with provenance, then the Arize trace/eval with the number ("12/12 double-dose scenarios blocked, 0 false escalations").
  - **1:45–1:55 Generality.** Same engine, a blackout block app.
  - **1:55–2:00 End card.** Title, repo URL, sponsor logos.
- **Badges in the README:** a "Built with" shields row (Daytona · Arize · ElevenLabs · Anchor · SurrealDB · Bedrock), plus "Demo video" and "Live demo" badges.

### Devpost field draft (Village)

- **Name:** Village
- **Tagline:** Describe your family by voice; an agent builds your family's own app in a Daytona sandbox. Mom logs pills by phone, and a safety gate stops double doses and calls her son.
- **Summary (2–3 sentences):** Village is generative software for one group. Ana describes her family out loud, and an agent builds and deploys a custom mobile app inside a Daytona sandbox, with a different view for each role. Mom just phones a voice line, every family member's phone updates live, and a hard-coded safety gate blocks a double dose of a high-alert medication and calls her son within seconds.
- **Problem & Impact:** 53M US adults are unpaid family caregivers *(verify the stat before posting)*. Coordination happens over group texts, and the most dangerous moment, an elderly parent unsure whether she already took her anticoagulant, goes unseen. Generic apps fail because every family is different (who's on call, which pills, what language Mom speaks). Village builds the app around the family instead of making the family fit an app. Measured result: [X/Y] seeded double-dose scenarios blocked, [0] false escalations, [N]s from call to sibling's phone ringing.
- **Architecture & components:** voice intake (ElevenLabs) → planner on Bedrock (Claude) emits a typed family spec → builder agent generates role UIs and deploys them to a **Daytona** sandbox from a prebuilt snapshot (signed preview URL behind our proxy) → Mom's phone line (ElevenLabs agent + Twilio) calls tools on a core API → **policy gate (deterministic code, not the model)** validates every proposed action → **SurrealDB** agent memory stores facts with supersession and provenance → SSE pushes to every phone → escalations via ElevenLabs outbound call → **Anchor Browser** fetches DailyMed labels and city outage pages → everything traced in **Arize** with evals plus an experiment comparing prompts.
- **Sponsor tools:** one bullet per sponsor with **what it does in Village + the file path**. Example: "Daytona: each family app runs in its own sandbox built from snapshot `village-kit`. Generated code never touches our core (`builder/daytona.py`)."
- **Built With tags:** daytona, arize, elevenlabs, anchor-browser, surrealdb, aws-bedrock, twilio, python, typescript, react.
- **Try it out:** repo + live QR URL + video.

### README outline
1. Title, tagline, badges, hero GIF (the 3-phone update)
2. **60-second demo** (embedded video link)
3. What it does (3 bullets) + the number
4. Architecture diagram (Mermaid, so it renders on GitHub) + one paragraph per component
5. **Safeguards** (policy gate rules, consent, AI disclosure on calls, no dosing advice, eval results)
6. **Sponsor tools** table: Tool | What it does here | Code path | Screenshot
7. Run it locally (env vars, `uv run`, one command)
8. Evals & results (Arize experiment link, table)
9. Limitations & next steps (honest)
10. Built at Daytona HackSprint NYC, Oct 16 2026, solo

---

## 2. The 3-minute pitch

**The structure, in time order:**
- **0:00–0:20 Hook + one-liner**
- **0:20–0:40 QR scan**, with the agent reasoning panel narrated while phones load
- **0:40–1:25 Live loop**: dose logged, then double dose blocked and Marco's phone rings
- **1:25–1:50 Safeguards slide**
- **1:50–2:20 Proof**: memory timeline + Arize
- **2:20–2:45 Generality**: blackout block
- **2:45–3:00 Close**

**Audience participation:**
- Expect 4–6 judges, and maybe 50–70% scan. **Never depend on them.** Mirror your own "Ana" phone on the projector (macOS iPhone Mirroring, or QuickTime > New Movie Recording > iPhone source over a cable), so the room sees the update even if nobody scans.
- Put a **live "phones connected: N" counter** on the slide. It rewards scanning and proves concurrency.
- The QR is huge (at least 40% of slide height), black on white, with a **short human URL under it** (e.g. `vlg.yourdomain.com/rossi`). That short URL is **your redirector**, so you can repoint it to a backup if the sandbox dies.

**Network:**
- The room is in a basement (JFK27). Assume **cellular is weak**. Test at 10:00, in the pitch room, on venue Wi-Fi and on cellular.
- If venue Wi-Fi blocks `*.proxy.daytona.works` or `trycloudflare.com` (corporate DNS filtering is common), serve the QR through your own domain via a named Cloudflare tunnel.

**While things load, narrate.** Never say "um, it's loading." Read the reasoning panel aloud: "It's deciding Mom gets a two-button view because Ana said her eyesight is bad." The silence becomes evidence of agency.

**Make the safeguards slide land:**
- Use **one sentence + one diagram**: "The agent acts on its own; code draws the lines it can't cross." Show the arrow: LLM → typed proposal → **policy gate** → action.
- Show 3 rules max:
  - High-alert duplicate within the window → block + call a human
  - Mom can't turn off safety by voice
  - Every call discloses AI
- Then **point back at what they just saw**: "That's the gate that just called Marco."

**Rehearsal:**
- Run it 5 full times with a stopwatch. Two of those runs should include a **deliberate failure** (kill Wi-Fi, decline the call) so you practice the fallback line.
- The script is 420 words at ~150 wpm, which leaves ~15 s of slack for loading.

### Spoken script (~420 words)

> **[Slide 1: black, one line]** Last spring my friend's mom took her blood thinner twice in one morning. She just didn't remember the first one. Nobody in the family group chat knew until the bruising started.
>
> **[Slide 2: Village / QR]** This is Village: software made for one group. Ana described her family to our agent by voice: Mom, her brother Marco, three medications, Mom speaks mostly Italian. The agent wrote and deployed the Rossi family's own app in a Daytona sandbox. Scan this. You're now in the Rossi family. *[glance at counter]* Five phones connected.
>
> While that loads, look at the agent's reasoning on the left: it gave Mom a two-button view because Ana said her eyes are bad, and Marco a one-tap "call Mom" because he's the on-call sibling. Nobody designed those screens. They were generated for this family.
>
> **[Dial Mom line on speaker]** Mom doesn't use apps. She calls. *[Mom: "I took my blue pill."]* ... Look at your phones. Eliquis, 9:02, logged by voice. That's every phone in this room, live.
>
> Now the dangerous part. Mom calls back an hour later. *[Mom: "Did I take my blue pill? I'll take it now."]* The agent wants to be helpful, but it doesn't get to decide. **[Marco's phone rings on the podium]** That's Marco. A deterministic safety gate saw a duplicate dose of a high-alert drug, blocked it, told Mom "you already took it at 9:02, I'm calling Marco," and phoned him. *[answer on speaker, 3 seconds]*
>
> **[Slide 3: Safeguards]** Our rule is simple: the agent acts on its own; code draws the lines it can't cross. Every action is a typed proposal checked by policy code. Mom can't switch off safety by voice. Every call says it's an AI. We never give dosing advice; we only report what the log says.
>
> **[Slide 4: Memory + Arize]** Every fact has provenance. Here in SurrealDB: who said it, when, by which channel, and what it superseded when Mom corrected herself. And in Arize, every call is traced and evaluated. We ran twelve double-dose scenarios: twelve blocked, zero false alarms on Marco.
>
> **[Slide 5: blackout]** And it isn't a pill app. Same engine, different group: a block in Bushwick during a blackout. One description, and the agent built a check-in app for neighbors, with cooling centers pulled live by Anchor Browser from city sites.
>
> **[Slide 6]** Apps are built for millions of users. Families aren't millions of users. Village builds software for the group you already have. Thank you.

Fallback lines (memorize):
- "The call's slow on basement cell, so I'll use the web line, same agent."
- "Here's the same moment recorded at 2pm."

Switch within 5 seconds. Never debug on stage.

---

## 3. Q&A (2 minutes)

- **Answer pattern:** one-sentence answer, then one proof you can point at, then stop. Keep each answer to about 20 s so judges get 3–4 questions in; more questions means more chances to score.
- Repeat or paraphrase the question if the room is loud. It also buys you 2 seconds.
- If you don't know: "I haven't measured that. My guess is X, and here's how I'd test it."

**Prepared answers:**
- *Is the app really generated or a template?* "Generated code on a fixed component kit. The kit keeps it safe, the agent composes it. Here's the diff between two families."
- *What if the LLM is wrong / prompt injection?* "The LLM can't act; it proposes. The gate is 40 lines of code with unit tests."
- *HIPAA/FDA?* "Direct-to-consumer logging and caregiver alerts fall under FDA enforcement discretion. Once we sell to a plan, we sign a BAA. We never give dosing instructions."
- *Mom's autonomy?* "She consents by voice on the first call and can ask what's shared."
- *Business?* "Families pay $X/month; home-care agencies are the B2B path."
- *Why Daytona?* "Untrusted generated code, one sandbox per family, isolation by default."
- *Latency?* "Call to sibling ringing in ~N s, measured in Arize."

---

## 4. Live-demo risk register

| Risk | Mitigation |
|---|---|
| Venue Wi-Fi down / filtered | Phone hotspot (5 GHz, not shared). Test the QR URL on venue Wi-Fi at 10:00 **and** at 15:45. Own-domain redirector to the backup. |
| Basement = no cell for judges or for your calls | Turn on **Wi-Fi Calling** on the Mom and Marco phones. Test inbound and outbound in the pitch room. The app also works on venue Wi-Fi, so tell the room "join the Wi-Fi if your signal is bad" on the slide. |
| Phone call won't connect / Twilio delay | **Pre-dial** at the start of the slide-2 narration, not when you need it. ElevenLabs web-widget fallback is open in a hidden tab, tied to the same agent and tools. Use an upgraded Twilio account (no trial preamble). |
| Marco's phone doesn't ring | Outbound call **plus** a push/SSE banner on Marco's web view. Narrate the banner. Volume to max, Do Not Disturb **off** on that phone only. |
| Sandbox build slow | Demo the **prebuilt** Rossi village and say so honestly: "built at 3:40 by the same pipeline; the Arize trace has the timestamp." Optionally kick off a fresh build at 0:00 and show it finished at 2:30. |
| Daytona warning interstitial | Front it with your proxy that adds `X-Daytona-Skip-Preview-Warning: true` (see `daytona.md`). Otherwise warn on the slide: "tap Continue." |
| ElevenLabs latency | Use a Flash/Turbo voice and a fast LLM. Tool responses under 1.5 s. Turn on `tool_call_sound`. Narrate over gaps. |
| QR fails | Short URL under it, high contrast, no glare. Test from the back row. |
| Judge phones on corporate DNS / VPN | Own domain on Cloudflare, HTTPS only, standard port 443. |
| Laptop sleep | `caffeinate -dimsu &`, power plugged in, Focus mode on (notifications off), close Slack and Messages. |
| Screen mirroring | Bring a USB-C→HDMI adapter. Use **mirror** (not extend) so what you see is what they see. Set 1920×1080 ahead of time. Increase browser zoom to 150%. |
| Total failure | 2-min video ready locally (not streamed), plus a "recorded 2pm" clip of the double-dose moment. |
| State is dirty from rehearsal | `reset_demo.sh` clears today's doses and re-seeds. Run it at T-5. |

### T-15 checklist
1. Hotspot on; laptop on the chosen network; QR URL opens on 2 phones (one Wi-Fi, one cellular)
2. `reset_demo.sh` run; the phone counter reads 0
3. Test call to the Mom line connects; hang up
4. Marco's phone: charged, ringer max, DND off, Wi-Fi Calling on
5. Tabs in order: slides, reasoning panel, SurrealDB timeline, Arize trace, widget fallback, backup video
6. `caffeinate` running; notifications off; display mirrored; zoom checked
7. Water. Stopwatch. Read the opening line once out loud.

---

## 5. Slide deck (6 slides)

1. **"She took it twice."** Black slide, one sentence, no logo.
2. **Village: software made for one group.** QR + short URL + live "phones connected" counter. The reasoning panel sits beside it (or switch to the live app).
3. **Safeguards: the agent acts on its own; code draws the lines it can't cross.** Diagram: LLM → typed proposal → policy gate → action / call human. 3 rules. Small print: AI disclosure, consent, no dosing advice.
4. **Proof.** Left: SurrealDB timeline (supersession arrow, provenance chips). Right: Arize eval table "12/12 blocked · 0 false escalations · call→ring N s".
5. **Same engine, different village.** Screenshot of the blackout block app; Anchor logo next to "live cooling centers."
6. **Advantages + close.** Three bullets (built per group · voice-first for people who don't use apps · safety in code, not prompts), a sponsor logo row, the repo URL.

This covers the required "idea, advantages, safeguards" explicitly. Name the slides with those words so judges can tick the boxes.

---

## 6. Day-of time plan (solo)

| Time | Work |
|---|---|
| 09:30 | Arrive. Test Wi-Fi and cell **in the pitch room**. Get AWS lab creds. |
| 10:00–10:20 | Repo init, README skeleton, Devpost draft saved (Name + tagline). |
| 10:20–12:30 | Core loop: voice → gate → SurrealDB → SSE → phones. Daytona deploy from snapshot. |
| 11:30 | **Sponsor lap 1 (10 min):** tell Daytona, ElevenLabs, SurrealDB, Arize, and Anchor in 1 sentence how you're using them, and ask "what would make this Best Use?" Write the answers down. |
| 12:30–13:30 | Escalation call, Arize evals + experiment, Anchor fetch, blackout variant. |
| 13:00 | **Sponsor lap 2:** show each sponsor a working integration on your phone (30 s each). Ask them to scan the QR. |
| **13:30** | **FEATURE FREEZE.** Bug fixes and demo hardening only after this. Prebuild the Rossi and blackout villages. Write `reset_demo.sh`. |
| 13:45–14:25 | **Record the video.** Use Screen Studio, or `Cmd+Shift+5` / QuickTime, for the screen. Record the phone with iPhone Mirroring, or by filming the phones with a second phone. Record voiceover separately (QuickTime audio) and edit in iMovie or CapCut. Burn in captions. |
| 14:25 | Upload to YouTube unlisted (start the upload *before* writing the page). |
| 14:30–15:05 | Devpost page: paste the drafted fields, gallery images, architecture diagram (export from Mermaid). Finish the README sponsor table. Make the repo public. |
| **15:10** | **Submit.** Then reload logged out and check that the video plays and the links work. |
| 15:10–15:30 | Small Devpost edits only (it locks at 15:30). |
| 15:30 | **Sponsor lap 3:** "submitted, here's the page, here's the exact line where we use you." |
| 15:35–15:55 | Rehearse the pitch 3× with a stopwatch, including one failure drill. Run the T-15 checklist. |
| 16:00 | Pitch. |

**Using Claude Code subagents:**
- Have one subagent draft the README and Devpost copy from the spec at 13:30 while you harden the demo.
- Have another generate the Mermaid diagram and the eval-results table straight from Arize.
- Do not let any agent touch the demo-path code after 15:00.

---

### Sources
- Devpost pages (fetched Oct 15 2026): [ChaosAgent](https://devpost.com/software/chaosagent), [PolySandbox](https://devpost.com/software/polysandbox), [Katena](https://devpost.com/software/katena), [VoiceSRE](https://devpost.com/software/voicesre), [SF Jul '26 gallery](https://daytona-hacksprint-sf-jul-2026.devpost.com/project-gallery), [SF Nov '25 gallery](https://daytona-hacksprint-sf-nov-25.devpost.com/project-gallery)
- [Lessons from Winning Five Hackathons](https://sustained.substack.com/p/lessons-from-winning-five-hackathons) (video-first, sponsor framing, cut early)
- [TRON: Improving your Devpost judge score](https://forum.trondao.org/t/tron-grand-hackathon-improving-your-devpost-judge-score/9393) (video is the first and often only thing judges see)
- [Seibel / YC pitch guide](https://www.saastr.com/the-y-combinator-guide-to-perfectly-pitching-your-seed-stage-startup-with-michael-seibel) (2 sentences + example; 80% accurate, 100% understandable)
- [Reasons your demos will fail at a conference](https://github.com/thebeebs/thebeebsContent/blob/master/reasons-your-demos-will-fail-at-a-conference.md), [Red Gate: avoiding demo fails](https://www.red-gate.com/simple-talk/?p=111618), [Lorna Jane: live demo risks](https://lornajane.net/posts/2017/live-demo-risks-and-rewards)
- [Daytona custom preview proxy](https://daytona.io/docs/en/custom-preview-proxy) (`X-Daytona-Skip-Preview-Warning`)
- Internal: `research/daytona.md`, `research/elevenlabs.md`, `research/safety-business-qa.md`
