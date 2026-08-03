# 10-agentcore-runtime-deepdive

## At a glance

| | |
|---|---|
| **Scope** | Full capability depth of AgentCore Runtime -- not deployment mechanics (that's `01-agentcore-runtime`), but everything Runtime actually *does* once your code is running there |
| **Source material** | AWS's "AgentCore Deep Dive: Runtime" video (AWS Show and Tell), the official Runtime devguide (23 sub-topics), and direct AWS Console exploration |
| **Status** | Category structure defined, build not yet started |
| **What's different here** | Part of the depth phase (`10`-`18`) that follows the breadth phase (`00`-`09`) -- one AgentCore capability covered exhaustively instead of one agent deployed many ways |

`01-agentcore-runtime` already proved 8 different ways to get an agent *onto* Runtime. This module
is the other half of the story: once it's there, what can Runtime actually do? Deployment mechanics
and capability depth are genuinely different questions, and conflating them was a real gap caught
partway through planning this module.

This uses a different example application than the calculator agent used throughout the breadth
phase -- several of these categories (protocols, outbound auth) need a real MCP server and a real
third-party API to demonstrate anything meaningful. Calculator can't carry this phase.

## Categories

| # | Topic | Status |
|---|---|---|
| 01 | [Framework & Model Flexibility](./01-framework-and-model-flexibility/) | Not started |
| 02 | [Session Isolation & State](./02-session-isolation-and-state/) | Not started |
| 03 | [Session Lifecycle & Timeouts](./03-session-lifecycle-and-timeouts/) | Not started |
| 04 | [Async & Long-Running Jobs](./04-async-long-running-jobs/) | Not started |
| 05 | [Protocols: MCP, A2A, AG-UI](./05-protocols-mcp-a2a-agui/) | Notes done (RUNTIME-BASICS.md pts 13-16), code not started |
| 06 | [Invocation & Streaming](./06-invocation-and-streaming/) | Notes done (pts 18-19), code not started |
| 07 | [Inbound & Outbound Auth](./07-inbound-outbound-auth/) | Notes done (pt 21 — full inbound/outbound/workload identity/Token Vault flow), code not started |
| 08 | [Versioning & Endpoints](./08-versioning-and-endpoints/) | Notes done (pt 20), code not started |
| 09 | [Runtime Environment Mechanics](./09-runtime-environment-mechanics/) | Filesystem config covered (pt 17), rest not started |
| 10 | [IAM Permissions](./10-iam-permissions/) | Notes done (pt 23 — execution role vs Workload Identity, permission buckets, trust policy, prod hardening), code not started |
| 11 | [Observability Hooks](./11-observability-hooks/) | Notes done (pt 25 — ADOT, auto-vs-manual instrumentation by deploy method, session/trace propagation, per-resource logging), code not started |
| 12 | [Security, Pricing & Limits](./12-security-pricing-limits/) | Notes done (pricing pts 4-6/19, security pt 27 — MMDS credential exposure, shared responsibility model, header limits), code not started |
| 13 | [Networking & VPC](./13-networking-vpc/) | Notes done (pt 26 — VPC-mode inbound/outbound clarification, ENI mechanics, 4 production network patterns, VPC endpoints cost gotcha), code not started |

13 categories total: roughly 8 need real hands-on code and working examples, the rest (IAM,
Observability hooks, Security/Pricing/Limits) are reference/notes-driven and lean on cross-linking
to other parts of this repo (`iam/`, the future `17-agentcore-observability` module) rather than
standing alone. Networking/VPC was initially parked (same discipline as `08-eks`) but has since
been covered in notes -- RUNTIME-BASICS.md point 26.

## Console notes

See [`console-notes/`](./console-notes/) -- a running scratchpad of what's been explored directly
in the AWS Console for Runtime, kept separate from the category folders since it's not tied to one
specific capability.

## Source material

- AWS Show and Tell -- "Amazon Bedrock AgentCore Deep dive series: Runtime" (transcript reviewed,
  cleaned copy kept locally in `_research/agentcore-transcripts/`, not committed -- source content
  isn't ours to republish)
- [Host agent or tools with Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html) -- official devguide, 23 sub-topics
- [Securely launch and scale your agents and tools on Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/blogs/machine-learning/securely-launch-and-scale-your-agents-and-tools-on-amazon-bedrock-agentcore-runtime/) -- AWS engineering blog, denser/more technical than the video; source of the real architecture diagrams (session lifecycle, session isolation, embedded identity flow, memory interaction, billing model) referenced in `RUNTIME-BASICS.md`
