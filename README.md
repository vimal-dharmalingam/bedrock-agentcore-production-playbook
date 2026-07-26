# Amazon Bedrock AgentCore — Production Deployment Playbook

One simple calculator agent (built with the [Strands Agents](https://strandsagents.com) framework),
deployed to AWS the same way a production team would evaluate deployment options: side by side,
via every mechanism available, so the tradeoffs are directly comparable rather than theoretical.

Built while learning Amazon Bedrock AgentCore in depth, as a hands-on comparison of deployment
mechanisms rather than a single "getting started" walkthrough. Where relevant, module READMEs
also note how a given service maps to the AWS Certified Generative AI Developer – Professional
exam guide, as a technical cross-reference rather than the point of the repo.

## What's here

```
01-agentcore-runtime/          AgentCore Runtime, deployed 4 different ways so far:
  starter-toolkit-cli/         agentcore CLI (deprecated toolkit) -- fully automated build+deploy
  boto3-direct/                starter toolkit's Python API, scripted rather than CLI-driven
  direct-code-zip/             no container at all -- code zip uploaded straight to S3
  manual-container-build/      hand-written Dockerfile, manual docker build/push/ECR/deploy
  cdk/ terraform/ cloudformation/   -- IaC versions, in progress
  scripts/                     list/delete agent runtime utilities (boto3)

02-agentcore-cli/              AWS's newer @aws/agentcore CLI -- generates and deploys via CDK

03-classic-bedrock-agent-lambda/   The OLDER "Bedrock Agents" service (separate from AgentCore),
                                    action-group Lambda -- kept for architectural comparison,
                                    see its README for platform status (entering maintenance
                                    mode July 2026)
```

Each module folder is self-contained and runnable on its own -- the same `my_calc_agent.py` is
deliberately duplicated across folders rather than shared, so every deployment method can be
tried independently without cross-folder dependencies.

**Every module's README documents the exact commands to rerun it from scratch, plus the real
errors hit along the way and how they were fixed.** Treat this as a debugging log as much as a
working repo -- most of the actual learning happened in the IAM permission errors, the ARM64
build quirks, and the platform-specific gotchas, not in the happy path.

See [ROADMAP.md](./ROADMAP.md) for full status, architecture notes, and how this maps to the
AWS Certified Generative AI Developer – Professional exam's scope.

## Why AgentCore, and why so many deployment paths

Amazon Bedrock AgentCore is AWS's managed runtime for hosting agentic applications built with
any framework (Strands, LangGraph, CrewAI, etc.), separate from the older, more constrained
"Bedrock Agents" service. Deploying the *same* agent multiple ways surfaces real tradeoffs that
don't show up from reading docs alone: CLI automation vs. raw boto3 for production control,
container images vs. code-zip packaging, and imperative one-shot API calls vs. declarative
Infrastructure-as-Code with tracked state.

## AWS environment

Deliberately run under a narrow-permission IAM user rather than an admin account, so every new
AWS feature tends to surface a real permission gap -- treated as portfolio/interview material on
least-privilege design, not something to route around with broader access. Details in
[ROADMAP.md](./ROADMAP.md#working-iam-user).
