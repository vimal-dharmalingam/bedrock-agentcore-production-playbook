# Agentcore2026 — Roadmap

## Purpose
Two goals, tracked together:
1. **Portfolio for job search** — currently GenAI Lead at an investment firm (London), building
   a public GitHub repo demonstrating full production-level agent deployment skills to support
   a move to a new role.
2. **AWS AI certification exam prep** — hands-on practice doubles as study material. Where
   relevant, note exam-relevant concepts (service architecture, IAM permission models, managed
   vs. self-managed tradeoffs) in module READMEs, not just "it worked" logs.

Single running example throughout: a simple calculator agent (Strands Agents framework),
redeployed via every mechanism below so the differences are directly comparable.

## Folder structure

```
Agentcore2026/
├── README.md
├── ROADMAP.md                         # this file
├── .gitignore
│
├── 00-local-dev/
│   ├── local-python/                  # run agent directly with `python`, no Docker
│   └── local-docker/                  # same image built for ECR, run + curl-tested locally
│
├── 01-agentcore-runtime/
│   ├── starter-toolkit-cli/           # agentcore configure/launch (deprecated, document tooling shift)
│   ├── boto3-direct/                  # deploy_my_agent.py, invoke_agent.py
│   ├── direct-code-zip/               # CodeConfiguration path — no Docker/ECR at all
│   ├── manual-container-build/        # own Dockerfile, docker build/push to ECR, create_agent_runtime
│   ├── cdk/                           # hand-written CDK
│   ├── terraform/                     # AWS's AgentCore Terraform provider
│   ├── cloudformation/                # raw, hand-authored YAML/JSON template
│   └── scripts/                       # list_agents.py, delete_agent.py, wait_for_model_access.py
│
├── 02-agentcore-cli/                  # new npm @aws/agentcore CLI, generates its own CDK app
│   └── CalcAgentCli/                  # IN PROGRESS — local dev working, deploy pending
│
├── 03-classic-bedrock-agent-lambda/   # different service: Bedrock Agents + Lambda action groups
│
├── 04-lambda/                         # agent as standalone Lambda (container + zip variants)
│   ├── cdk/
│   └── terraform/
│
├── 05-ec2/                            # raw VM (systemd service, security group)
│   └── terraform/
│
├── 06-ecs-fargate/                    # containerized, orchestrated, behind an ALB
│   └── cdk/
│
├── 07-app-runner/                     # optional/stretch
│   └── cloudformation/
│
├── 08-eks/                            # optional/lowest priority — cluster IaC + separate K8s manifests
│
├── 09-cicd-github-actions/            # wraps any of the above via OIDC-federated pipeline
│
└── iam/                               # cross-cutting: real policy JSONs from permission debugging
```

## Status (updated as we go)

- [x] `01-agentcore-runtime` — reorganized into the full subfolder structure. `starter-toolkit-cli/`,
      `boto3-direct/`, `direct-code-zip/`, and `manual-container-build/` done and working end to
      end; `scripts/` done; `cdk/`, `terraform/`, `cloudformation/` still scaffolded with
      placeholder READMEs, not yet built.
- [x] `02-agentcore-cli` — scaffolded, calculator tool ported, local dev, deploy (via CDK), and
      invoke all confirmed working end to end.
- [x] `03-classic-bedrock-agent-lambda` — fully working end to end (console-built agent + Lambda
      action group, boto3 test script with trace support). See its README for platform-status
      context (Bedrock Agents Classic maintenance mode) and exam-alignment notes above.
- [ ] `04` through `09` and `iam/` — not started. **Next up per original plan: pick one of the
      unstarted `01-agentcore-runtime` sub-methods (cdk, terraform, cloudformation) to build
      next, before moving to compute-target modules.**

## Exam alignment — AWS Certified Generative AI Developer - Professional (AIP-C01)
Confirmed against the official exam guide (docs.aws.amazon.com/aws-certification/latest/ai-professional-01/):

- **AgentCore, not classic Agents, is the named exam topic.** "Amazon Bedrock AgentCore" is
  explicitly listed as its own in-scope service; classic "Bedrock Agents" isn't named separately
  anywhere (only generic "Amazon Bedrock" is listed). `01`/`02` are squarely on-target; `03` was
  worth building for the conceptual model but isn't a heavily-tested topic by name.
- **Terraform is NOT in scope** for this exam (absent from the in-scope services list, which is
  otherwise thorough). Keep building it for the job-search portfolio, just don't prioritize it
  for exam study time. CDK and CloudFormation ARE in scope.
- **CI/CD is tested via AWS-native tooling specifically** — CodePipeline + CodeBuild are named
  (Task 2.3.5). Add a CodePipeline-based CI/CD example alongside the planned GitHub Actions one
  — GitHub Actions itself won't appear on the exam (not an AWS service).
- **Compute-target modules (04-08) are all validated** — Lambda, EC2, App Runner, ECS, EKS,
  Fargate, ECR are all explicitly in scope.
- **CloudShell is explicitly OUT of scope** (despite being used constantly today for IAM fixes)
  — practically useful, not exam-tested.

### New gaps to add to the roadmap (from Task 2.1 "Implement agentic AI solutions and tool integrations")
- **MCP servers hosted on Lambda (stateless) or ECS (complex)** — distinct pattern from `03`'s
  "Lambda as a Bedrock action group": here the agent talks to an MCP server, not a direct action
  group. The `02-agentcore-cli` scaffold already has a dormant MCP client stub worth actually
  using.
- **AWS Step Functions** — appears repeatedly across exam tasks (ReAct/chain-of-thought
  orchestration, safeguarded workflow stopping conditions, human-in-the-loop review/approval,
  dynamic model routing). Not in the roadmap at all currently — needs its own module or at least
  a dedicated experiment.
- **AWS Agent Squad** — named multi-agent framework, not yet explored.
- **Amazon Bedrock Prompt Flows / Prompt Management** — named services, not yet explored.
- **Kiro** — AWS's AI-native IDE, listed under Developer Tools, worth basic familiarity.

## Candidate future module
**AgentCore managed harness** (`agentcore add harness`) — AWS's recommended replacement for
Bedrock Agents Classic (which entered maintenance mode July 30, 2026, see
`03-classic-bedrock-agent-lambda/README.md`). Config-based like Classic, but runs on AgentCore
infrastructure. Sits conceptually between `03` (fully managed, no code) and `01`/`02` (fully
custom code) — worth its own module once the core compute-target modules are done.

## Known gotchas already hit (keep documenting — good interview + exam material)
- Bedrock model lifecycle: old model IDs go Legacy/EOL, must track current model IDs
- One-time Anthropic "use case details" form required per AWS account before first invoke
- AWS Marketplace subscribe permissions needed for first-time third-party model invocation
- IAM inline policy 2048-char limit — use customer-managed policies instead
- `cdk bootstrap` needs broad/admin-level permissions — a one-time, account-wide step
- Windows terminal quoting (`cmd.exe` vs bash) breaks copy-pasted CLI examples from docs
- Windows console default codepage isn't UTF-8 — breaks on emoji in model responses

## Working IAM user
`always_learner` (account 486517829337) — deliberately narrow permissions, so every new AWS
feature tends to surface a new permission gap. This friction is itself useful exam/interview
material on the principle of least privilege, so it's not being "fixed" by granting admin access.
