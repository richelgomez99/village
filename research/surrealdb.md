# SurrealDB research for Village (Agent Memory + Cloud realtime)

Researched 2026-10-15. Sources: surrealdb.com/docs/agent-memory (REST, bulk-import, reconciliation, temporal-validity, state-and-diffs, MCP tools, multi-agent cookbook), surrealdb.com/docs/reference (JS/Python live queries, record access), pricing.json, plus **local tests** (PyPI install on Python 3.13, embedded engines). The labels **[doc]**, **[tested]** and **[inferred]** mark where each claim comes from.

---

## 1. Agent Memory write paths

`POST /api/v1/{ctx}/facts` with `infer` set to one of four modes [doc]:

| infer | What it does | LLM? | Latency |
|---|---|---|---|
| `full` (default) | Extracts entities, attributes and relations from `text`, then reconciles them | yes | [inferred] seconds, from one LLM extraction call. The docs give no number. |
| `triples` | Stores the `triples[]` you send, without extraction, as `source.kind="upsert"` | **no** | [inferred] about 100–500 ms (an HTTP call plus one ACID reconcile transaction) |
| `preview` | Dry run that returns the extraction without saving it | yes | same as full |
| `none` | Stores the literal text as a `memory_chunk` (embedded, no extraction) | no (embedding only) | low |

`/facts/batch` takes `messages[]` and `session_id`, with `extract: whole_conversation|per_message`. It has **no `triples` field**.

**Can we write structured facts directly? YES, through `infer:"triples"`** [doc]:
```json
POST /api/v1/{ctx}/facts
{ "infer":"triples", "scopes":[["village/carmen"]], "observed_at":"2026-10-03T14:05:00Z",
  "triples":[
   {"entity":{"type":"person","name":"Carmen Ruiz"},"key":"lisinopril_dose","value":"10mg daily"},
   {"entity":{"type":"person","name":"Carmen Ruiz"},"key":"takes","target":{"type":"product","name":"Lisinopril"},
    "valid_from":"2026-09-01T00:00:00Z"},
   {"entity":{"type":"person","name":"Carmen Ruiz"},"verb":"took_dose","object":"Lisinopril 10mg 08:02"} ]}
```
- Each entry is one of: an attribute (`key` + `value`), a relation (`key` + `target`), an action (`verb` plus an optional `object`; a dated event), or a bare entity. An ambiguous entry returns 422.
- **`valid_from`/`valid_until` apply to relations only.** An attribute takes its time from the request's **`observed_at`** (known time). A later triple with the same entity and key **supersedes** it. You can set `observed_at` explicitly, so backdating "dose changed 2026-10-03" works.
- **Custom entity types are NOT supported.** The type list is closed: `person, organisation, project, location, topic, product, policy, concept, event, agent, service, other`. Any other type is **silently** stored as `other`, and `agent`/`service` are reserved. Put your own type in the name or key (for example `event` "Shift 2026-10-16 AM", or `concept` "Need: insulin fridge"). Attribute keys and relation labels can be any string.
- **Gap (SDK)** [tested]: Python `surrealdb-memory 1.0.0b1` `remember()` takes `triples` and `labels` but **has no `observed_at` parameter**, and it has no uncertainty-resolve method. Send those two requests over raw HTTP (httpx) with `Authorization: Bearer sp-…`.
- **Gap (provenance)**: triples cannot carry your own `source.ref` or `span` (the docs show no field for them). Their source is `kind:"upsert"` plus the turn id. Workaround: put the provenance in **labels** (`["src=call:CA123","span=412-468","url=dailymed:setid"]`). Labels are stamped on the rows the write creates, and `/query` can filter on them.

## 2. Supersession, history, asOf and uncertainty

**Rule** [doc]: two values conflict when they share a scope, an entity and a key. What happens next depends on `source.kind`:
- **Same `source.kind`** (turn vs turn, upsert vs upsert, document vs document): the new value **supersedes** the old one. The old value gets `valid_until` and `superseded_by`, and the new one gets `valid_from` and `supersedes`. A confidence floor of 0.7 applies only when a confidence score is supplied.
- **Different `source.kind`** (for example a DailyMed *document* says 5mg and a phone *turn* says 10mg): **neither supersedes the other**. Both stay live and an **`uncertainty`** record is created. This is the "authority" rule: curated data is never overwritten by chat.
- The same key in different scopes means two values that coexist. Explicit negation closes the value with `valid_until`.

**Demo consequence**: write all dose changes through the *same* path (triples, so `upsert` vs `upsert`) to get a clean 5mg→10mg chain. Upload the DailyMed label as a *document* to deliberately produce an uncertainty you can resolve on stage.

The `/facts` response includes `extraction.corrections:[{entityId,key,oldValue,newValue}]`, so the write itself tells you that a supersession happened [doc].

```http
GET  /api/v1/{ctx}/entities/person/Carmen%20Ruiz/history/lisinopril_dose   # ordered chain
GET  /api/v1/{ctx}/entities/person/Carmen%20Ruiz/history                   # all keys
GET  /api/v1/{ctx}/entities/person/Carmen%20Ruiz?asOf=2026-10-02T00:00:00Z # also atInstant, validFrom, validUntil
POST /api/v1/{ctx}/query {"query":"Carmen lisinopril dose","asOf":"2026-10-02T00:00:00Z","lens":[["village/carmen"]]}
GET  /api/v1/{ctx}/uncertainty?entity=…&resolved=false
POST /api/v1/{ctx}/uncertainty/{id}/resolve {"acceptedValue":"10mg daily","note":"Dr. Patel call 2026-10-03, CA123@412-468"}
```
Resolving an uncertainty writes the accepted value as a fresh assertion, and the competing records are **superseded** (not forgotten). An uncertainty with no subject returns 422. `asOf` is *known time*: what we believed at a given moment. **Caveat:** a relation whose `valid_until` has passed disappears from recall, and `asOf` does not bring it back. Keep historic facts as attributes so they form a chain.

`GET /state` returns attributes with `validFrom`, `validUntil`, `supersedes`, `supersededBy` and `source:{kind,ref,sessionId}`, plus `unknowns`. `POST /lookup {"subject":"person/Carmen Ruiz"}` returns entities, facts, relations, events and uncertainty in one call, which suits a fact card.

## 3. Provenance

Every record has `source{kind, ref, session_id, turn_at, valid_from, span{start,end}, trust, derived_from}` [doc]. `span` is the character position in the originating turn or passage ("jump to quote").
- **To get real spans, use `infer:"full"` on the transcript.** Ingest each call through `/facts/batch` (with `session_id` set to our conversation id) or `/facts` (with `session_id` and `role`). Extraction then fills in `source.ref` (the turn) and `span`. `GET /sessions/{id}/turns` returns the transcript text, so the UI can highlight `[start,end]`.
- **Documents**: upload the DailyMed or official page with metadata `{"title","source":"https://dailymed…","observedAt"}`. Recall hits of kind `chunk`/`section` include `documentTitle`, and `/chat` citations include `positionPercent`.
- Recall: `POST /query` returns `hits[].source` (a ResultKind: entity/attribute/memory_chunk/chunk/section), `occurredAt`, an inline `trace` and `traceId`. Use `GET /traces/{id}` for the retrieval_trace (candidates, per-signal scores, tier) and `GET /audit?kind=decision` for decision traces (which source produced which belief). MCP `inspect` takes `ref:"trace:<id>"`.
- **Hybrid plan**: on the voice path, ingest the transcript with `full` (for spans) **and** write the operational fact as triples (fast and deterministic), labelled `src=call:<id>`, `span=a-b`. Test tonight whether the turn-derived fact and the upsert fact on the same key create a cross-kind uncertainty. They probably will, so use different keys: `dose_reported` from turns, `lisinopril_dose` from upserts.

## 4. Multi-agent: principals, keys and scopes

Every key is bound to exactly one principal. The chain is key → principal → grants (`memory:read|write|forget`, `scope:create|read|delete`, `grant:manage`) on scope paths [doc]. Principals are created in **Studio** (or through the Cloud API), not over the data-plane REST. Grants go through `POST /principals/{id}/grants` (requires grant:manage). A key can only narrow its principal's access, and `GET /me` introspects the caller. Delegation uses the header `X-Spectron-On-Behalf-Of` (depth 1, intersection of grants).

**Scopes**: register them before first use, or the request fails with "unknown scope node": `POST /scopes {"path":"village/carmen"}`, the CLI command `agent-memory scopes create village/carmen`, or Studio → Scopes. The wire format is DNF: `[["a","b"]]` means a AND b, while `["a","b"]` means a OR b. Grants reach down the tree, never up, and `/*` works only as a trailing subtree marker. **`lens` narrows but never grants**, so isolation needs **separate keys per agent**.

Village pattern (from the cookbook's supervisor-and-workers recipe):
```
village/carmen                      shared family memory (all agents + family)
[["village/carmen","agent/momline"]]  Mom-line private scratch (AND clause)
[["village/carmen","agent/escalation"]]
village/block-14                    blackout block
principal momline:     read+write village/carmen, agent/momline
principal builder:     read village/*, write village/*
principal escalation:  read village/carmen + agent/escalation, write agent/escalation
principal rumorcheck:  read+write village/block-14, agent/rumor
```
`POST /reflect {"query":"What changed for Carmen this week? What is uncertain?","persist":true}` writes lower-trust derived facts (`source.kind=reflect`, with `derived_from`). `POST /consolidate` is caller-scoped. Use `labels:["agent=momline"]` for per-agent attribution in the UI.

## 5. Change notifications

**Agent Memory has no webhooks, streams or live queries.** The REST reference lists none, and "Connectors: not available". The docs' own realtime-UI recipe is to apply **`extraction` (attributes + corrections) from each write response** to the UI. So **Core must be the only writer** (all agents call Core tools, and Core calls Agent Memory). Core then fans the write-response delta out over its realtime channel. A Context maps to a SurrealDB ns/db internally, but nothing documents direct DB access on Cloud. Check in Studio tonight whether you can open that DB and run LIVE SELECT on it, but don't depend on it.

## 6. SurrealDB Cloud plus live queries

- **Free tier**: from pricing.json, one free instance per account, with 1 GB storage, 0.25 vCPU and 1 GB RAM (a search snippet said 512 MB). It **auto-pauses after 7 days idle**. Paid Start/burstable plans begin at $0.021/hr (small). Agent Memory has a **free Sandbox (3M tokens one-off)**, and Lite costs $30/mo.
- **HACKSPRINTNYC50**: no public information. Billing is per organisation (Agent Memory's 429 mentions "organisation credit enforcement"), so the credit is *probably* org credit usable by both products. Either way the free instance costs $0, so the credit only matters for Agent Memory tokens. Verify in Studio → Billing tonight.
- **Browser live queries: YES, directly over `wss://<instance>.surreal.cloud`** [doc]. JS SDK **v2** (`surrealdb@2.1.1`) API. The installed `surrealdb-js` skill shows the stale v1 `db.live(table, cb)`, so don't use it.
```ts
import { Surreal, Table } from "surrealdb";
const db = new Surreal();
await db.connect("wss://<id>.aws-use1.surreal.cloud/rpc");
await db.authenticate(tokenFromCore);          // record-user JWT minted by Core
const live = await db.live(new Table("event")); // managed: auto-restarts on reconnect
live.subscribe((action, rec) => render(action, rec));
// filtered: const [id] = await db.query("LIVE SELECT * FROM event WHERE village = $v",{v}); db.liveOf(id).subscribe(...)
```
- **Auth for phones**: use `DEFINE ACCESS member ON DATABASE TYPE RECORD WITH JWT ALGORITHM HS512 KEY $secret DURATION FOR TOKEN 12h`. Core signs a JWT whose `id` claim is `member:dana`, and add table `PERMISSIONS FOR select WHERE village = $auth.village`. Live notifications respect those permissions. The docs also say a server can `signin` and hand the token to the browser. Note that a session changing principal kills its live queries.
- **Python Core live queries** [doc]: `qid = await db.live("event")` then `async for n in db.subscribe_live(qid)`. This requires ws/wss.
- **Embedded fallback**: [tested] Python `AsyncSurreal("mem://")` works with `pip install --pre 'surrealdb[embedded]'`, **but live queries raise `UnsupportedFeatureError`** ("embedded engine has no notification channel"). [tested] JS `@surrealdb/node` `mem://` `db.live` also failed ("Live subscription failed to listen"). **The local fallback is `surreal start -u root -p root memory`** (`brew install surrealdb/tap/surreal`) over ws://localhost:8000, which supports live queries.
- **Latency** [inferred]: a LIVE SELECT notification is pushed in the same transaction commit, so it arrives in tens of ms on a local server and roughly 50–150 ms plus the RTT to the Cloud region (pick us-east-1 for NYC). That fits comfortably within ~1 s. Measure it tonight.

## 7. MCP server

It is built in at `https://<context-host>/mcp` with `Authorization: Bearer sp-…`, and has 7 tools: **remember** (including `infer:"triples"` + `triples`, and `observed_at`), **recall**, **context**, **reflect**, **forget** (`purge`), **upload** (base64), **inspect** (`entity:<Type>/<Name>`, `trace:<id>`, `document:<id>`). Arguments use snake_case. There is no MCP tool for history or uncertainty, so use REST for those.
Dev time: `claude mcp add --transport http agent-memory https://<host>/mcp --header "Authorization: Bearer sp-…"` (or `agent-memory mcp` prints snippets). Agents could use MCP, but for the demo it's better that agents call Core tools, so that Core can fan out to realtime.

## 8. Install gotchas [tested on py3.13]

- `pip install --pre 'surrealdb[memory]'` (or `uv add --prerelease=allow 'surrealdb[memory]'`) installed surrealdb 3.0.0b10 (pure-Python wheel, Python ≥3.10) and surrealdb-memory 1.0.0b1. Python 3.12 and 3.13 are both fine. Without `--pre` you get 2.0.0, which has no memory extra. Embedded mode needs the separate `[embedded]` extra.
- Import with `from surrealdb.memory import AsyncMemory` (a shim to `surrealdb_memory`). The constructor is `AsyncMemory(context, endpoint=, api_key=)`, with no environment-variable reading. Recall takes the snake_case arguments `as_of`, `lens`, `labels`, `valid_from`.
- npm: `@surrealdb/memory@1.0.0-alpha.11` (fetch-based, no dependencies), and `surrealdb@2.1.1` is the latest DB SDK.
- Field casing: `/query` and `/context` take camelCase (`asOf`, `k`, `lens`), `/facts` takes snake_case (`observed_at`, `session_id`), and MCP uses snake_case. **Unknown fields are silently ignored**, which is the top bug source. `k` has a maximum of 50.
- Embeddings are fixed to gemini-embedding-2 for the deployment. Workbench turns pollute a Context, so use a fresh Context for the demo.

## 9. What will impress Martin Schaer

1. **Dose timeline**: the `/history/lisinopril_dose` chain rendered as 5mg (closed 2026-10-03) → 10mg, each node clickable through to its source (call transcript with the span highlighted, or the DailyMed URL). Add an "as of" slider driving `asOf`.
2. **Uncertainty card**: the DailyMed document says 5mg and Carmen's phone turn says 10mg, which produces an uncertainty. A family member taps "Accept 10mg (Dr. Patel)" in the app, which calls `/resolve` and shows the chain update live on every phone.
3. **Per-agent scopes**: a panel calling `GET /me` for each agent key shows grants. Demo the escalation agent getting a 403 on Mom-line's private scope.
4. **Trace drawer**: `traceId` → `/traces/{id}` showing the tier (direct, hybrid or escalated), per-signal scores and `queryMs`.
5. **Studio Knowledge graph** of the Carmen Context, plus a Cloud instance query view showing LIVE SELECT. That covers both SurrealDB products in a single demo.
6. Use the docs' vocabulary: "supersede, not overwrite", "tri-temporal", "provenance on every fact", "one ACID transaction".

---

## Recommended architecture decision: **B**

Use a **SurrealDB Cloud free instance as the operational store, with LIVE SELECT pushed to browsers and to Core, plus Agent Memory for semantic, temporal and provenance facts.**

Rationale:
- (A) Agent Memory alone fails the realtime requirement. It has no push channel, `/state` is a capped snapshot with no `since`, and the closed type list makes rota and needs data awkward. Polling would be slow and burn tokens.
- (C) works, but SQLite plus SSE shows the judge nothing about SurrealDB. B costs about the same: Core still writes once, and browsers subscribe directly with no SSE code.
- B shows *both* SurrealDB products: the database (live queries, record-level permissions, graph edges) and Agent Memory (supersession, provenance, scopes).
- Write path: a voice tool call reaches Core, which does (1) `CREATE event` in Cloud (live push to phones in <1 s), then (2) asynchronously writes Agent Memory triples labelled with the source, plus a transcript `/facts/batch` at call end (spans). The event row stores `am_turn_id` and `trace_id` for click-through.
- Fallback if the Cloud instance misbehaves: `surreal start memory` on the Mac with the same code (ws://), or worst case SSE from Core.

## Data model sketch

**Cloud DB (ns `village`, db `main`)**
```surql
DEFINE TABLE village SCHEMAFULL;   -- village:carmen, village:block14 {name, kind:'care'|'block'}
DEFINE TABLE member  SCHEMAFULL PERMISSIONS FOR select WHERE village = $auth.village;
  -- member:dana {village, name, phone, role}
DEFINE TABLE event   SCHEMAFULL PERMISSIONS FOR select WHERE village = $auth.village FOR create,update,delete NONE;
DEFINE FIELD village ON event TYPE record<village>;
DEFINE FIELD kind    ON event TYPE string ASSERT $value IN ['dose','checkin','shift','need','offer','alert','rumor'];
DEFINE FIELD payload ON event TYPE object FLEXIBLE;   -- {drug:'Lisinopril',mg:10,taken_at}
DEFINE FIELD actor   ON event TYPE string;            -- 'agent:momline' | 'member:dana'
DEFINE FIELD source  ON event TYPE object FLEXIBLE;   -- {kind:'call',ref:'CA123',span:[412,468]} | {kind:'url',ref:'https://dailymed…'}
DEFINE FIELD am      ON event TYPE option<object> FLEXIBLE; -- {turn_id, trace_id, entity:'person/Carmen Ruiz', key}
DEFINE FIELD at      ON event TYPE datetime DEFAULT time::now();
DEFINE TABLE shift SCHEMAFULL ...;  -- rota: {village, member, start, end, status}
DEFINE TABLE covers TYPE RELATION FROM member TO shift;   -- graph edge for Studio
DEFINE ACCESS member ON DATABASE TYPE RECORD WITH JWT ALGORITHM HS512 KEY '<secret>' DURATION FOR TOKEN 12h;
```
**Agent Memory (one Context `village-demo`)**
- Scopes: `village/carmen`, `village/block-14`, `agent/momline`, `agent/builder`, `agent/escalation`, `agent/rumor`
- Entities: person/Carmen Ruiz, person/Dana Ruiz, product/Lisinopril, organisation/DailyMed, location/Block 14, event/Blackout 2026-10-16, concept/Rumor: "water unsafe"
- Keys: `lisinopril_dose`, `dose_schedule`, `last_dose_taken`, `primary_caregiver`, `status` (rumor: unverified/confirmed/debunked), `power_restoration_eta`
- Relations: Carmen `takes` Lisinopril; Dana `cares_for` Carmen; Rumor `about` Block 14
- Labels: `src=call:<id>`, `span=a-b`, `url=<…>`, `agent=<name>`, `village=<id>`

## Open risks to test tonight

1. Create the Context and the Cloud free instance under one org, and apply HACKSPRINTNYC50: does it credit Agent Memory, Cloud, or both?
2. Do principals and keys per agent work on the Sandbox plan? (Created in Studio; does Sandbox limit the number of keys?)
3. Triples latency (p50) and `full` extraction latency per call transcript. Do triples writes consume tokens?
4. Two triples with the same key from different `observed_at` values: confirm the history chain order and the `corrections` payload.
5. A turn-derived key vs an upsert on the same key: confirm the uncertainty, then `/resolve`, then the history.
6. Does `source.span` appear in `/state` and `history` output for turn-derived attributes? Is turn text retrievable to highlight?
7. Does the SDK lack `observed_at`? Confirm the raw httpx path for `/facts` and `/uncertainty/*/resolve`.
8. Cloud: a browser `wss` LIVE SELECT on iOS Safari with a Core-minted record JWT; measure end-to-end latency; check whether the free instance throttles at 0.25 vCPU.
9. Check whether Studio exposes the Context's underlying SurrealDB (a bonus if LIVE SELECT works on Agent Memory tables).
10. Fallback: `brew install surrealdb/tap/surreal && surreal start memory` with live queries working locally.
