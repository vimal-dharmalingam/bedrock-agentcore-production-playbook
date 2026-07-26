# 09-cicd-codepipeline

The AWS-native sibling of `09-cicd-github-actions`: same idea (push to `main` redeploys the live
agent), same deploy target (`01-agentcore-runtime/boto3-direct`, byte-for-byte unchanged), but
orchestrated by CodePipeline + CodeBuild instead of GitHub Actions. Built specifically because
CodePipeline and CodeBuild are named explicitly on the AWS Certified Generative AI Developer -
Professional exam guide (Task 2.3.5) — GitHub Actions isn't an AWS service and won't appear on it.

## How this compares to 09-cicd-github-actions

Both pipelines do exactly the same three things — checkout, deploy via
`python deploy_my_agent.py`, smoke-test invoke — but AWS splits "orchestration" and "compute"
into two separate services where GitHub Actions collapses them into one workflow file:

- **CodePipeline** is the orchestrator only. It never runs a shell command itself — its whole
  job is moving an artifact through stages (Source → Build) and handing off to CodeBuild.
- **CodeBuild** is the actual compute. `buildspec.yml` in this folder is functionally the same
  as `deploy-agentcore.yml`'s steps, just AWS-native syntax instead of GitHub Actions YAML.

Authentication is also architecturally different. GitHub Actions used OIDC (a GitHub-issued JWT
traded for temporary AWS credentials, no long-lived keys anywhere). CodePipeline instead uses a
**CodeStar Connection** — a persistent, account-level trust relationship between AWS and your
GitHub account/repo, authorized once through the console (OAuth), not re-established per run.

## The one step that can't be scripted

`AWS::CodeStarConnections::Connection` can be *created* via CloudFormation, but it comes up in
`PENDING` status — AWS deliberately does not allow the GitHub OAuth handshake itself to happen
through the API, only through the console. After deploying `template.yaml`, you must:

1. Go to the AWS Console → CodePipeline → Settings → **Connections** (or search "Developer Tools
   Connections")
2. Find `CalcAgentGitHubConnection`, status `Pending`
3. Click **Update pending connection** → authorize against your GitHub account/org → select this
   repo
4. Status flips to `Available` — only then can the pipeline actually run

## Files
- `template.yaml` — `GitHubConnection`, `ArtifactBucket`, `CodeBuildServiceRole`,
  `CodePipelineServiceRole`, `CodeBuildProject`, `Pipeline` (Source + BuildAndDeploy stages)
- `buildspec.yml` — what CodeBuild actually runs. Notably does **not** need Docker-in-Docker /
  privileged mode, because it never builds the container image itself — `deploy_my_agent.py`'s
  `Runtime.launch()` spins up a *separate*, nested CodeBuild project internally to build the
  actual ARM64 image. This project is CodeBuild triggering CodeBuild, one level removed.
- `iam/cfn-codepipeline-policy-merged.json` — extends `AgentCoreCloudFormationDeployAccess`
  (not a new policy, same discipline as every other module) with `codepipeline:*`,
  `codebuild:*` (project management), `codestar-connections:*`, the artifact bucket, and
  `iam:CreateRole`/`PassRole` scoped to `role/CalcAgent*` for the two service roles this stack
  creates.

## How to run end to end

```bash
cd 09-cicd-codepipeline
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name CalcAgentCodePipelineStack \
  --capabilities CAPABILITY_NAMED_IAM
```

Then complete the manual connection-authorization step above. Once `GitHubConnection` shows
`Available`, either push a change under `01-agentcore-runtime/boto3-direct/` or trigger the
pipeline manually:

```bash
aws codepipeline start-pipeline-execution --name CalcAgentDeployPipeline
```

Watch progress:
```bash
aws codepipeline get-pipeline-state --name CalcAgentDeployPipeline
```

To tear down: `aws cloudformation delete-stack --stack-name CalcAgentCodePipelineStack` (note
the `ArtifactBucket` may need emptying first if it has objects — S3 buckets with content block
stack deletion).

## IAM permissions

First time `codepipeline:*`, `codebuild:CreateProject` for a top-level pipeline project, and
`codestar-connections:*` were touched via CloudFormation in this project. Three gaps hit, all
fixed by extending `AgentCoreCloudFormationDeployAccess` (not a new policy):

1. **`codestar-connections:PassConnection` AccessDenied** on the `AWS::CodePipeline::Pipeline`
   resource creation — since CloudFormation runs this under the caller's own credentials (same
   pattern as `07-app-runner`), `always_learner` needed this action scoped to the connection ARN,
   directly analogous to how `iam:PassRole` works for handing a role to a service.
2. **`codepipeline:StartPipelineExecution` AccessDenied** when manually triggering the pipeline
   after deploy — the original policy only covered pipeline *management* (create/update/delete),
   not actually running it. Added `StartPipelineExecution`, `GetPipelineExecution`, and
   `ListPipelineExecutions`.
3. **5-versions-per-policy cap hit again** on `AgentCoreCloudFormationDeployAccess` while adding
   fix #2 — same recurring pattern as `AgentCoreConsoleEc2ReadAccess` earlier in the project.
   Deleted the oldest version (`v1`) before creating the new one.

## A non-IAM bug: CodeBuild working directory persists across phases, not just within one

Not a permission gap — a real logic bug in the original `buildspec.yml`. Each phase (`install`,
`build`, `post_build`) had its own `cd 01-agentcore-runtime/boto3-direct` command, on the
assumption that CodeBuild resets to `$CODEBUILD_SRC_DIR` at the start of every phase. It doesn't:
the shell's working directory carries over across *all* phases of a single build, not just
between commands within one phase. So `install`'s `cd` correctly landed in
`.../01-agentcore-runtime/boto3-direct`, but `build`'s `cd 01-agentcore-runtime/boto3-direct`
then tried to descend into a *nested* subdirectory of that same name relative to where the shell
already was — which doesn't exist, failing with a plain `No such file or directory`. Root-caused
via CloudWatch Logs (`aws logs get-log-events`, since `aws logs tail`/`FilterLogEvents` wasn't
granted to `always_learner`) showing the exact failing command and phase. Fixed by anchoring
every `cd` to the absolute `$CODEBUILD_SRC_DIR` instead of a bare relative path, which is correct
regardless of what directory a previous phase left the shell in.

**Separate Windows-only wrinkle hit while debugging this**: `aws logs get-log-events --output text`
(and even `--output json`) crashed with `'charmap' codec can't encode characters` on this Windows
terminal — pip's progress-bar output contains characters the console's default codepage can't
render, even after `chcp 65001` and `set PYTHONIOENCODING=utf-8`. Worked around by calling
`boto3`'s `get_log_events` directly via a one-line `python -c` script and writing the result to a
file with explicit `encoding="utf-8"`, sidestepping the AWS CLI's own output formatter entirely.

## Notes / gotchas
- Stack name deliberately `CalcAgentCodePipelineStack`, matching the already-granted
  `stack/CalcAgent*/*` pattern in `AgentCoreCloudFormationDeployAccess` — same lesson from
  `04-lambda/cloudformation` and `07-app-runner/cloudformation`.
- `CodeBuildServiceRole`'s permissions are almost identical to `GitHubActionsAgentCoreDeployRole`
  from the GitHub Actions module — same underlying `Runtime.launch()` call graph needs the same
  AWS actions regardless of which CI/CD tool is driving it. Worth pointing out in an interview:
  the *deploy logic* doesn't change across CI/CD tools, only the orchestration layer around it.
- `CodePipelineServiceRole` is deliberately much narrower than `CodeBuildServiceRole` — it only
  moves artifacts and starts builds, never touches ECR/bedrock-agentcore/IAM directly. Splitting
  "orchestration" and "compute" into separate services also means splitting their IAM roles
  cleanly along the same line.
- `deploy_my_agent.py` was extended (in `09-cicd-github-actions`) to write `agent_arn.txt`
  locally in addition to `$GITHUB_OUTPUT` — that's what makes the exact same script work
  unmodified under both CI/CD tools; CodeBuild's `buildspec.yml` just reads the plain file since
  it has no equivalent of GitHub Actions' step-output mechanism.

## Status
- [ ] Stack deployed
- [ ] GitHub connection authorized (console step)
- [ ] First pipeline run succeeded end to end (deploy + smoke test)
- [ ] IAM gaps (if any) documented above with real errors
