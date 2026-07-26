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
   `bedrock-agentcore:*AgentRuntime*`, and logs):
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
- **`aws-actions/configure-aws-credentials@v4` tags the assumed role session by default** (repo,
  workflow, actor, etc. -- visible in the debug log as `N role session tags are being used`).
  That requires the trust policy to grant `sts:TagSession` in addition to
  `sts:AssumeRoleWithWebIdentity`. Ours only grants the latter, so every attempt failed with
  `Not authorized to perform sts:AssumeRoleWithWebIdentity` -- a misleading error, since the
  actual missing permission is `TagSession`, not `AssumeRoleWithWebIdentity` itself. Fixed by
  setting `role-skip-session-tagging: true` on the action instead of widening the trust policy.
  Root-caused by re-running the workflow with the `ACTIONS_STEP_DEBUG=true` repo secret set,
  which prints the actual OIDC claims and session-tag count before the AssumeRole call --
  the standard (non-debug) log only shows the generic denial, not what was actually attempted.

## Status
- [x] OIDC provider + IAM role created
- [x] `AWS_ROLE_ARN` repo variable set
- [ ] First pipeline run succeeded end to end (deploy + smoke test)
- [x] IAM gaps (if any) documented here with real errors
