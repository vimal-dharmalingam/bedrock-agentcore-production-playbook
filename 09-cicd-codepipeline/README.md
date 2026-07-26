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

(Document actual AccessDenied errors and fixes here as they're hit — first time
`codepipeline:*`, `codebuild:CreateProject` for a top-level pipeline project, and
`codestar-connections:*` have been touched in this project via CloudFormation, so treat
everything as a new gap until proven otherwise, same caution every prior module needed.)

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
