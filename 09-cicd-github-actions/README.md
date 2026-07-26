# 09-cicd-github-actions

First CI/CD pipeline in this repo. Wraps `01-agentcore-runtime/boto3-direct` (the AgentCore
Runtime "boto3-direct" method): push to `main`, and the same agent gets rebuilt and redeployed
automatically, with a smoke-test invoke at the end proving it actually works.

## Where the pieces live
- **The workflow itself:** `.github/workflows/deploy-agentcore.yml` at the **repo root** --
  GitHub only ever looks in `.github/workflows/`, never in a module subfolder, no matter how this
  README is organized.
- **IAM policy documents** (for reference/portfolio purposes): `iam/github-actions-trust-policy.json`
  and `iam/github-actions-permissions-policy.json` in this folder.
- **The deploy script it runs:** `01-agentcore-runtime/boto3-direct/deploy_my_agent.py` --
  unchanged except for one addition: it now writes `agent_arn=<arn>` to `$GITHUB_OUTPUT` when run
  inside a GitHub Actions job, so the next step can read it without re-deploying or hardcoding it.

## CI stage vs CD stage, mapped onto the actual workflow
- **CI:** checkout the repo, set up Python 3.11, `pip install -r requirements.txt`. Nothing
  touches AWS yet -- if a dependency is broken, it fails here and never gets near your account.
- **CD:** `aws-actions/configure-aws-credentials` assumes an AWS IAM role via OIDC (no stored AWS
  keys anywhere in GitHub), then `python deploy_my_agent.py` runs -- which itself calls the
  Bedrock AgentCore Starter Toolkit's `Runtime.launch()`. That one call does the equivalent of a
  full build pipeline: builds the container image (via a CodeBuild project the toolkit manages,
  so no local Docker needed at all, even on GitHub's runner), pushes it to ECR, and creates/updates
  the AgentCore Runtime agent. Then a final smoke-test step invokes the deployed agent with a real
  prompt and asserts it got a response -- the actual proof the deploy worked, not just that the
  API call succeeded.

## One-time setup (do this once, in CloudShell as root/admin -- `always_learner` cannot create
OIDC providers or IAM roles, same restriction hit in every prior module)

1. **Create the GitHub OIDC identity provider** (skip if you already have one -- `aws iam
   create-open-id-connect-provider` errors with `EntityAlreadyExists` harmlessly if so):
   ```bash
   aws iam create-open-id-connect-provider \
     --url https://token.actions.githubusercontent.com \
     --client-id-list sts.amazonaws.com \
     --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
   ```

2. **Create the deploy role**, trusting only this specific repo's `main` branch (see
   `iam/github-actions-trust-policy.json` -- the `sub` condition is what scopes it, so no other
   GitHub repo or branch can assume this role even if it also uses OIDC):
   ```bash
   aws iam create-role \
     --role-name GitHubActionsAgentCoreDeployRole \
     --assume-role-policy-document file://github-actions-trust-policy.json
   ```

3. **Attach the permissions policy** (see `iam/github-actions-permissions-policy.json` --
   ECR, CodeBuild, a scoped S3 prefix, IAM role creation scoped to `*AgentCore*` role names,
   `bedrock-agentcore:*AgentRuntime*` + `*AgentRuntimeEndpoint*` + `*WorkloadIdentity*`, and
   logs):
   ```bash
   aws iam put-role-policy \
     --role-name GitHubActionsAgentCoreDeployRole \
     --policy-name AgentCoreDeployPermissions \
     --policy-document file://github-actions-permissions-policy.json
   ```

4. **Get the role ARN:**
   ```bash
   aws iam get-role --role-name GitHubActionsAgentCoreDeployRole --query "Role.Arn" --output text
   ```

5. **Add it to GitHub** (not a secret -- a role ARN isn't sensitive, so it's a repository
   *variable*, not a secret): repo → Settings → Secrets and variables → Actions → **Variables**
   tab → New repository variable → name `AWS_ROLE_ARN`, value the ARN from step 4.

6. Commit and push (the workflow file, this README, and the `deploy_my_agent.py` change all count
   as a change under the path filters) → watch it run under the repo's **Actions** tab.

## Notes / gotchas
- This is a genuinely different kind of AWS principal than every prior module: `always_learner`
  is a narrow-by-design human IAM user; `GitHubActionsAgentCoreDeployRole` is a role only GitHub's
  OIDC token can assume, scoped to one repo and one branch. Different principal, so its own
  permission gaps are expected -- treat the first few pipeline runs as a normal debugging loop,
  same as `05-ec2`/`06-ecs-fargate`/`07-app-runner` needed.
- The starter toolkit's `Runtime.launch()` is somewhat opaque about exactly which AWS calls it
  makes internally (it uses CodeBuild + S3 behind the scenes rather than a local `docker build`),
  so the permissions policy above is a best-effort starting point, not a guarantee -- expect to
  extend it via `aws iam put-role-policy` again if a specific action comes back AccessDenied in
  the Actions log.
- `permissions: id-token: write` in the workflow YAML is what's actually necessary for OIDC to
  work at all -- without it, `configure-aws-credentials` fails immediately with a missing-token
  error, before anything AWS-side is even attempted.
- `workflow_dispatch: {}` lets you re-run this by hand from the Actions tab (useful for retrying
  after an IAM fix, without needing an empty commit to re-trigger the `push` trigger).
- **GitHub's OIDC "immutable subject claims" rollout (July 15, 2026) broke the trust policy's
  `sub` condition on first attempt.** Any repo created after that date issues OIDC tokens with
  the new default `sub` format `repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH`
  (numeric IDs permanently baked in, to stop a renamed/recycled repo or org name from inheriting
  trust) instead of the older plain-name `repo:OWNER/REPO:ref:refs/heads/BRANCH` format most
  existing docs and examples still show. Our trust policy was written with the old plain-name
  format, so every `AssumeRoleWithWebIdentity` call failed with a generic
  `Not authorized to perform sts:AssumeRoleWithWebIdentity` -- no hint in that error that the
  actual problem was the `sub` string shape, not a missing permission.
  (First guess -- session tagging needing `sts:TagSession` -- was wrong and is not the real
  cause; ruled out by reading `aws-actions/configure-aws-credentials`'s own source, which
  unconditionally strips session tags before the OIDC `AssumeRoleWithWebIdentity` call regardless
  of any setting.)
  Root-caused by adding a temporary workflow step that fetches and decodes the actual OIDC JWT
  (via `ACTIONS_ID_TOKEN_REQUEST_URL`/`ACTIONS_ID_TOKEN_REQUEST_TOKEN`, both auto-populated when
  `permissions: id-token: write` is set) and prints its `aud`/`sub`/`repository` claims directly
  -- comparing the *real* token content against the trust policy, rather than guessing from the
  denial message, is what found this. Fixed by updating the trust policy's `sub` condition to
  the actual `OWNER@ID/REPO@ID` string (find your own repo/owner IDs the same way -- the debug
  step above, or `gh api repos/OWNER/REPO --jq '.id, .owner.id'`).
- **Two more IAM gaps surfaced only after OIDC auth was fixed** -- both hit on the very first
  successful `CreateAgentRuntime` attempt, confirming the toolkit's internal API surface is wider
  than the "obvious" actions:
  1. `bedrock-agentcore:CreateAgentRuntimeEndpoint` AccessDenied -- creating a runtime also
     creates/updates an "endpoint" sub-resource (`DEFAULT` qualifier) in the same call chain.
     Fixed by adding the full `*AgentRuntimeEndpoint*` action set to the permissions policy.
  2. `bedrock-agentcore:CreateWorkloadIdentity` AccessDenied, hit immediately after fixing (1) --
     AgentCore Runtime auto-provisions a workload identity resource per agent. Fixed by adding a
     dedicated `BedrockAgentCoreWorkloadIdentity` statement.
  Both were plain permission additions to the same inline policy on `GitHubActionsAgentCoreDeployRole`
  only -- no other role, policy, or principal in the account was touched by either fix.
- **`ConflictException: Agent 'my_calc_agent' already exists`** -- not an IAM gap. The agent name
  was already deployed once from local testing before this pipeline existed (see
  `01-agentcore-runtime/boto3-direct`'s earlier manual runs). `Runtime.launch()` refuses to
  overwrite an existing agent unless told to. Fixed in `deploy_my_agent.py` by passing
  `auto_update_on_conflict=True` to `launch()` -- this is also what makes the pipeline properly
  idempotent going forward: first run creates the agent, every run after updates it in place,
  which is the actual behavior you want from a "push redeploys the live thing" pipeline.
- **Scope check (nothing else in the account was affected):** every CloudShell command run while
  debugging this module targeted `GitHubActionsAgentCoreDeployRole` by name specifically
  (`create-role`, `update-assume-role-policy`, `put-role-policy`) -- `always_learner`'s own
  policies, every other module's IAM roles, and every previously-deployed agent/resource were
  never referenced or modified. The one deliberately broad grant is the `role/*AgentCore*`
  wildcard for `iam:CreateRole`/`PutRolePolicy`/`AttachRolePolicy`/`PassRole` -- it's scoped to
  role *name pattern*, not to a specific role, so in principle it could touch other AgentCore
  execution roles created by `01-agentcore-runtime`'s other sub-methods (cdk/cloudformation/
  terraform) if their role names also happened to contain "AgentCore". None of those roles were
  actually referenced by any command run in this module -- the wildcard is unused capability, not
  an actual change to anything -- but it's worth tightening to the exact
  `AmazonBedrockAgentCoreSDKRuntime-*`/`AmazonBedrockAgentCoreSDKCodeBuild-*` role names this
  pipeline actually creates if this repo is ever handed to someone else or used beyond a personal
  portfolio.

## Status
- [x] OIDC provider + IAM role created
- [x] `AWS_ROLE_ARN` repo variable set
- [x] First pipeline run succeeded end to end (deploy + smoke test), manually re-verified with a
      direct `invoke_agent.py` call against the live agent
- [x] IAM gaps documented here with real errors
