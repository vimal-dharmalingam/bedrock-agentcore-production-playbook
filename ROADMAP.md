# Agentcore2026 — Roadmap

## Purpose
Four goals, tracked together (as of the goals-clarification session):
1. **Portfolio for job search** — currently GenAI Lead at Aviva (London), building a public
   GitHub repo demonstrating full production-level agent deployment skills to support a move
   to a new role.
2. **Job search deadline** — explicit target: land a new role before end of this year. This
   makes breadth-and-momentum matter more than exhaustive depth on any single module.
3. **AWS AI certification exam prep** — hands-on practice doubles as study material. Where
   relevant, note exam-relevant concepts (service architecture, IAM permission models, managed
   vs. self-managed tradeoffs) in module READMEs, not just "it worked" logs.
4. **Direct work relevance** — Aviva is about to start using AgentCore internally, so this
   learning has immediate on-the-job payoff, not just interview/exam value.
5. **Personal AgentCore project (separate initiative, not yet started)** — a customized personal
   assistant web app, connected to phone location, stay history, calendar, Gmail, a food-tracking
   history, custom news, Google Drive, with voice capability. Genuinely different in kind from
   modules 1-9 below (real tool/API integrations and an actual useful agent, vs. deployment-
   mechanism comparisons using one trivial calculator agent) — likely a stronger portfolio
   centerpiece than the deployment-comparison repo once built, and maps directly to exam Task 2.1
   ("Implement agentic AI solutions and tool integrations"). Scope/sequencing/repo location TBD.

Single running example throughout modules 1-9: a simple calculator agent (Strands Agents
framework), redeployed via every mechanism below so the differences are directly comparable.

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
│   ├── zip-deploy/
│   ├── cdk/
│   ├── terraform/
│   └── cloudformation/
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

- [x] `01-agentcore-runtime` — **COMPLETE. All 8 of 8 sub-methods done and working end to end:**
      `starter-toolkit-cli/`, `boto3-direct/`, `direct-code-zip/`, `manual-container-build/`,
      `cdk/`, `cloudformation/`, `terraform/`, `console/`. `scripts/` done. Same calculator agent
      deployed via every mechanism, each folder self-contained and independently runnable.
      `console/` alone surfaced 4 new IAM gaps (VPC read, Bedrock model listing, standalone IAM
      policy creation) — more than any single CLI/IaC tool, since a UI has to support every
      possible path through a form, not just the one action a script performs.
- [x] `02-agentcore-cli` — scaffolded, calculator tool ported, local dev, deploy (via CDK), and
      invoke all confirmed working end to end.
- [x] `03-classic-bedrock-agent-lambda` — fully working end to end (console-built agent + Lambda
      action group, boto3 test script with trace support). See its README for platform-status
      context (Bedrock Agents Classic maintenance mode) and exam-alignment notes above.
- [x] `04-lambda` — **COMPLETE. All 4 methods deployed, invoked, and documented:**
      `zip-deploy/` (boto3), `cdk/`, `terraform/`, `cloudformation/`. Deliberate exception to
      the pacing decision below: all 3 IaC tools built for Lambda since it's simple
      (no Docker/arm64), not just 1-2. `cloudformation/` surfaced a naming-driven gap (stack
      name didn't match an already-granted `CalcAgent*` pattern) fixed by renaming the stack,
      not by touching IAM — kept the account under the 10-managed-policy ceiling.
      **Pacing decision (end-of-year deadline):** `05` onward gets 1-2 solid methods per
      compute target, not the full 8-method depth `01-agentcore-runtime` got — breadth across
      `05`-`09` matters more now than exhaustive depth on any single target.
- [x] `05-ec2` — **COMPLETE. Terraform method deployed, invoked, and documented** (single method,
      per the pacing decision — first compute target with no managed invoke API, so Terraform
      does genuine IaaS provisioning: AMI lookup, security group, IAM instance profile, and a
      `user_data` cloud-init bootstrap running the agent as a FastAPI app behind systemd).
      By far the longest debugging chain in the project so far — five distinct root causes before
      it worked: (1) a security-group `description` field rejecting an apostrophe, (2) IAM gaps
      requiring policy-version extension (account was already at the 10-policy ceiling), (3) a
      self-inflicted bug where `user_data.sh.tpl`'s own top comment used literal `${...}` syntax,
      which `templatefile()` substituted mid-comment and corrupted the whole script — found by
      rendering the template locally and reproducing the exact failure with plain `bash`, byte-
      for-byte matching the real EC2 console log, before touching AWS again, (4) `terraform
      apply`'s default in-place user-data update not re-running cloud-init, requiring
      `user_data_replace_on_change = true`, and (5) AL2023's default `python3` being 3.9, too old
      for `strands-agents` (needs `python3.11` explicitly). Also confirmed manual stop/start via
      `aws ec2 stop-instances`/`start-instances` as a cheap way to pause billing between uses —
      relevant beyond the portfolio, since this is the compute target being considered for the
      separate personal-assistant project (see Purpose §5), controlled by a future WhatsApp-
      triggered Lambda (start/stop). See `05-ec2/terraform/README.md` for the full gap-by-gap
      writeup.
- [ ] `06` through `09` and `iam/` — not started.

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
- Building arm64 Docker images on x86 Windows goes through QEMU emulation — if pip/uv falls back
  to compiling anything from source, it can hang 30+ minutes; fix is pre-fetching wheels on the
  host with `uv --only-binary=:all:` and never running `pip install` inside the emulated container
- `bedrock_agentcore` SDK's server binds `127.0.0.1` unless `DOCKER_CONTAINER=1` is set — container
  looks healthy, every external request just gets an empty reply, no error logged
- Each IaC tool needs its own permission gap discovered independently, even for the same
  underlying AWS action — CDK, CloudFormation, and Terraform each triggered distinct AccessDenied
  errors (`cloudformation:DescribeStacks`, `ecr:ListTagsForResource`, etc.) despite deploying the
  exact same resource type, because each tool's client makes different background API calls
- `cmd.exe` treats `<` and `>` as redirection operators even outside code context — typing a
  placeholder like `<VALUE>` literally fails with a file-not-found error, not a syntax error
- AWS's default hard quota of 10 managed policies per IAM user is real and gets hit fast under a
  "one policy per gap" habit — the durable fix is extending an existing related policy via
  `aws iam create-policy-version --set-as-default` (versions cap at 5 per policy, so prune old
  ones eventually), not creating a new standalone policy per fix
- Terraform's `templatefile()` substitutes `${...}` anywhere it appears in the template file,
  including inside what's meant to be a plain comment describing the mechanism — writing
  `${app_py_content}` in a comment sentence spliced real multi-line file content into the middle
  of that line and corrupted the whole rendered script. Never write a variable's literal
  dollar-brace syntax in template prose; describe it in words instead
- `terraform apply`'s default behavior for an `aws_instance` `user_data` change is an in-place
  stop/modify/start, not a replacement — but EC2 user-data only executes once, at first boot, via
  cloud-init. A "successful" apply can silently leave the instance running its old boot state.
  Set `user_data_replace_on_change = true` to force a real replace whenever the boot script itself
  changes
- Amazon Linux 2023's unversioned `python3` package is 3.9 — too old for many current libraries
  (e.g. `strands-agents` needs >=3.10). Install a versioned package (`python3.11`) explicitly
  rather than assuming the default `python3` is recent
- When debugging a headless EC2 instance with no SSH/SSM access, `exec > >(tee /var/log/x.log) 2>&1`
  in the boot script (not a plain `>` redirect) plus `set -x` is what makes the EC2 console's
  "Get system log" actually useful — a plain redirect sends output where the console can't see it

## Working IAM user
`always_learner` (account 486517829337) — deliberately narrow permissions, so every new AWS
feature tends to surface a new permission gap. This friction is itself useful exam/interview
material on the principle of least privilege, so it's not being "fixed" by granting admin access.
