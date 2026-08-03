# AgentCore Runtime — Quick Notes

Notepad-style, terse, for fast review. Full code/detail goes in the numbered category folders.

## 1. Unique identity
- Every deployed Runtime = one ARN (e.g. `arn:aws:bedrock-agentcore:region:account:runtime/name-id`)
- Powered by AgentCore Identity → real workload identity, not just a name
- Enables inbound auth (who can call it) + outbound auth (it calls Slack/GitHub/etc.)
- Misconception: "1 identity, many users" ≠ shared execution. Each user = own session = own microVM
- Mental model: 1 identity (stable) sits above many sessions (constantly created/destroyed)
- **MicroVM is per SESSION, not per ARN.** 1 ARN → many concurrent sessions → each session = 1 microVM
  - 50 users on same agent = 50 sessions = 50 separate microVMs, never shared
- Redeploy = new version, same ARN/identity. DEFAULT endpoint just points to latest version
- See: `07-inbound-outbound-auth/`, `08-versioning-and-endpoints/`

## 2. URI vs ARN
- **URI** = general standard, usually *fetchable* (e.g. ECR image URI — pull bytes from it)
- **ARN** = AWS-only, permanent *name/handle*, not fetchable — used in API calls, IAM policies
- URI answers "where do I get this." ARN answers "what IS this, uniquely, forever"
- URI with a mutable tag can point to different content over time. ARN never changes identity
- Use ECR URI = deployment (where to pull image from)
- Use ARN = invocation, IAM policies, cross-service references

## 3. URL is a subtype of URI
- URI (umbrella) → splits into **URL** (has protocol, fetchable: `https://`) and **URN** (pure name, no fetch)
- Every URL is a URI. Not every URI is a URL
- ECR "image URI" has no `https://` prefix → technically not a full URL, hence "URI" naming
- S3 object link / CloudWatch link (has `https://`) = proper URL
- ARN is philosophically closer to a **URN** (pure name) than a URL

## 4. Serverless, monitoring, pricing
- Serverless = no server provisioning/patching/scaling. **NOT** "no monitoring needed"
- Agentic systems need more observability (multi-step, autonomous failures are easy to miss)
- Runtime ships built-in OpenTelemetry tracing + CloudWatch GenAI Observability by default
- Pricing ≈ Lambda in spirit (usage-based), different in mechanics:
  - CPU: $0.0895/vCPU-hr — **free during idle/I-O wait** (e.g. waiting on LLM response)
  - Memory: $0.00945/GB-hr — **billed continuously while session is alive (Active or Idle)**, NOT free during wait
  - **Key: CPU idle = $0. Memory idle ≠ $0 — keeps costing until session hits Stopped**
- "Memory" here = microVM RAM (like EC2/Lambda memory), NOT the AgentCore Memory service (different product, different pricing)
- Analogy: memory = hotel room (pay per hour reserved, whether used or not). CPU = room service (pay only when ordered)
- Never-invoked ARN = $0 forever (no session exists). Cost starts only on first invoke
- ECR image storage = separate small ongoing cost regardless of invocation (different service)

### Session lifecycle (3 states, confirmed via AWS docs)
- **Active** — processing request/command/background task
- **Idle** — done processing, still available for next call on same session
- **Stopped** — microVM terminated (default: 15 min inactivity, OR 8 hr max lifetime, OR explicit stop)
- Stopped ≠ session dead. Same session ID → reactivates with new microVM + fresh 8hr budget
- Session ID valid until the Runtime ARN itself is deleted
- AgentCore does NOT map sessions to users — that's on your app to manage
- Ephemeral by default (data dies with the microVM) unless "session storage" (persistent mount) configured

### Open item / unconfirmed
- 500 concurrent sessions — likely per-ARN, but scope not confirmed in docs (only video mentioned the number). Verify against AWS quotas page.

## 5. CPU/memory sizing — no fixed size, fully dynamic

- **No instance size to pick.** Unlike Lambda (memory slider) or Fargate (fixed vCPU/memory combo per task), Runtime doesn't ask you to choose anything
- Dynamically detects + meters actual CPU/memory used, moment to moment
- Can scale up/down **within a single session's lifetime** based on what the code is doing right then
- AWS example: financial analysis agent — 0.5 vCPU/2GB while parsing data → spikes to 2 vCPU/8GB for 15 min during heavy computation → drops back down while waiting on batch ops. All one session, zero config
- Worked cost example (60-sec customer support session): 18 sec active CPU (30%) + 42 sec waiting (70%), memory 1.5–2.5GB fluctuating
  - CPU billed: only 18 active sec (~$0.00045)
  - Memory billed: full 60 sec at avg footprint (~$0.00032)
  - Confirms CPU-vs-memory asymmetry from point 4
 - it decided moment to moment which cpu to up or memory up based on workload

### Real AWS architecture diagrams (from AWS's engineering blog, not just the video)
Source: [Securely launch and scale your agents and tools on Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/blogs/machine-learning/securely-launch-and-scale-your-agents-and-tools-on-amazon-bedrock-agentcore-runtime/) — denser/more technical than the video, worth a full read.


- [Session lifecycle states diagram](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2025/08/12/ML-19422-image-1-kosti.png)
- [Two sessions in isolated microVMs, side by side](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2025/08/12/ML-19422-image-2.jpg)
- [Embedded identity flow — Runtime, IdP, AgentCore Identity, AWS services, external APIs](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2025/08/12/ML-19422-image-3.jpg)
- [Runtime ↔ Memory (short/long-term) interaction diagram](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2025/08/12/ML-19422-image-6.jpg)
- [Billing model diagram — which parts of the agent loop get charged](https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2025/08/12/ML-19422-image-7.png)

(Couldn't mirror these locally — sandbox network blocks the CDN domain. Linked directly to AWS instead.)

## 6. Serverless — closing points before moving on

- **Cold starts are real, scoped to new microVMs, not every request.** Happens on first-ever invoke or when a Stopped session reactivates. Active/Idle sessions reuse the warm microVM for subsequent calls — no repeated cold start mid-conversation
- **Serverless hands off infra, not your contract obligations.** AWS owns hosts/scaling/capacity. You still own: implementing `/ping` + `/invocations` correctly (incl. `HealthyBusy` pings for long background tasks, or the platform may think your session died), your execution role/IAM permissions, and session ID generation/user-mapping
- **Not infinite, not everywhere.** Real quotas exist (~500 concurrent sessions), region availability limited (Virginia, Oregon, Sydney per video). Serverless removes capacity planning, not limits
- **Still Preview.** Quotas/defaults/behaviors explicitly called out as adjustable — not final GA numbers

## 7. Framework-agnostic — what's actually confirmed vs assumed

- **Confirmed with real code on AWS's own docs page:** Strands Agents, LangGraph, Google ADK, OpenAI Agents SDK
- **Confirmed only via the GitHub samples repo / blog mention, not the docs page itself:** CrewAI, Autogen, LlamaIndex
- **Semantic Kernel — NOT found anywhere in AWS's own sources** (not docs, not video, not blog). Should work in principle (see mechanism below) but treat as unconfirmed by AWS until tested, not "officially supported"

### The actual mechanism (more useful than memorizing the framework list)
- Every framework example does the exact same 4 things: `import BedrockAgentCoreApp` → `app = BedrockAgentCoreApp()` → decorate entrypoint with `@app.entrypoint` → `app.run()`
- Entrypoint signature always: `def agent_invocation(payload, context)` (sync or async both work)
- No per-framework adapters — the contract sits above any framework, you just call the framework's own normal "run" method inside a plain function
- **This is *why* it's framework-agnostic**, not just a claim

### Other details worth keeping
- `context` object has `.session_id` — AgentCore's own session ID, usable inside your framework code
- Watch for **two separate "session" concepts** when a framework has its own internal session/state (Google ADK's `InMemorySessionService`, LangGraph's checkpointing) vs AgentCore's own session — don't conflate them
- Model choice fully decoupled from framework — confirmed concretely: LangGraph example calls Bedrock-hosted Claude, OpenAI Agents SDK example calls OpenAI's API directly, no special Runtime reconfig either way

## 8. Model-agnostic — auth paths and what to watch for

Source: [Use any foundation model](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-model.html) — 4 providers shown with real code.

- **Two auth paths, not four separate mechanisms:**
  - **Amazon Bedrock** — IAM-based, uses a `boto_session`, no API key. Inherits the Runtime execution role's credentials; role needs `bedrock:InvokeModel`/`InvokeModelWithResponseStream` explicitly granted
  - **OpenAI, Gemini, Fireworks AI** — all API-key-based, not IAM
- **Docs examples hardcode the key inline or via env var — NOT the secure pattern.** Real pattern (from the video): store the key via AgentCore's credential provider system, fetch it with `@requires_api_key(provider_name="...")` from `bedrock_agentcore.identity.auth`. Same outbound-auth mechanism as category 7 — a model API key is just another third-party credential, no different from a Slack/GitHub token
- **Fireworks AI reuses the `OpenAIModel` class** — just swaps `base_url` to `https://api.fireworks.ai/inference/v1`. Means any OpenAI-compatible-API provider (Together AI, Groq, self-hosted vLLM/Ollama) works the same way, zero new code — "any model" is broader than the 4 named examples

### Things to actually watch for
- Bedrock models still carry pre-existing gotchas (from ROADMAP): one-time Anthropic "use case details" form, AWS Marketplace subscription for 3rd-party models on first invoke — not Runtime-specific but still apply
- Non-Bedrock models = real outbound internet calls from inside the microVM. Fine on default public networking; will matter once `13-networking-vpc` is tackled (private Runtime needs explicit egress, e.g. NAT gateway, to reach OpenAI/Gemini/Fireworks at all)

## 9. Session ID ownership & where session data actually lives (production)

- **Correction: Runtime CAN auto-generate a session ID** if `runtimeSessionId` is left empty on first invoke — but don't rely on this. You won't know the ID beforehand, so you can't pre-register the user→session mapping
- **Recommended: your app generates the ID upfront**, ≥33 chars (e.g. `user-{user_id}-conversation-{uuid4()}`), stores the mapping, THEN invokes
- **Where session data lives: microVM RAM/ephemeral filesystem ONLY.** Not a database, not CloudWatch, nowhere durable
- **CloudWatch = observability trail only** (traces/spans/logs of what happened) — NOT a place to restore live session state from
- If the microVM terminates with nothing saved elsewhere, that conversation's working memory is genuinely gone

### Production pattern
- Your app owns a session store (DynamoDB/Redis/etc.): `user_id → {session_id, created_at, last_active}` — 100% your responsibility, AgentCore tracks none of it
- New conversation → generate ID, store mapping, THEN invoke
- Follow-up message → look up existing session ID, reuse, pass again
- Enforce your own policies (max sessions/user, expiry/rotation) — confirmed AgentCore won't do this
- **Reusing session ID after Stopped ≠ automatic state restoration.** Just starts a new microVM under the same ID. Real continuity requires your agent code to explicitly pull prior context from AgentCore Memory (or your own store) at start of the new compute. Persistent filesystem (if configured) only carries files, not full in-memory conversation state

### The actual Runtime vs Memory boundary
Runtime = fast, isolated scratchpad for one conversation's active lifetime.
Memory (or your own store) = anything that needs to survive beyond that scratchpad's life.

## 10. Worked example — one chatbot conversation, start to finish

Scenario: Priya chats with a support bot. Walks through session creation → reuse → termination →
reactivation → the memory boundary, in one story.

1. **Priya opens chat.** Your backend (not Runtime) generates a session ID, saves `priya → session_id` in your own DB. Runtime knows nothing yet.
2. **First message ("return policy?").** Backend calls Runtime with the agent ARN + that session ID. Never-seen-before ID → new microVM spun up (cold start, few sec). Agent answers. MicroVM stays alive, Idle, holding conversation in RAM.
3. **Second message 10 sec later.** Backend looks up the same session ID, sends again. Same microVM, still alive → no cold start, agent genuinely remembers, because it's the same running process/RAM.
4. **Priya goes idle 20 min.** After 15 min inactivity, Runtime kills the microVM — RAM wiped. Billed for memory the entire 15 idle min (CPU was free, memory wasn't).
5. **Priya returns, sends another message.** Backend reuses the same saved session ID (nothing wrong with that) — but Runtime sees it's Stopped → spins up a **brand-new** microVM, fresh cold start, **zero memory of the earlier conversation** (that RAM is gone). Same ID, blank slate.
6. **Fix: AgentCore Memory (or your own DB).** For the agent to say "welcome back, following up on X," your own agent code must explicitly fetch prior history from a durable store at the start of the new microVM and feed it into context. Runtime does NOT do this automatically just because the session ID matches.
7. **CloudWatch, the whole time:** only logging metadata (session started, tool called, duration, errors) — a security camera, not conversation storage. Can't restore a chat from it.
8. **Concurrent user (Raj), same agent:** own separate session ID, own separate microVM, fully invisible to Priya's — even though it's the identical deployed agent (same ARN).

## 11. Precision fix: it's not "15 min of memory," it's "15 min of INACTIVITY"

- Continuous back-and-forth chatting keeps automatic in-RAM memory working for up to **8 hours
  total** (max lifetime) — every message resets the inactivity clock
- The 15-min rule triggers only on a **gap with no activity at all**, not on conversation length
- So: session alive (active use, or idle gaps under 15 min, up to 8 hrs total) → context works
  automatically, free, just sitting in RAM
- Session actually terminates (15-min idle gap OR 8-hr cap OR explicit stop) → automatic memory
  gone. From then on, code must explicitly fetch + re-inject prior history (AgentCore Memory or
  own store) to fake continuity for what looks like "the same session" to the user

## 12. Production choice: rely on session RAM vs always pass explicit history

- **"Free" in-session memory isn't automatic — depends on YOUR code.** Session alive = microVM
  process keeps running. Whether history persists across calls depends on whether your code keeps
  the agent object alive at a scope that survives between invocations (module-level) vs
  recreating it fresh inside the entrypoint every call
- **Pattern A — rely on session RAM:** agent object created once at module scope, reused across
  calls, no explicit history passed. Works only while session is alive, breaks on termination
- **Pattern B — always pass explicit history (more production-robust):** recreate a fresh agent
  object INSIDE the entrypoint every call, seed entirely from passed-in history, run the turn,
  discard the object. Nothing persists except what's explicitly in the payload
- **Don't half-mix the two** — a persistent module-level agent object (Pattern A) PLUS also
  passing full explicit history (Pattern B) = duplication. Turn 1 exists in both the agent's own
  internal memory AND your explicit history → sent to the LLM twice. Wastes tokens, bloats
  context, not catastrophic but sloppy
- **Clean version of "always pass history":** go fully stateless per invocation. Session
  warm/cold becomes irrelevant to correctness — only affects speed (cold start), not memory
  behavior, since nothing depends on ambient state anymore
- **Trade-off:** fetch history from storage (Memory/own DB) on every call = added latency;
  payload/token size grows with conversation length (100MB payload cap rarely the real
  constraint — LLM context window + cost is). Standard fix: truncate/summarize older turns,
  same as any production chat app already does

## 13. A2A protocol — agent-to-AGENT, not agent-to-tool

Source: [Deploy A2A servers in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html), [A2A protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html)

- **MCP** = agent → TOOL. Call a function, get structured data back, done
- **A2A** = agent → another full AGENT. Delegating a task to an independent reasoning entity, not calling a function — more like handing work to a colleague than calling an API

### Real example: travel planning system
1. Flight Search Agent deployed with A2A enabled → auto-gets `/.well-known/agent-card.json` — its "business card": name, skills, endpoint, auth needed
2. Supervisor agent fetches that Agent Card first — the discovery step ("can this agent do what I need, how do I reach it")
3. Supervisor sends a plain message (not a rigid function call): `"Find flights London to NYC, Nov 3rd"` via JSON-RPC `message/send`
4. Runtime routes it through the same session isolation (own microVM) + enterprise auth (SigV4/OAuth) — but the A2A payload itself passes through untouched ("transparent proxy")
5. Flight Search Agent reasons independently inside its own microVM (might call ITS OWN MCP tools internally), returns an "artifact" (the result)
6. Supervisor gets the artifact, continues — could delegate hotel booking to a separate Hotel Agent the same way

### Technical shape (deliberately different plumbing from MCP/HTTP)
| | HTTP | MCP | A2A |
|---|---|---|---|
| Port | 8080 | 8000 | 9000 |
| Path | `/invocations` | `/mcp` | `/` (root) |
| Format | REST JSON/SSE | JSON-RPC | JSON-RPC 2.0 |
| Discovery | N/A | Tool listing | Agent Cards |

- Agent Card = JSON metadata: name, description, skills, `url`, auth requirements — enables automatic discovery in multi-agent systems
- AgentCore = "transparent proxy" — passes JSON-RPC straight through, only adds session isolation + auth on top
- Errors come back as standard JSON-RPC 2.0 errors with HTTP 200 (protocol compliance) — different from typical REST error conventions

## 14. One agent can mix direct MCP tools AND A2A sub-agents together

- **Standard pattern, not an edge case.** Supervisor holds both: direct MCP tools for
  single-step tasks (calculator, weather, DB query) + A2A connections to sub-agents for tasks
  deserving their own full reasoning loop. Matches the original video's 3-layer architecture:
  supervisor → sub-agents → tools/APIs
- **"Agent-as-tool" pattern** — a sub-agent call can be wrapped to LOOK like just another tool in
  the Supervisor's tool list. The Supervisor's LLM sees `search_flights(query)` and doesn't know
  or care if it's a local function, an MCP call, or a full A2A call to another agent

### What's actually different underneath (be deliberate about this)
- **Latency/cost**: MCP tool call = one function execution, fast/cheap. A2A call = kicks off the
  ENTIRE sub-agent's reasoning loop (its own LLM calls, its own tool use) = slower, pricier every
  time. Decide which capabilities deserve full sub-agent status vs staying a plain MCP tool
- **Separate identity/auth**: a sub-agent on its own Runtime = own ARN, own execution role/IAM,
  own inbound auth deciding who can call it. Supervisor needs valid outbound credentials to reach
  it — same outbound-auth mechanism as category 7, just pointed at another agent instead of a
  3rd-party API
- **Session correlation**: sub-agent manages its own sessions independently (separate Runtime
  deployment = separate session lifecycle). Tie sub-agent session ID back to Supervisor's session
  deliberately (e.g. naming convention) or CloudWatch traces end up as two disconnected histories
  for what was really one user interaction

## 15. The broader agent protocol landscape (2026)

Sources: [Survey of agent interoperability protocols (arXiv)](https://arxiv.org/abs/2505.02279), [AG-UI vs MCP vs A2A vs A2UI field guide](https://medium.com/system-design-mastery-series/ag-ui-vs-mcp-vs-a2a-vs-a2ui-a-field-guide-to-the-2026-agent-protocol-stack-07080e346fc9), [Protocols comparison — k21academy](https://k21academy.com/agentic-ai/agentic-ai-protocols-comparison/)

**Stack analogy:** like TCP/HTTP/HTML — each protocol solves a different layer, not competing.

- **MCP** — agent ↔ tool (vertical). Already know this
- **A2A** — agent ↔ agent (horizontal), controlled/intra-org workflows. Just covered
- **AG-UI** — agent ↔ user interface, structured events/messages to a frontend. 4th protocol
  AgentCore Runtime supports, still to cover
- **A2UI** — newer, complementary to AG-UI: agent generates/draws the UI itself, not just events
- **ACP (IBM)** — RESTful HTTP, MIME multipart, scoped to ONE runtime environment. Less adopted.
  NOT an AgentCore-supported protocol
- **ANP (Agent Network Protocol)** — decentralized, peer-to-peer, agents discover/authenticate
  EACH OTHER across the open internet using DIDs (no central registry). A2A assumes you already
  know who you're talking to; ANP is for finding agents you've never met, across org boundaries.
  NOT an AgentCore-supported protocol

### Governance (real interview-relevant signal)
- Dec 2025: Agentic AI Foundation (AAIF) formed under Linux Foundation, neutral governance for
  BOTH MCP and A2A
- Members include Anthropic, Google, OpenAI, Microsoft, AWS — 190 member orgs by May 2026
- Signals MCP + A2A specifically are becoming industry-standard infra, not vendor-specific bets

### What AgentCore actually supports vs the broader market
**AgentCore Runtime supports 4 protocols total: HTTP (generic REST/WebSocket, the default) +
MCP + A2A + AG-UI.** Of the agent-specific stack, that's MCP, A2A, AG-UI — 3 of the layers.
Deliberately NOT ACP or ANP, and A2UI isn't a separate supported protocol either (too new/still
complementary to AG-UI). Know the difference between "exists in the market" and "AgentCore has
native support for."

## 16. AG-UI protocol — agent ↔ user interface

Sources: [Deploy AG-UI servers in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-agui.html), [AG-UI protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-agui-protocol-contract.html)

- **What it's for**: MCP = agent↔tool, A2A = agent↔agent, **AG-UI = agent↔frontend**.
  Standardizes how an agent streams its work (text, reasoning steps, tool calls, UI state)
  to a live user interface — not a REST response, an ongoing event feed
- **AgentCore role**: same "transparent proxy" pattern as A2A — passes requests straight
  through to your container, adds session isolation + auth (SigV4 or OAuth 2.0) on top
- **Port/path quirk**: runs on port 8080 with `/invocations` — SAME as plain HTTP protocol.
  Runtime tells them apart only via the `--protocol AGUI` flag set at `agentcore configure`
  time, not anything in the request itself
- **Transport**: SSE (`/invocations`, unidirectional stream) or WebSocket (`/ws`,
  bidirectional — needed for user interrupts mid-run)
- **Container requirement AG-UI specifically adds**: must be ARM64 (MCP/A2A docs don't
  call this out as explicitly)
- **Request shape**: `RunAgentInput` JSON — `threadId`, `runId`, `messages[]`, `tools[]`,
  `context[]`, `state{}`, `forwardedProps{}`. `threadId`/`runId` are AG-UI's own concepts,
  separate from AgentCore's own session ID header (`X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`,
  auto-added by the platform) — two different IDs doing two different jobs
- **Response shape**: typed SSE events — `RUN_STARTED` → `TEXT_MESSAGE_START` →
  `TEXT_MESSAGE_CONTENT` (streamed deltas) → `TOOL_CALL_START`/`TOOL_CALL_RESULT` →
  `TEXT_MESSAGE_END` → `RUN_FINISHED`. Lets a frontend render "agent is calling a tool now"
  live, not just a final answer
- **Error handling has a split personality**: errors before your container runs (bad auth,
  throttling) = normal HTTP status codes. Errors DURING a run (agent crashes mid-stream)
  = come back as a `RUN_ERROR` event inside the SSE stream itself, HTTP 200 — because the
  stream already started, can't retroactively change the status code
- **Framework support**: Strands (`ag-ui-strands` package), LangGraph, CrewAI all have
  AG-UI integrations via CopilotKit's docs — confirmed sources, not assumed
- **Real use case**: generative UI — agent doesn't just chat, it can drive a progress bar,
  update a dashboard, render structured tool output in the frontend live

### Full protocol comparison — all 4 AgentCore supports
| | HTTP | MCP | A2A | AG-UI |
|---|---|---|---|---|
| Port | 8080 | 8000 | 9000 | 8080 |
| Path | `/invocations` | `/mcp` | `/` (root) | `/invocations` or `/ws` |
| Format | REST JSON/SSE | JSON-RPC | JSON-RPC 2.0 | Typed SSE events / WebSocket |
| Direction | Client → agent | Agent → tool | Agent → agent | Agent → user interface |
| Discovery | N/A | Tool listing | Agent Cards | N/A |

- AG-UI and plain HTTP are genuinely indistinguishable at the wire level (same port, same
  path) — the ONLY thing separating them is the deployment-time `--protocol` flag. Worth
  remembering as an interview gotcha

## 17. Filesystem configuration — how it's different from "memory" and from a session DB

Sources: [File system configurations for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-filesystem-configurations.html), [Persist session state across stop/resume](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-persistent-filesystems.html)

- **Three DIFFERENT things people lump together as "agent memory" — keep them separate:**
  1. **In-session RAM memory** (point 4/11) — conversation stays in the running process's
     memory, free while active, dies with the microVM, gone after 15-min-inactivity/8-hr cap
  2. **App-owned session DB** (point 9, e.g. DynamoDB) — YOUR app's own mapping of
     `user_id → session_id`, and optionally conversation history text, so you can resume/
     route correctly. Lives OUTSIDE Runtime entirely, you built and pay for it separately
  3. **Filesystem configuration (this point)** — actual POSIX disk mounted INTO the microVM
     at `/mnt/<name>`. Raw files, not semantic/conversational memory. New(er) capability
- **What filesystem config actually solves**: by default every session boots a completely
  clean filesystem — stop the session, everything on disk is gone. No installed packages,
  no downloaded files, no generated code survive a restart. Filesystem config fixes THAT
  specific problem, nothing to do with chat history directly
- **Two categories, pick based on need:**
  | | Managed session storage (Preview) | Bring-your-own (S3 Files / EFS) |
  |---|---|---|
  | Isolation | Per-session only, private | Shared — multiple sessions/agents see same data |
  | VPC required | No | Yes |
  | Persistence | Survives stop/resume, 14-day idle expiry, wiped on version update | Customer-managed, permanent until you delete |
  | Best for | Scratch space, code, installed packages, per-user project state | Shared datasets, shared tool libraries, model weights |
- **Mechanics (managed session storage)**: mount path must be `/mnt/<name>` (single
  subdirectory level, 6-200 chars). Agent writes normally (`ls`, `git`, `npm`, `pip` all just
  work) → async-replicated to durable storage behind the scenes → session stops → flushed on
  graceful shutdown → resume SAME `runtimeSessionId` → new microVM, storage re-mounted,
  agent picks up exactly where it left off (files, `.git` history, `node_modules`, everything)
- **Not full POSIX**: no hard links, no device files/FIFO/sockets, no xattr, no fallocate,
  no cross-session file locking. `chmod`/`stat` work but permissions aren't actually
  enforced — agent is the only "user" inside its own microVM anyway
- **The chatbot-relevant twist**: AWS's own reference example uses this filesystem mount
  to ALSO store conversation history — Strands `FileSessionManager` writes chat history as
  files into `/mnt/workspace/.sessions/`. So filesystem storage CAN double as a session
  store instead of DynamoDB — trade-off: simpler (no separate DB to manage), but tied to
  Runtime's own lifecycle/limits (1 GB/session, 14-day idle wipe) rather than a DB you fully
  control. For a real production chatbot at scale, DynamoDB/Redis session store is still the
  more standard, portable pattern — filesystem storage is better suited to a coding agent's
  actual PROJECT FILES than to a chatbot's message history
- **Bring-your-own (S3 Files/EFS)** needs VPC mode, IAM perms (`ClientMount`/`ClientWrite`
  with `AccessPointArn` condition), security group allowing port 2049 outbound, and mount
  targets in a matching Availability Zone — meaningfully more setup than managed session
  storage, but gives permanent, customer-owned, cross-session-shared storage
- **Limits**: up to 5 filesystem configs per runtime total (max 2 S3 Files + 2 EFS + 1
  managed session storage), each mount 30-sec timeout, all mounts happen in parallel — one
  failing mount fails the WHOLE invocation (HTTP 424)
- **Isolation confirmed**: managed session storage is private per session — "cannot read or
  write data from other sessions of the same agent runtime or sessions of different agent
  runtimes." Docs state this explicitly, not inferred
- **Backing it up to your own storage**: no built-in AWS export/snapshot API for managed
  session storage (it lives in an AWS-owned bucket, `acr-storage-*`, not yours). Only way to
  back it up is from INSIDE the agent's own code — either mount a 2nd filesystem config (BYO
  S3/EFS) alongside it and copy files across, or just call boto3 directly from agent code to
  push files to a bucket you own. AgentCore doesn't do this for you
- **Decision framework — why 3 storage tiers, not redundant:**
  - **RAM** (session-live only) → need conversation context WHILE a session is active. Free,
    fast, gone when the microVM stops
  - **Managed session storage** (survives stop/resume, still private) → need files to
    outlive a stop/resume gap for ONE session only. Good for: one user's coding workspace,
    one job's checkpoints
  - **BYO S3/EFS** (shared, permanent, outside Runtime's own rules) → need data visible to
    MULTIPLE sessions/agents/users, or accessible from outside Runtime entirely (another
    pipeline, dashboard, direct S3 API), or needs to survive independent of AgentCore's own
    14-day-idle/version-update wipe rules
  - **Trigger to reach past managed session storage**: does more than one session/agent/user
    need to read or write this same data, OR does it need to outlive AgentCore's own
    retention rules. Either yes → BYO storage earns its extra VPC/IAM setup

## 18. Invocation & streaming — `InvokeAgentRuntime`

Source: [Invoke an AgentCore Runtime agent](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html)

- **The call**: `agent_core_client.invoke_agent_runtime(agentRuntimeArn=..., runtimeSessionId=...,
  payload=...)` — payload is binary, up to **100 MB max**
- **Permission needed**: `bedrock-agentcore:InvokeAgentRuntime` on the caller's IAM identity
- **Two response shapes, check `contentType` to know which**:
  - `text/event-stream` → streaming SSE, read line by line, strip `"data: "` prefix off each
    chunk, print/accumulate incrementally — same SSE pattern as AG-UI (point 16), general
    mechanism not AG-UI-specific
  - `application/json` → normal single blob, read all chunks then `json.loads()` once
  - Streaming vs non-streaming is a CHOICE your agent code makes (what it returns), not
    something Runtime forces either way
- **Multi-modal**: images go in the SAME payload JSON, base64-encoded, alongside `prompt` —
  no separate endpoint/method needed for text vs image input
- **Session continuity mechanic (ties back to point 9/12)**: same `runtimeSessionId` across
  calls = same conversation context. New UUID = fresh conversation. This is literally the
  lever that decides stateful-continuation vs fresh-start, at the API level
- **OAuth callers can't use the AWS SDK for this call** — must hit the raw HTTPS endpoint
  directly instead (SDK path is SigV4-only). Matches what AG-UI's client example already
  showed (`httpx` + Bearer token, not boto3)
- **Qualifiers**: can target a specific agent version/endpoint on invoke — this is the
  hook into category 8 (versioning & endpoints), not covered in depth yet
- **Errors to actually handle**: `ValidationException` (bad ARN/session/payload format),
  `ResourceNotFoundException` (ARN doesn't exist), `AccessDeniedException` (missing IAM
  perm), `ThrottlingException` (rate limit — needs exponential backoff, AWS's own advice)
- **Sibling operation, NOT the same thing**: `InvokeAgentRuntimeCommand` — runs deterministic
  shell-level ops (tests, git, builds) directly in the same session WITHOUT routing through
  the agent's LLM. AWS's own best-practice: use this for anything that doesn't need
  reasoning, save LLM calls for things that do. Ties directly into the coding-agent +
  filesystem-config example from point 17 (`shell` tool there vs this separate API path)

## 19. Invocation gotchas an actual AgentCore engineer would flag (beyond the basic API)

Sources: [Handle asynchronous and long running agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html), [Execute shell commands in AgentCore Runtime sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-execute-command.html)

### Concurrent invokes on the SAME session — don't do it
- Two `InvokeAgentRuntime` calls hitting the same `runtimeSessionId` at the same time do NOT
  queue or error cleanly — the second one gets back `{"status": "processing", "duplicate":
  true}`. This is undocumented/surprising behavior (confirmed via AWS re:Post, not the
  official devguide) — build your OWN app-layer lock/serialization per session, don't rely
  on Runtime to protect you here

### The `/ping` mechanism — this is how long-running work avoids the 15-min idle kill
- Your agent must expose `/ping` returning `{"status": "Healthy"|"HealthyBusy",
  "time_of_last_update": <unix ts>}`
- `Healthy` = idle, subject to the normal 15-min-inactivity timeout (point 4/11)
- `HealthyBusy` + a RECENT `time_of_last_update` = tells Runtime "still working, don't kill
  me" — this is the actual mechanism behind async/background task support
- **Real gotcha**: don't set `time_of_last_update` to "now" on EVERY ping. If it always
  advances, Runtime sees continuous status change and the idle timeout never fires at all —
  session then just runs until the 8-hr MaxLifetime regardless of whether real work is
  happening. Only update the timestamp when status actually changes
- **Blocking-entrypoint trap**: if `@app.entrypoint` does synchronous blocking work, it can
  starve the `/ping` thread too (single-threaded app) → ping stops responding → Runtime
  thinks the agent is dead → kills a session that was actually still working. Long-running
  work needs to run on a separate thread/async task, not inline in the entrypoint
- **SDK pattern**: `app.add_async_task("name")` when starting background work,
  `app.complete_async_task(task_id)` when done — SDK auto-manages the ping status for you so
  you don't hand-roll the `/ping` handler yourself. Lets agent respond "started working on
  it" immediately, keep processing in a background thread, user checks back later

### `InvokeAgentRuntimeCommand` — the deterministic-ops sibling, worth knowing in depth
- Separate operation, SAME session/container/filesystem as `InvokeAgentRuntime` — not a
  separate resource, just a second way to talk to an already-running session
- **Stateless between commands** — each call spawns a FRESH bash process, no persistent
  shell, no carried-over `cd`/env vars. Chain what you need with `&&` in one command string
  (`cd /workspace && export NODE_ENV=test && npm test`)
- **Non-blocking / concurrent with agent invokes** — you CAN run `InvokeAgentRuntime` (LLM
  reasoning) and `InvokeAgentRuntimeCommand` (shell ops) on the same session at the same
  time, platform handles it — different from the same-session-concurrent-INVOKE problem above
- Response streams 3 event types over HTTP/2: `contentStart` (command began) →
  `contentDelta` (stdout/stderr as produced, real-time) → `contentStop` (`exitCode` +
  `status`: `COMPLETED` or `TIMED_OUT`)
- Non-zero exit code is NOT an API error — always check `exitCode` yourself in `contentStop`
- **Container needs dev tools pre-baked** — microVM has no `git`/`npm`/language runtimes by
  default, must be in your Dockerfile or installed at runtime yourself
- **Limits**: command string 1 byte–64 KB, timeout 1–3600 sec, session ID still needs the
  33-char minimum, throttle at 25 TPS (tighter than general invoke)
- **Security/audit split**: CloudWatch Logs gets the request ID + the COMMAND text (what ran)
  but NOT stdout/stderr (that only streams back to your app, never logged server-side).
  CloudTrail gets caller identity/timestamp/IP but not payload. Correlate both via request ID
  if you need a full audit trail
- **The real production pattern this enables**: `InvokeAgentRuntime` for reasoning (agent
  decides WHAT to do) + `InvokeAgentRuntimeCommand` for deterministic execution (tests, git,
  builds — no LLM tokens wasted on things that don't need reasoning) + filesystem config
  (point 17) for the persistent workspace both operate on. All three together = the complete
  production coding-agent picture AWS's own docs build toward

### Addendum — official invocation quotas (missed in point 18, belongs here)
Source: [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)
- Request timeout: **15 min max** for synchronous requests (not adjustable)
- Streaming chunk size: 10 MB max per chunk (not adjustable)
- Streaming max duration: **60 min max** for a streaming connection (SSE or WebSocket) —
  different from the 8-hr session MaxLifetime, this is a per-CONNECTION cap
- Async job max duration: 8 hrs (matches session MaxLifetime, makes sense — same ceiling)
- WebSocket frame size: 64 KB max per frame
- Throttle: `InvokeAgentRuntime` = 200 TPS per agent per account (adjustable)
- **Discrepancy worth flagging, not papering over**: the dedicated
  [Execute shell commands](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-execute-command.html)
  page states `InvokeAgentRuntimeCommand` throttles at **25 TPS**, but the official quotas
  page lists it at **200 TPS** same as regular invoke. Two AWS pages disagree — treat 25 TPS
  as the more conservative number to design against until confirmed, don't assume either is
  definitely stale
- Hardware ceiling: max 2 vCPU / 8 GB per session (not adjustable) — caps the "dynamic
  sizing" from point 5, it scales UP TO this within a session, not infinitely
- Account-wide: 1,000 agents/account, 5,000 active session workloads/account (2,500 outside
  us-east-1/us-west-2) — relevant when you're designing for scale, not just a single demo

## 20. Versioning & endpoints

Source: [AgentCore Runtime versioning and endpoints](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html), [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)

### Core mechanic
- **Automatic, not optional**: create a Runtime → V1 auto-created. ANY update (container
  image swap, network settings change, protocol config change) → a NEW version auto-created.
  You never manually "cut a version" — every meaningful change just makes one
- **Versions are immutable** once created — a complete, self-contained config snapshot, not
  a diff. This is what makes instant rollback safe: rolling back = just pointing somewhere
  else, not un-doing changes
- **Endpoints = named, addressable pointers to a specific version** — think Lambda aliases,
  almost exactly the same mental model if you know Lambda
- **`DEFAULT` endpoint is special**: auto-created, and it AUTOMATICALLY re-points to the
  latest version on every update — you never touch it, it just tracks HEAD
- **Custom/named endpoints (e.g. `"production"`) do NOT auto-advance** — they stay pinned to
  whatever version you last explicitly set, via `update_agent_runtime_endpoint(...,
  agentRuntimeVersion=...)`. This pinning is the actual safety mechanism for controlled
  rollout — code ships to V2, `DEFAULT` moves to V2 immediately, but `production` endpoint
  keeps serving V1 traffic until YOU explicitly promote it

### Worked scenario (from AWS's own table, this is the exact mental model to remember)
| Change | New version? | Latest | DEFAULT | PROD (named endpoint) |
|---|---|---|---|---|
| Initial create | V1 | V1 | → V1 | (not created yet) |
| Protocol change | V2 | V2 | → V2 (auto) | still V1 |
| Create PROD endpoint at V2 | no | V2 | V2 | → V2 |
| Container image update | V3 | V3 | → V3 (auto) | still V2 |
| Explicitly update PROD to V3 | no | V3 | V3 | → V3 |
| Network settings change | V4 | V4 | → V4 (auto) | still V3 |

- **Reading this table correctly**: DEFAULT is basically "whatever I most recently pushed" —
  fine for dev/testing. PROD only moves when a human (or a CI/CD gate) explicitly says so —
  that's the actual production safety net, not any magic on AWS's side
- **Real pattern this enables**: separate named endpoints for dev/staging/production, each
  pinned to a different version. Rollback from a bad V4 = one API call pointing `production`
  back to V3, no redeploy, no rebuild, no waiting — because V3 still fully exists (immutable)

### Endpoint lifecycle states
`CREATING` → `READY` (normal happy path), or `CREATING` → `CREATE_FAILED` (bad IAM perms,
bad container, etc.). Updating an existing endpoint: `READY` → `UPDATING` → `READY`, or
`UPDATING` → `UPDATE_FAILED` on error. Check state before assuming an endpoint is servable.

### Enumeration & the invoke-time connection
- `ListAgentRuntimeVersions` — see every immutable version that's ever been created
- `ListAgentRuntimeEndpoints` — see every named endpoint and which version it currently points to
- **Ties directly to point 18's `qualifier` parameter** on `InvokeAgentRuntime` — that's
  literally how you choose WHICH endpoint (hence which version) a given invoke call hits.
  `qualifier='DEFAULT'` = latest. `qualifier='production'` = whatever version PROD is pinned to

### Limits (confirmed, official quotas page)
- **1,000 versions per agent** (adjustable via Service Quotas)
- **10 endpoints (aliases) per agent** (adjustable) — plenty for dev/staging/prod/canary,
  wouldn't support hundreds of environments without a quota increase

## 21. Inbound & Outbound Auth — the full mechanic

Source: [Authenticate and authorize with Inbound Auth and Outbound Auth](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html)

This connects and completes three threads already touched loosely: point 1 (workload
identity), point 8 (model-agnostic "secure credential pattern"), point 16 (AG-UI's
SigV4/OAuth options). This is the actual mechanic behind all three.

### Inbound Auth — who's allowed to CALL the agent (2 mechanisms, mutually exclusive)
- **IAM SigV4** — the default. Zero config, works exactly like any other AWS API call
  (caller needs `bedrock-agentcore:InvokeAgentRuntime` IAM permission, nothing more)
- **JWT Bearer Token** — configured at `create_agent_runtime` time via
  `authorizerConfiguration.customJWTAuthorizer`: `discoveryUrl` (OIDC `.well-known` URL,
  validated against token's `iss` claim), `allowedClients` (validates `client_id` claim),
  `allowedAudiences` (validates `aud` claim), `allowedScopes`, required custom claims
- **A runtime supports ONE OR THE OTHER, never both at once.** Need both? Create separate
  VERSIONS (point 20) each configured for a different inbound auth type
- **OAuth error discovery follows RFC 6749/7235** — missing token → 401 + `WWW-Authenticate`
  header pointing to a Protected Resource Metadata (PRM) API for client discovery. Exact
  same pattern already seen in AG-UI (point 16) — this is a consistent design across every
  AgentCore protocol, not AG-UI-specific
- **boto3/AWS SDK CANNOT make OAuth-authenticated invoke calls** — confirmed again here
  ("Since boto3 doesn't support invocation with bearer tokens, you'll need requests
  library"). SigV4 = SDK works fine. JWT/OAuth = raw HTTPS call required. Same fact already
  surfaced in point 18/16, now with the actual AWS wording behind it

### The `X-Amzn-Bedrock-AgentCore-Runtime-User-Id` header — a 3rd, DIFFERENT mechanism
- Not really "inbound auth" — it's a way to tell AgentCore WHICH end-user to fetch OAuth
  credentials for, when you don't have a real JWT to prove who that user is yet (quickstart/
  dev scenarios, or enterprise systems with their own internal user ID strings)
- **Critical distinction**: JWT path (`GetWorkloadAccessTokenForJWT`) cryptographically
  verifies issuer + signature + expiry — real proof of identity. This header path
  (`GetWorkloadAccessTokenForUserId`) does NOT verify the value against anything — it's an
  opaque string, trusted purely because the CALLER supplied it
- Needs its own separate IAM action: `bedrock-agentcore:InvokeAgentRuntimeForUser`
- **AWS's own explicit security guidance** (worth remembering, this is a real interview-
  grade gotcha): restrict this IAM permission tightly (never wildcard/broad managed policy),
  derive the user-id from an ALREADY-authenticated principal rather than trusting client
  input directly, audit-log the IAM-principal↔user-id relationship via CloudTrail, and
  explicitly DENY the action on runtimes that don't need user-delegation at all
- **Production guidance is blunt**: use JWT for production, this header is for dev/
  quickstart or specific enterprise-identity-passthrough cases only

### Workload Identity — the thread from point 1, now with real mechanics
- Auto-created per Runtime by AgentCore Identity when you create the Runtime (already knew
  this from point 1 — now here's how it's actually used)
- Since **Oct 13, 2025**: a Service-Linked Role (`AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`)
  auto-grants the permissions workload identity needs — no manual IAM policy required for
  NEW agents. Agents created BEFORE that date still need manual policy granting
  `GetWorkloadAccessToken` / `GetWorkloadAccessTokenForJWT` / `GetWorkloadAccessTokenForUserId`
  scoped to the `workload-identity-directory` resource — a real "it depends when you created
  it" gotcha to know

### Outbound Auth — the FULL flow behind point 8's "secure credential pattern"
Point 8 described `@requires_api_key` abstractly. Here's the complete mechanic end to end
(worked example: agent reading a user's Google Drive):
1. **Register a Credential Provider** — `create-oauth2-credential-provider` (e.g.
   `GoogleOauth2` vendor + your registered app's client ID/secret) → AWS returns a
   `callbackUrl` you must register in the 3rd-party app's OAuth redirect URI list
2. **Inbound validation happens first** — Runtime validates the caller's JWT per the
   authorizer config already set up
3. **Token exchange**: Runtime swaps that validated inbound token for a **Workload Access
   Token** via `GetWorkloadAccessTokenForJWT`, delivered to your agent code in the payload
   header `WorkloadAccessToken` — this is the credential your agent code actually holds
4. **Tool-call time**: agent code decorated with `@requires_access_token(provider_name=...,
   scopes=[...], auth_flow="USER_FEDERATION")` uses the Workload Access Token to call the
   **Token Vault API** (`GetResourceOauth2Token`), which generates a 3-legged-OAuth (3LO)
   consent URL
5. Agent surfaces that URL to the end user (via the `on_auth_url` callback) — user opens it,
   logs into Google, grants consent — classic OAuth consent screen, nothing unusual here
6. **AgentCore Identity caches the resulting Google access token in the Token Vault**, keyed
   by (workload identity + end-user ID from the inbound JWT) — so the SAME user isn't asked
   for consent again on every future call, only once until the token expires
- **This is the concrete mechanism point 8 only described in outline** — `@requires_api_key`
  (simple API-key providers) and `@requires_access_token` (full 3LO OAuth providers, this
  flow) are the two decorator forms of the same underlying Credential Provider + Token Vault
  system

### Bonus mechanism — propagating the raw JWT into agent code
- Optional: allowlist the `Authorization` header via request-header-allowlist config so your
  OWN agent code can decode/inspect JWT claims directly (e.g. with PyJWT). Skip signature
  verification in your own code — Runtime already validated it before your code ever ran
- Separate/optional from the outbound flow above — this is for when your agent logic itself
  needs to branch on claims (e.g. role-based behavior), not for calling 3rd-party APIs

### Troubleshooting (AWS's own debug checklist, genuinely useful)
- Decode a JWT without a library: base64-decode the middle segment of the token
  (`token.split('.')[1]`), check `iss`/`client_id`/`aud`/`exp` manually against your
  authorizer config
- Most common failures: `iss` claim doesn't match the discovery URL's issuer exactly,
  `client_id`/`aud` not in the allowed lists, or the token simply expired (Cognito default:
  60 minutes)

## 22. Environment variables

Sources: [CreateAgentRuntime API reference](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateAgentRuntime.html), [UpdateAgentRuntime API reference](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateAgentRuntime.html)

- **The mechanism**: `environmentVariables` param on `CreateAgentRuntime`/`UpdateAgentRuntime`
  — plain string→string map, up to **50 entries**, key 1–100 chars, value 0–5000 chars each.
  Standard OS-level env vars once inside the microVM — your agent reads them exactly like
  `os.environ["MY_API_URL"]` in any normal app, nothing AgentCore-specific about the read side
- **Static, not per-invocation** — set once at deploy time, same values for every session and
  every invocation on that version, until you explicitly update them. Contrast with things
  that DO vary per-call: session ID, `WorkloadAccessToken` (point 21) — those arrive via
  payload/headers at invoke time, never via env vars
- **Changing env vars = a config change = a NEW immutable version** (ties directly to point
  20's rule: "any update... creates a new version"). `DEFAULT` endpoint auto-advances to
  pick up the new values immediately; a pinned `production` endpoint keeps running on the
  OLD env var values until you explicitly promote it — same safety mechanism as any other
  config change, nothing special-cased for env vars
- **Not a secrets mechanism — genuinely don't put secrets here.** Values are plaintext,
  visible via `GetAgentRuntime` and in the console. For real secrets (API keys, DB
  passwords), use Secrets Manager or Parameter Store and grant the execution role IAM
  permission to fetch them at runtime — or better, for 3rd-party service credentials
  specifically, use the Credential Provider + Token Vault system from point 21, which is
  the AWS-native pattern built exactly for this. Env vars are for non-sensitive config:
  feature flags, API endpoint URLs, log levels, model IDs
- **Local dev override**: `agentcore dev --env KEY=value` lets you simulate/override env
  vars for local testing without touching the deployed Runtime at all — useful for testing
  config combinations before committing to an actual new version
- **Distinct from Dockerfile `ENV` directives** — a custom container image can bake its own
  env vars via the Dockerfile. Whether Runtime-level `environmentVariables` override
  container-baked ones or the reverse isn't something I found explicitly confirmed in
  AWS's docs — flagging as unconfirmed rather than guessing, worth testing directly if it
  matters for a real deployment
- **Terminology note**: AWS also has a separate, newer resource called "AgentCore harness"
  (a higher-level wrapper that's itself backed by a managed Runtime under the hood) with its
  OWN `create-harness --environment-variables` flag. Functionally analogous but it's a
  DIFFERENT API/resource from `CreateAgentRuntime` — don't conflate the two if you see
  "harness" terminology elsewhere, they're not interchangeable even though the env-var
  mechanic looks nearly identical

## 23. IAM Permissions for AgentCore Runtime

Source: [IAM Permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)

### Three SEPARATE permission layers — don't conflate them
1. **Caller permissions** — who can hit the AgentCore control-plane API (`CreateAgentRuntime`,
   `InvokeAgentRuntime`, etc.). Covered by `BedrockAgentCoreFullAccess` managed policy, or a
   narrower custom one
2. **AgentCore CLI permissions** — broader dev/test-only IAM the CLI itself needs (create IAM
   roles matching `*BedrockAgentCore*`, manage CodeBuild projects, push to ECR, S3 buckets
   prefixed `bedrock-agentcore-*`). **Explicitly flagged by AWS as NOT production-suitable**
   — "designed for development and testing... not suitable for production environments"
3. **Execution role** — the role AgentCore Runtime itself ASSUMES to actually run your agent
   code. This is the one that matters for what your DEPLOYED agent can do at runtime

### When to use which — think "who's the actor," not "which is more permissions"
| Layer | Actor | Answers | When needed |
|---|---|---|---|
| 1. Caller | You/CI-CD/backend app calling the API | "Who can manage/invoke this agent?" | Always — every setup needs this |
| 2. CLI | Your own dev-machine identity | "What can my CLI provision for me?" | Only if using `agentcore` CLI for dev. Deploying via raw boto3/CDK/Terraform/CFN instead? Skip this layer, use THOSE tools' own IAM needs |
| 3. Execution role | The Runtime SERVICE itself (via trust policy) | "What can the agent DO once running?" | Always — unconditional, every deployed Runtime needs one regardless of deploy method |
- Layers 1 & 2 control access TO the agent from outside. Layer 3 controls what the agent can
  reach FROM INSIDE once it's live. Not a hierarchy, three different concerns entirely

### Execution role ≠ Workload Identity — genuinely different systems
- **Execution role** = standard IAM role mechanism, same concept as a Lambda execution role.
  Governs what AWS API calls your running agent CODE can make (CloudWatch, Bedrock, ECR, etc.)
- **Workload Identity** (point 1, point 21) = AgentCore Identity's OWN separate concept, used
  specifically for the outbound-OAuth token exchange flow. Auto-created per Runtime, not an
  IAM role you write
- They intersect at ONE place: the execution role must be GRANTED the IAM actions
  (`GetWorkloadAccessToken*`) that let your agent code actually USE its workload identity to
  fetch tokens. Two different systems, one permission bridge between them

### What the execution role policy actually contains (real buckets, not arbitrary)
- **Observability** (forward-link to category 11, not covered in depth yet): CloudWatch Logs
  (`CreateLogGroup`/`CreateLogStream`/`PutLogEvents`/`Describe*`, scoped to
  `/aws/bedrock-agentcore/runtimes/*`), X-Ray (`PutTraceSegments`/`PutTelemetryRecords`/
  `GetSamplingRules`/`GetSamplingTargets`), CloudWatch custom metrics (`PutMetricData`,
  scoped via a `cloudwatch:namespace = bedrock-agentcore` condition — not resource-scoped,
  condition-scoped)
- **Model invocation** (only needed if using Bedrock models — ties to point 7/8's model-
  agnostic discussion, this policy assumes Bedrock specifically): `bedrock:InvokeModel` +
  `InvokeModelWithResponseStream`, scoped to `foundation-model/*` plus account-specific
  Bedrock resources. If you're calling OpenAI/Gemini/Fireworks instead, this bucket doesn't
  apply — you'd need the Credential Provider permissions from point 21 instead
- **Container image pull** (only for container-based deploys, not direct-code-zip):
  `ecr:BatchGetImage` + `GetDownloadUrlForLayer` + `GetAuthorizationToken`
- **Workload access token retrieval** (the execution-role↔Workload-Identity bridge from
  above): `GetWorkloadAccessToken` / `GetWorkloadAccessTokenForJWT` /
  `GetWorkloadAccessTokenForUserId`, scoped to
  `workload-identity-directory/default/workload-identity/<agentName>-*` — **note the ARN
  bakes in the agent NAME**, meaning you decide the agent's name before creating this role,
  and the scoping is genuinely per-agent, not account-wide
- **Two nearly-identical execution role variants** in AWS's docs: "direct deploy" (code-zip
  method) omits the ECR-pull and workload-token statements that the general "AgentCore
  Runtime execution role" includes — matches the deployment method you're using

### Trust policy — separate from the permissions policy, both required
- The execution role also needs a TRUST policy allowing `bedrock-agentcore.amazonaws.com` to
  assume it (`sts:AssumeRole`) — permissions policy alone isn't enough, standard IAM role
  mechanic, easy to forget when hand-rolling a role
- **Confused-deputy protection built in**: trust policy conditions require
  `aws:SourceAccount` = your account AND `aws:SourceArn` matching
  `arn:aws:bedrock-agentcore:region:account:*` — prevents a DIFFERENT AWS customer's
  AgentCore resources from tricking your role into being assumed on their behalf. This is
  the same general anti-confused-deputy pattern used across AWS service-to-service trust
  (S3→Lambda, EventBridge→targets, etc.), not AgentCore-specific, but worth recognizing

### Production hardening — reconfirms point 21's warning at the actual policy level
- `BedrockAgentCoreFullAccess` (the convenient managed policy) grants
  `GetWorkloadAccessTokenForUserId` broadly — AWS's OWN docs explicitly call this out as
  risky: "allows issuing workload access tokens using caller-supplied user identifier
  strings without IdP token verification" (this is literally the unverified-header mechanism
  flagged in point 21)
- **Explicit AWS recommendation**: for production, where you have real JWT tokens available,
  explicitly DENY `GetWorkloadAccessTokenForUserId` and grant only
  `GetWorkloadAccessTokenForJWT`. Copy only the specific statements you need out of the full
  managed policy into a custom one scoped to your actual resources — don't run production on
  the broad managed policy as-is

## 24. MCP tool permission & agent (A2A) permission — where they actually live

Sources: [Deploy MCP servers in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html), [AgentCore Gateway and Policy in AgentCore IAM Permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-permissions.html)

Yes, there's more IAM surface here — but there's no single unified "MCP permission."
It depends entirely on which ROLE you're playing and which AWS service sits on the other
end. Three genuinely different scenarios:

### Scenario 1 — your agent IS an MCP server (others call it, point 5/13)
- **No new IAM concept at all.** When Runtime hosts your agent with `--protocol MCP`,
  inbound access is governed by the SAME inbound auth mechanism from point 21 — either IAM
  SigV4 or JWT Bearer Token via `authorizerConfiguration`. Whoever calls your MCP tools needs
  `bedrock-agentcore:InvokeAgentRuntime` (SigV4 path) or a valid bearer token (JWT path)
  exactly like any other protocol. MCP doesn't get its own separate permission model — it
  rides on the Runtime-level inbound auth already covered

### Scenario 2 — your agent CALLS tools fronted by AgentCore Gateway (a DIFFERENT service)
- **This is the real new surface.** AgentCore Gateway is a separate AgentCore service (one
  of the "Build" pillar services alongside Runtime, Memory, Identity) that turns Lambda
  functions/APIs into MCP tools your agent can call. Gateway has its OWN **Gateway execution
  role** — completely separate from your agent's Runtime execution role (point 23)
- **Gateway execution role needs**: `lambda:InvokeFunction` scoped to the target Lambda
  ARN (if the tool backend is Lambda — Gateway always uses IAM auth for the Lambda call
  itself, no way around that), plus its own trust policy trusting
  `bedrock-agentcore.amazonaws.com`
- **If using AgentCore Policy** (Cedar-based authorization decisions on which tool calls are
  allowed) **on top of Gateway**: the Gateway execution role additionally needs
  `bedrock-agentcore:AuthorizeAction`, `PartiallyAuthorizeActions`, `GetPolicyEngine` — these
  are NOT auto-granted, must be added manually
- **Outbound auth from Gateway to the actual backend**: either IAM SigV4 (Gateway's own role
  credentials authenticate to the target) or OAuth — same two-mechanism pattern already seen
  for Runtime inbound auth (point 21), just applied one hop further down the chain
- **Best practice AWS states explicitly**: scope the Gateway execution role to only the
  specific targets configured, avoid wildcard Action/Resource — same least-privilege
  discipline as the Runtime execution role in point 23
- **Practical takeaway**: your AGENT's own execution role doesn't need Lambda-invoke
  permissions at all if you're going through Gateway — Gateway holds that permission on
  your agent's behalf. Your agent just needs permission to call the Gateway endpoint itself

### Scenario 3 — agent-to-agent via A2A (point 14/21, reconfirmed here)
- Each sub-agent is its OWN separate Runtime deployment — own ARN, own execution role, own
  Workload Identity, own inbound auth config. Nothing new beyond what points 14 and 21
  already established: the calling (supervisor) agent needs valid OUTBOUND credentials to
  reach the sub-agent, exactly like reaching any other authenticated Runtime endpoint
- No "agent permission" as a distinct IAM primitive — it's just Runtime-to-Runtime auth,
  the supervisor is simply another caller from the sub-agent's point of view

### The one-line mental model to keep these straight
Runtime execution role (point 23) = what YOUR agent's code can do. Gateway execution role
(new here) = what GATEWAY can do on your agent's behalf when fronting external tools. A2A
sub-agent's execution role = a completely separate agent's own permissions, reached via
normal inbound/outbound auth, not a shared or inherited permission set.

## 25. Observability

Sources: [Add observability to your Amazon Bedrock AgentCore resources](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html), [Get started with AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html)

### Two tiers of data, one required one-time account setup
- **Tier 1 — service-generated, automatic**: basic metrics/logs from the AgentCore service
  itself, land in CloudWatch by default with minimal setup (execution role already needs the
  logs/X-Ray perms from point 23 — that's not a coincidence, those ARE the observability
  permissions)
- **Tier 2 — code-instrumented, richer**: full spans, traces, custom metrics, visible on the
  **GenAI Observability dashboard** — requires the ADOT (AWS Distro for OpenTelemetry) SDK
  wired into your agent code
- **One-time ACCOUNT-level prerequisite for either tier**: enable **CloudWatch Transaction
  Search** (console: Application Signals → Transaction Search → Enable, tick "ingest spans as
  structured logs"; or API: `put-resource-policy` granting `xray.amazonaws.com` →
  `logs:PutLogEvents`, then `update-trace-segment-destination --destination CloudWatchLogs`,
  optional `update-indexing-rule` for sampling %). Takes ~10 min to start returning results.
  Not per-agent — one-time per AWS account/region

### Auto-instrumentation depends on HOW you deployed — genuinely different by method
- **Deploy via `agentcore deploy` (the AgentCore CLI)**: fully automatic. "No additional OTEL
  libraries or configuration are needed" — AWS's own words. The CLI wires ADOT in for you
- **Deploy via raw boto3/CDK/CloudFormation/Terraform/manual container** (every method
  already built in this repo's `01-agentcore-runtime/`): NOT automatic. You must manually add
  `aws-opentelemetry-distro>=0.10.0` + `boto3` to `requirements.txt`, and run your entrypoint
  via `opentelemetry-instrument python my_agent.py` (or as the container `CMD` for
  Dockerfile-based deploys) — a real, concrete gap between the "quick path" CLI and every
  other deployment method this project has already built
- **Framework support**: Strands/LangChain/CrewAI ship built-in OTEL + GenAI semantic-
  convention support out of the box. Other frameworks need an auto-instrumentation add-on —
  OpenInference, Openllmetry, OpenLit, or Traceloop are the ones AgentCore explicitly supports

### Session ID and trace ID propagation — two SEPARATE mechanisms, don't conflate
- **Session ID at invoke time**: pass `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header →
  ADOT automatically propagates it as `session.id` into downstream telemetry. This is the
  HTTP-header path, works for standard Runtime invokes
- **Session ID in custom code** (finer control, or for non-Runtime agents): OTEL baggage —
  `baggage.set_baggage("session.id", session_id)` then `attach(ctx)` — a code-level mechanism,
  separate from the header approach
- **Trace ID propagation**: either pass `traceId=<traceId>` as an invoke parameter, or supply
  `X-Amzn-Trace-Id` (X-Ray format) / `traceparent` (W3C format) as custom headers — OTEL
  auto-generates one if you supply neither

### Enhanced observability custom headers (optional, at `InvokeAgentRuntime` time)
| Header | Purpose |
|---|---|
| `X-Amzn-Trace-Id` | X-Ray format trace ID (root/parent/sampling decision) |
| `traceparent` | W3C standard tracing header, needed for cross-vendor trace correlation |
| `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` | session identifier (already known from point 9/18) |
| `mcp-session-id` | MCP-specific session identifier |
| `tracestate` | vendor-specific extra tracing context alongside `traceparent` |
| `baggage` | arbitrary key-value context propagated across service boundaries |
- Same header set (X-Ray ID + traceparent only) also works on Built-in Tools APIs
  (`StartCodeInterpreterSession`, etc.) and Identity APIs (`GetWorkloadAccessToken*`,
  `GetResourceOauth2Token`) — observability isn't Runtime-exclusive, spans the whole platform

### Logging behavior genuinely DIFFERS by resource type — don't assume uniformity
- **Runtime**: CloudWatch log group **auto-created by default** at deploy time — no manual
  config needed for basic logs
- **Memory & Gateway**: AgentCore does **NOT** auto-configure log destinations — you must
  manually set one up (console: resource's "Log delivery" pane; or SDK: `put_delivery_source`
  → `put_delivery_destination` → `create_delivery`, a 3-step wiring). Default console-created
  log group pattern: `/aws/vendedlogs/bedrock-agentcore/{memory|gateway}/APPLICATION_LOGS/{resource-id}`
- **Built-in tools** (Browser, Code Interpreter): **NO default logs at all**. You emit and
  route your own if you want any
- **Tracing is a SEPARATE toggle from log delivery**, per resource, in the console — enabling
  log delivery does NOT automatically enable tracing and vice versa. Spans land in the
  `aws/spans` log group / `/aws/spans/default` once tracing is on
- **Runtime's actual log group paths**: stdout/stderr at
  `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/[runtime-logs] <UUID>`, OTEL
  structured logs at `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs`
  — two DIFFERENT log groups for raw output vs structured OTEL data

### The GenAI Observability dashboard (CloudWatch console)
Three views: **Agents View** (every agent, on-Runtime or not, drill into runtime metrics/
sessions/traces per agent), **Sessions View** (navigate all sessions across agents),
**Trace View** (execution graph + timeline per individual trace — see the actual agent
reasoning trajectory, not just a flat log)

### Non-Runtime agents get the SAME dashboard — real forward-link to the breadth-phase modules
Agents deployed on your OWN infrastructure (Lambda/EC2/ECS/EKS/App Runner — every method
already built in `04-lambda/` through `08-eks/`) can appear on the identical GenAI
Observability dashboard. Requires manually setting AWS creds + OTEL env vars
(`AGENT_OBSERVABILITY_ENABLED=true`, `OTEL_PYTHON_DISTRO=aws_distro`,
`OTEL_PYTHON_CONFIGURATOR=aws_configurator`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`,
`OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=...,x-aws-log-stream=...,x-aws-metric-namespace=...`,
`OTEL_RESOURCE_ATTRIBUTES=service.name=<name>`) then running via `opentelemetry-instrument`.
**Observability is genuinely NOT a Runtime-exclusive feature** — worth remembering, since
it's easy to assume it only works for Runtime-hosted agents

### Escape hatch and best practices
- `DISABLE_ADOT_OBSERVABILITY=true` env var — unsets AgentCore's default ADOT config
  entirely, for wiring your own 3rd-party platform (Datadog, Langfuse, etc.) instead
- **Security-relevant best practice, easy to overlook**: "filter sensitive data from
  observability attributes and payloads" — traces/spans can leak PII or secrets if your
  agent's prompts/tool calls aren't sanitized before they hit telemetry, worth remembering
  alongside point 22's "don't put secrets in env vars" guidance — same class of mistake,
  different surface
- Other stated best practices: reuse session IDs across related requests, add custom
  attributes for context, monitor memory usage metrics specifically, set CloudWatch alarms
  proactively rather than only reviewing dashboards reactively

### Built-in vs your job — the checklist version of this whole point
**Automatic, zero config:**
- CloudWatch log group auto-created at Runtime deploy time (Runtime ONLY — Memory/Gateway
  don't get this, see below)
- Execution role template (point 23) already bundles the CloudWatch Logs + X-Ray +
  CloudWatch-metrics permissions needed for basic telemetry to flow
- Deploy via `agentcore deploy` (the CLI) specifically → full OTEL auto-instrumentation,
  zero code changes, model calls/tool executions/token usage/spans all captured

**You must do this yourself, every time:**
- Enable CloudWatch Transaction Search — ONE-TIME per AWS account/region, gates the ENTIRE
  GenAI Observability dashboard, nothing shows up without it
- Deployed via anything OTHER than the CLI (raw boto3/CDK/CFN/Terraform/manual container —
  every method already in `01-agentcore-runtime/`) → manually add `aws-opentelemetry-distro`
  to `requirements.txt` + run via `opentelemetry-instrument python my_agent.py` (or as
  container `CMD`) — the single biggest real gap between the CLI's happy path and everything else
- Enable TRACING explicitly per resource in console — separate toggle from log delivery,
  turning on one does NOT turn on the other
- Memory/Gateway resources → no automatic log group, configure a destination yourself
  (console "Log delivery" pane, or SDK `put_delivery_source`→`put_delivery_destination`→
  `create_delivery`)
- Built-in tools (Browser/Code Interpreter) → NO default logs at all, emit and route your own
- Non-Runtime agents (Lambda/EC2/ECS/EKS — the breadth-phase modules) wanting the SAME
  dashboard → fully manual: AWS creds + full OTEL env var set
  (`AGENT_OBSERVABILITY_ENABLED`, `OTEL_PYTHON_DISTRO`, `OTEL_PYTHON_CONFIGURATOR`,
  `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_EXPORTER_OTLP_LOGS_HEADERS`,
  `OTEL_RESOURCE_ATTRIBUTES`)
- Sanitizing sensitive data out of traces before they hit telemetry — AWS does not do this
  for you, explicitly your responsibility per AWS's own best-practices list
- Picking a 3rd-party observability vendor instead of ADOT — set
  `DISABLE_ADOT_OBSERVABILITY=true` yourself, AWS doesn't do this automatically either

## 26. Networking & VPC (category 13 — no longer deferred)

Sources: [Configure Amazon Bedrock AgentCore Runtime and tools for VPC](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html), [Network connectivity patterns for agents deployed on Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/blogs/networking-and-content-delivery/network-connectivity-patterns-for-agents-deployed-on-amazon-bedrock-agentcore-runtime/) (AWS engineering blog, May 2026)

### The single most important fact — VPC mode ≠ private inbound
- **Two network modes**: `PUBLIC` (default) or `VPC`, set via `networkConfiguration` at
  create time. `PUBLIC` = both inbound AND outbound traffic traverse the internet
- **Critical, non-obvious point confirmed by AWS's own blog**: switching to `VPC` mode ONLY
  changes OUTBOUND connectivity (giving the agent private-IP access to your VPC resources).
  **It does NOT make the agent's own inbound endpoint private.** The agent stays reachable
  from the public internet exactly as before unless you separately lock it down (see Pattern
  3 below). Easy to wrongly assume "VPC mode = private agent" — it isn't, by itself

### ENI mechanics
- AgentCore creates elastic network interfaces (ENIs) in your chosen subnets via the
  service-linked role `AWSServiceRoleForBedrockAgentCoreNetwork` (auto-created on first VPC
  use; permission for it is bundled in `BedrockAgentCoreFullAccess`)
- **ENIs are SHARED** across any agents using identical subnet+security-group config — not
  one ENI per agent
- **Gotcha**: deleting an agent doesn't instantly reclaim its ENI — can persist in your VPC
  for **up to 8 hours** before automatic cleanup
- Each ENI gets a private IP from the subnet you specify; the attached security group is
  what actually controls reachability

### Supported Availability Zones — a real deploy-time failure mode
- AgentCore VPC connectivity only works in SPECIFIC AZs per region (not all AZs) — e.g.
  us-east-1 supports only `use1-az1/az2/az4`, not az3/az5/az6. Full table in the source doc
- **Picking a subnet in an unsupported AZ fails the deployment outright** — not a warning,
  a hard failure at resource creation. Always verify via
  `aws ec2 describe-subnets --query 'Subnets[0].AvailabilityZoneId'` before configuring

### Public subnet ≠ internet access (repeated AWS warning, common mistake)
- Placing the Runtime's ENI in a PUBLIC subnet does NOT give it internet access — AWS is
  explicit and repeats this warning twice in the source doc. Correct pattern: **private
  subnet + NAT gateway + internet gateway**, standard 3-tier VPC internet-egress design,
  nothing AgentCore-specific about the pattern itself, just a reminder it still applies here

### VPC endpoints — required or strongly recommended, with a real cost gotcha
- If your VPC has no internet access: VPC endpoints for ECR (`ecr.dkr` + `ecr.api`), S3
  (gateway endpoint), and CloudWatch Logs (`logs`) are REQUIRED for basic function
- **Even WITH a NAT gateway, AWS strongly recommends the S3 gateway endpoint anyway** — real
  cost reason, not just security: container agents periodically re-pull their image from
  ECR, and ECR stores image LAYERS in S3 behind the scenes. Without an S3 gateway endpoint,
  that layer-pull traffic routes through your NAT gateway and racks up NAT data-processing
  charges. The S3 gateway endpoint itself is free. Easy to miss since it's not obviously
  "your" S3 traffic — it's AgentCore's internal ECR-layer-storage traffic
- Same logic applies to direct-code-zip deployments (code stored in an AWS-owned bucket,
  `acr-code-*`) and to session storage (point 17's `acr-storage-*` bucket) — all three should
  be added to a scoped S3 gateway endpoint policy if you're using them

### Security groups — standard stateful pattern, one concrete example
- Runtime's SG needs an OUTBOUND rule to reach the target resource; the TARGET's SG needs an
  INBOUND rule allowing the Runtime's SG. Security groups are stateful — return traffic is
  automatic, no separate inbound rule needed on the Runtime side
- Worked example (RDS/MySQL): Runtime SG outbound → TCP 3306 → RDS SG. RDS SG inbound ← TCP
  3306 ← Runtime SG. Nothing inbound needed on Runtime's own SG — it only initiates
- Same NFS-on-2049 pattern from point 17's filesystem networking applies here too — this
  page just adds the actual `authorize-security-group-egress`/`-ingress` CLI commands and a
  self-referencing-rule note if you reuse ONE security group for both runtime and mount target

### The 4 production network patterns (from AWS's own engineering blog — the real mental model)
This is the best way to think about "how private does my agent actually need to be":

1. **Public endpoint (default)** — inbound AND outbound both over the internet. Fine for a
   demo or anything not touching private data
2. **+ VPC connectivity** — adds OUTBOUND private access to VPC/on-prem resources via ENIs.
   Inbound is STILL public (the point above) — this pattern alone is "agent can reach my
   private DB" not "agent is private"
3. **+ Resource-based policy blocking public inbound** — a genuinely NEW access-control layer
   (distinct from IAM execution role point 23, distinct from inbound JWT/SigV4 auth point
   21): condition-key-based rules on the Runtime resource itself (`aws:SourceVpc`,
   `aws:SourceIp`, `aws:SourceVpce`) that deny requests before they even reach the agent's
   auth check. Pair with an INTERFACE VPC endpoint (AWS PrivateLink) so legitimate in-VPC
   callers reach the agent without ever touching the public internet — condition the policy
   on `aws:SourceVpce` specifically for this
4. **Fully isolated VPC** — no internet gateway, no NAT gateway at all. Inbound only via the
   PrivateLink interface endpoint + resource policy from Pattern 3; outbound to AWS services
   only via VPC endpoints (ECR/S3/CloudWatch minimum, add more per your agent's actual
   dependencies e.g. DynamoDB/SQS). Complete isolation, for highly sensitive data — highest
   pattern AWS documents

### Resource-based policies — worth flagging as a 3rd distinct access-control mechanism
Point 21 covered inbound AUTH (who's allowed to invoke, identity-based: SigV4 or JWT).
Point 23 covered the execution role (what the agent's code can DO once running). **Resource-
based policies are a third, separate layer**: network-PATH-based conditions on the resource
itself, evaluated BEFORE auth even runs. Not a replacement for auth — a filter in front of it.

### Monitoring, troubleshooting, and a real performance cost
- **VPC connectivity increases session startup/init time** — worth knowing before assuming
  a slow cold-start is a bug; it's an expected cost of ENI provisioning
- Common failure signatures: connection timeouts (check SG rules + route tables first),
  DNS resolution failures (verify `enableDnsSupport`/`enableDnsHostnames` both `true` on the
  VPC), missing ENIs (check the service-linked role's permissions, or a service quota limit)
- File system mount failures over VPC (point 17) get their own detailed diagnostic flow in
  this doc — AZ-mismatch between agent subnets and mount targets is called out as the most
  common CAUSE of INTERMITTENT (not consistent) failures, since some invocations land in an
  AZ with a mount target and some don't

### Networking primer — the gated-estate story (for non-network people, memory aid)
Mental model: your **VPC** is a private gated housing estate you built and own.

- **VPC** — the whole estate. Defined by its own private address range (**CIDR block**,
  e.g. `10.0.0.0/16`)
- **Subnet** — one street inside the estate, tied to ONE specific Availability Zone.
  **Public subnet** = has a route to the front gate. **Private subnet** = no direct route out
- **Route table** — the street sign at each street's entrance, saying which way leads to the
  front gate vs which way stays local
- **Internet Gateway (IGW)** — the estate's front gate. Two-way: anyone authorized walks in
  or out. Free, one per VPC
- **NAT Gateway** — an exit-only booth in the public subnet. Lets private-subnet residents
  leave to run errands (outbound internet); strangers outside can't use it to get IN. Costs
  money per hour + per GB — the reason point 26 flagged the S3 gateway endpoint as a way to
  avoid routing AgentCore's own ECR-layer traffic through it unnecessarily
- **ENI (Elastic Network Interface)** — the agent's actual mailbox/street address: the real
  network card that gets a private IP. This is literally what AgentCore creates per point 26
- **Port** — the door number at that address for a specific kind of visitor (443 = HTTPS
  front door, 3306 = MySQL delivery door, 2049 = NFS door used for point 17's filesystem mounts)
- **Security Group** — the guard standing at one house's door. STATEFUL: remembers who it let
  in, so the reply walks back out automatically without a second check. Attached per-resource
  (per-ENI), allow-only, no explicit deny
- **NACL (Network ACL)** — the checkpoint at the ESTATE boundary, not one house. STATELESS:
  checks every car in both directions independently and forgets it the moment it's through.
  Attached per-subnet, supports both allow AND deny rules, evaluated in order. Most teams
  leave the default (allow-everything) NACL alone and do real access control at the SG level
- **VPC Endpoint** — a private tunnel straight to one specific AWS building (like S3), never
  touching the public road at all. Two kinds: Gateway endpoints (free, only S3/DynamoDB) and
  Interface endpoints (small hourly cost, most other services — this is how point 26's
  Pattern 3/4 lets in-VPC callers reach the agent without the public internet)
- **PrivateLink** — the underlying AWS tech that digs those private tunnels
- **DNS resolution / DNS hostnames** — two separate VPC-level switches that BOTH must be on
  for private AWS hostnames (like an EFS/S3-Files mount target) to resolve inside the estate
  at all — the exact troubleshooting check in point 26's file-system-mount-fails section

Quick shortcut: security group = per-house, stateful, allow-only. NACL = per-street, stateless,
allow+deny, order matters. Route table decides where traffic CAN go; SG/NACL decide whether
it's ALLOWED to.

## 27. Security best practices (category 12, the piece pricing/limits didn't cover)

Source: [Security best practices for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html) — a consolidated doc referenced by name in points 19/24/26 but never actually read until now. Real new material, not just a recap.

### MMDS credential exposure — the single most important new fact here
- Inside the microVM, execution role credentials are reachable by ANY code via a metadata
  endpoint (**MMDS** — MicroVM Metadata Service), exactly like EC2's IMDS
- **Practical consequence**: if your agent has a prompt-injection or code-execution
  vulnerability, whatever the execution role can do, an attacker can do — the microVM
  boundary protects you from OTHER customers, not from your OWN over-privileged role. This
  is the concrete mechanism behind "scope the execution role tightly" (point 23), not just
  abstract advice
- **Prevent privilege escalation**: execution role should have ≤ the privileges of whoever
  is allowed to INVOKE the agent — if a caller can invoke an agent whose role can do more
  than the caller itself could do directly, that's a privilege escalation path

### Custom header limits — a real gotcha not in point 21/25's coverage
- Headers capped at **4KB per value, 20 headers max per runtime**
- **`Authorization` header is reserved** — only usable for agents configured with OAuth
  inbound access, can't be repurposed for other custom data on a SigV4-configured runtime

### Resource-based policy evaluation — extends point 26's Pattern 3 with real mechanics
- For `InvokeAgentRuntime`/`InvokeAgentRuntimeCommand`, AWS evaluates policy on BOTH the
  runtime AND the endpoint — **both must explicitly allow**, cross-account access needs
  policies on both resources or the request is denied
- **Explicit deny always wins** — over any identity-based OR resource-based allow, standard
  IAM rule but worth reconfirming here since AgentCore stacks multiple policy types (execution
  role, resource-based policy, VPC endpoint policy) that could plausibly conflict
- **New IAM condition keys**: `bedrock-agentcore:subnets` / `bedrock-agentcore:securityGroups`
  — use these to ORG-WIDE enforce that every Runtime in an account must deploy in an approved
  VPC/subnet, a real governance lever for a security team, not just a per-agent setting

### VPC endpoint policy nuance for OAuth vs SigV4 — genuinely non-obvious
- VPC endpoint policies can only restrict callers by IAM PRINCIPAL — which only exists for
  SigV4 callers. **For OAuth-based requests, the endpoint policy's `Principal` must be `*`**
  — you cannot use a VPC endpoint policy to further restrict WHICH OAuth users get through,
  that restriction has to live in the JWT authorizer config instead (point 21)
- Specific PrivateLink endpoint names, useful to actually have: data plane
  `com.amazonaws.region.bedrock-agentcore`, control plane
  `com.amazonaws.region.bedrock-agentcore-control` — two separate endpoints for invoke-time
  vs manage-time API calls

### Shared responsibility model — clean split, genuinely interview-relevant
| AWS handles | You handle |
|---|---|
| microVM isolation at hardware level | Agent code security + dependency management |
| OS kernel patching (all deployment modes) | IAM access controls + resource policies |
| Language runtime patching (direct-code-deploy ONLY) | Command execution security |
| Network infrastructure security | Session-to-user mapping enforcement |
| Service availability/resilience | Container image updates (YOUR job for container deploys) |
| | Input validation + prompt injection prevention |
| | Network config (SGs, VPC endpoints, route tables) |
- **Real operational gotcha in the fine print**: AWS patches the OS kernel automatically for
  EVERY deployment mode, but for direct-code-deploy specifically, AWS does NOT patch the
  language runtime itself once it hits end-of-support — deprecated runtimes run as-is with
  unpatched vulnerabilities. For container deploys, YOU are entirely responsible for
  rebuilding with an updated base image — nothing auto-patches inside your own image, ever
- Security patches can break code relying on old insecure behavior — if that risk is
  unacceptable, AWS's own advice is to use container images instead of direct-code-deploy,
  since containers give you control over exactly when to take a base-image update

### A few concrete practices worth remembering
- **Run containers as non-root** — limits blast radius of a code-execution vulnerability,
  standard container hardening, explicitly called out for AgentCore specifically
- **Separate user-delegated vs autonomous credentials**: Authorization Code Grant (3LO, point
  21) when acting ON BEHALF of a specific user, Client Credentials Grant when the agent acts
  autonomously/independently — picking the wrong one blurs who's actually accountable for an action
- **Command execution's real security boundary is the microVM, not the command itself** —
  `InvokeAgentRuntimeCommand` (point 19) has full access to whatever the execution role and
  filesystem allow; restrict WHO can call it via IAM, don't rely on the command content
  itself being "safe"

### Encryption (brief, mostly "already handled")
- In transit: TLS 1.2 minimum, enforced by default, no setup needed. AWS recommends TLS 1.3
  where the client supports it
- At rest: AWS-owned KMS keys by default — no customer action required unless you need
  customer-managed keys specifically (not covered in this doc)
