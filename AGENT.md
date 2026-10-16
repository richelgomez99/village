# AGENT.md: what the Village agent is, and how it decides

Short answer: the agent is **not** Daytona, ElevenLabs or any sponsor. It is a program in Core (`core/agent/`): Claude on Bedrock running a tool-use loop we write ourselves, with a deterministic gate between what the model proposes and what happens, three layers of memory, and five roles that share one runtime. Sponsors are its senses, hands and conscience: SurrealDB (memory), ElevenLabs (voice), Daytona + Anchor + Arize (the release gate), Arize (self-observation).

## 1. The loop
```
trigger ──► build context ──► Claude (role prompt + typed tools) ──► tool call = proposal
                 ▲                                                        │
                 │                                             gate.decide() [pure code]
                 │                                                        │ allow / deny / require_approval
           remember + trace ◄── effect (ledger, memory, voice, release) ◄─┘
```
- **Triggers:** a conversation turn (Founder), a ledger event or call turn (Watcher/Verifier), a clock tick (Watcher), an approved proposal (Builder), an `@Village` question (Explainer).
- **Context builder** (working memory): village snapshot from the operational store + facts recalled from Agent Memory for the people involved + the last N decisions + the role's instructions. Bounded; never the whole history.
- **Typed tools** (pydantic in, pydantic out). Tools are either *read* (recall, query_evals, read_decisions) or *propose* (anything with an effect). Propose-tools are intercepted: the gate decides; `require_approval` turns the call into a proposal record for a leader.
- **Remember + trace:** every run writes a decision record (`decision` table: what was considered, what was chosen, why, evidence refs) and is one Arize trace (AGENT → LLM/TOOL spans, gate decisions as GUARDRAIL spans). The decisions log on the Control Room is this table, in plain words.
- **Framework:** none. A hand-written loop (~200 lines) over the Anthropic Messages API (`AnthropicBedrockMantle`, fallback `Anthropic`). Reasons: Claude 5.5 on Bedrock has no Converse/agent framework path; the gate must sit *inside* the loop; tracing is cleanest with the Anthropic instrumentor. Model routing: Sonnet 5.5 for Founder/Watcher/Builder reasoning, Haiku 5.5 for extraction and the Explainer, Sonnet for evals.

## 2. Roles (one runtime, five prompts and tool sets)
| Role | Trigger | Read tools | Propose tools | Output |
|---|---|---|---|---|
| **Founder** | conversation | `recall`, `capabilities.list` | `ask_followup`, `propose_village_draft`, `render_app` | draft village (people, profiles, capabilities per person, rules) |
| **Watcher** | events, call turns, evals, ticks | `recall`, `query_evals`, `read_decisions` | `consider_options` (no effect), `propose_change`, `nudge` | proposals + nudges in the village chat |
| **Verifier** | money request / unknown caller | `recall` (members, consent) | `start_verification`, `await_verification`, `notify`, `refuse_caller` | verification outcome, verbatim say |
| **Builder** | approved proposal | `catalog.read`, `recall` | `render_app`, `patch_app`, `create_component`, `run_release` | a tested, released version |
| **Explainer** | `@Village why…` / Control Room box | `read_decisions`, `read_facts`, `read_traces` | none (read-only) | answer with citations |

The voice line (ElevenLabs) is a *channel*, not a separate brain: its tools call Core, and Core runs the Verifier role for that turn. The pure gate, not the voice model, chooses the sentence.

## 3. Memory (three layers)
1. **Operational store** (SurrealDB Cloud): village, members, consent, ledger (`event`), verifications, dose windows, decisions, messages, views, releases. The gate reads only this. Changes are pushed live to every phone.
2. **Agent Memory** (SurrealDB): experiential facts with provenance labels (`src=call:<id> secs=…`), history (supersede, not overwrite), uncertainty when sources disagree, scopes per village and per role key. Never on the safety path.
3. **Working memory**: assembled per run by the context builder (§1). Discarded after the run; what matters is written back to 1 or 2.

## 4. How it decides what to build (quality levers)
**Capabilities, not components.** The Founder matches each person's *needs* to a catalog of **capabilities**: "a way to meet a need for a person like this". Each capability declares: `applies_when` (need types), `fits` (profile constraints: literacy, tech comfort, memory, mobility, language), `cost_to_person` (what they must do/remember), `risk_class`, and `implements` (components, voice behaviors, printables, rules). Examples: `lid_qr_logging` (phone-only, memory lapses, lives alone → stickers + scan page), `receptionist_line` (money/impersonation risk → screening on the voice line), `is_it_my_turn` (shift worker → HelperAnswer + 3 PM nudge). The Founder scores candidates per person, picks, and records the reason in the decision record. Components are chosen *by* the capability, so "why this screen?" always has an answer.

**Plan → critique → commit.** Before rendering, a critique pass with a different prompt ("For *this* person, what would fail? What did we assume?") revises the plan once. One extra call, large quality gain; shown on the Control Room as "second opinion".

**Options before proposals.** The Watcher's `consider_options` must list 2–3 candidate changes with tradeoffs and choose with reasons. For the second scam attempt: *a check button* (rejected: relies on her remembering under pressure), *a daily check-in call* (helps; doesn't stop the call), *receptionist on her line* (stops the call before it reaches her; chosen). The options and the choice are stored in the decision record and shown on the Rebuild screen. This is where "sharp reasoning" becomes visible.

**Evals close the loop.** Release evals score every build (coverage of needs, no medical advice, translation back-check, accessibility judge); session evals score calls; the scam eval set measures the gate. The Watcher reads these (Arize + local mirror) as triggers and as feedback.

## 5. Custom components (the catalog that grows)
The fixed catalog is the *floor*, not the ceiling. The Builder has a `create_component` tool that writes a new component (TSX) against the **component contract**: typed props (primitives only), the accessibility floor (D8/D17), no network, no direct data writes (only gated actions), i18n strings, tests included. It enters only through the release gate: built + type-checked + tested in **Daytona**, tried by **Anchor** at phone size, scored by **Arize**; then it is **registered in the village's catalog** with provenance (which need, which family, test results, trace id). A component that passes a stricter bar (two villages, zero eval failures, reviewed) is **promoted to the shared catalog** so other villages can reuse it ("PillOrganizer: created for the Reyes family, 16 tests, used by 3 villages"). That is the marketplace, grown from real needs, every entry with its origin and evidence. Tomorrow: the hero's `PillOrganizer` already flows through this path (V3); `create_component` as a Builder tool is V4+ stretch; the shared catalog is roadmap, shown as a catalog view with origin tags.

## 6. What's built tomorrow vs explained
| | Build (V-version) | Explain |
|---|---|---|
| Runtime loop with typed tools + gate interception | V0–V1 (verifier path), V2 (founder), V4 (watcher/builder) | |
| Capabilities catalog (6–8 entries) + per-person scoring in the Founder | V2 | full catalog |
| Plan → critique → commit | V2 (one critique call) | |
| `consider_options` in the Watcher, options shown on Rebuild | V4 | |
| Decision records + Explainer with citations | V2 | |
| `create_component` through the release gate | PillOrganizer path V3; tool V4+ stretch | shared catalog / marketplace |
