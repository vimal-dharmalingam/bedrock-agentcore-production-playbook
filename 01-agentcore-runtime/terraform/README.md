# terraform

Deploys the calculator agent to AgentCore Runtime via `hashicorp/aws`'s native
`aws_bedrockagentcore_agent_runtime` resource -- confirmed via the Terraform Registry docs
before writing any HCL, not assumed. Fully self-contained: Terraform creates its own ECR repo,
own IAM role/policy, and the runtime itself, independent of every other `01-agentcore-runtime`
sub-method.

Note: confirmed NOT in scope for the AIP-C01 exam (see top-level ROADMAP.md) -- built for the
job-search portfolio specifically, not exam prep.

## Files

```
main.tf                 ECR repo + IAM role/policy (via aws_iam_policy_document) + the runtime
variables.tf              Input variables (region, runtime name, repo name, image tag)
outputs.tf                 ecr_repository_url, agent_runtime_id, agent_runtime_arn
my_calc_agent.py            Same agent code as every other sub-method
requirements.txt             Agent's runtime deps
Dockerfile                    Same vendor/ + DOCKER_CONTAINER=1 pattern validated elsewhere
invoke_tf_agent.py             Same invoke pattern as every other module
vendor/                          Pre-fetched arm64 wheels (gitignored)
```

## How to run end to end

Terraform can't build a Docker image any more than CloudFormation could, but this module hits a
genuine chicken-and-egg problem CloudFormation didn't: the ECR repo has to exist before you can
push an image to it, but Terraform has to create that repo. Solved with two separate
`terraform apply` runs.

```bash
cd 01-agentcore-runtime/terraform

# 0. Install Terraform if not already present (separate binary from the CDK CLI)
winget install --id=Hashicorp.Terraform -e
# close/reopen terminal so PATH updates, then confirm:
terraform -version

# 1. Init
terraform init

# 2. First apply -- ECR repo only (need this to exist before we can push to it)
terraform apply -target=aws_ecr_repository.calc_agent
# note the printed ecr_repository_url output, or fetch it again any time:
terraform output ecr_repository_url

# 3. Pre-fetch arm64 wheels
uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 --target vendor --only-binary=:all: -r requirements.txt

# 4. Build for arm64
docker build --platform linux/arm64 -t calc-agent-terraform .

# 5. Authenticate, tag, push (use the REAL value from step 2, not a placeholder)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 486517829337.dkr.ecr.us-east-1.amazonaws.com
docker tag calc-agent-terraform:latest 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-terraform:latest
docker push 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-terraform:latest

# 6. Second apply -- IAM role, policy, and the runtime itself (image now exists to reference)
terraform apply

# 7. Invoke (terraform output shows agent_runtime_id, or check the apply output directly)
python invoke_tf_agent.py <AGENT_RUNTIME_ID> "What is 25 * 4?"
```

To tear down: `terraform destroy` (removes everything Terraform created -- runtime, IAM role/policy,
ECR repo -- in one command, same atomic-teardown benefit `cdk destroy` had).

## What's different from cdk and cloudformation

- **Different engine entirely, not CloudFormation-based at all.** Confirmed by checking:
  `aws_bedrockagentcore_agent_runtime` lives in `hashicorp/aws`, a natively hand-maintained
  Terraform resource -- not the `awscc` provider (which wraps CloudFormation resource types via
  Cloud Control API). Terraform tracks its own state file, independent of any CloudFormation stack.
- **IAM written via `aws_iam_policy_document` data sources**, not raw JSON -- same content as
  every other module's execution policy, expressed in HCL's own idiom.
- **The chicken-and-egg ECR problem is unique to this module.** CDK sidestepped it by building the
  image itself (`fromAsset`). CloudFormation sidestepped it by just taking an image URI as a
  parameter, never managing the ECR repo as a resource at all. Terraform does manage the repo as
  a resource, which is what forces the two-phase-apply pattern -- a genuinely common real-world
  Terraform shape whenever infrastructure needs to reference an artifact that doesn't exist yet.

## IAM permissions

One new gap, same CloudShell-as-root pattern as every previous fix:

- **`ecr:ListTagsForResource` AccessDenied**, hit immediately after the ECR repo was actually
  created successfully -- Terraform's AWS provider reads back tags for state consistency right
  after creating a resource, a background call the earlier `BedrockAgentCoreCLIAccess` policy's
  `ecr:CreateRepository` grant didn't cover. Fixed by creating `AgentCoreTerraformEcrAccess`,
  scoped to `bedrock-agentcore-*` repos, covering the full repo lifecycle (`DescribeRepositories`,
  `ListTagsForResource`, `TagResource`, `UntagResource`, `DeleteRepository`) in one pass rather
  than discovering each missing action one at a time.

## Status
- [x] Confirmed `aws_bedrockagentcore_agent_runtime` exists in `hashicorp/aws` before writing HCL
- [x] `main.tf`/`variables.tf`/`outputs.tf` written -- self-contained ECR repo, IAM, runtime
- [x] Two-phase `terraform apply` completed (repo, then image push, then IAM+runtime)
- [x] `ecr:ListTagsForResource` AccessDenied hit and fixed
- [x] Invoke confirmed working end to end

## Notes / gotchas
- **`winget install --id=HashiCorp.Terraform` returned "No package found"** -- the correct ID's
  capitalization is `Hashicorp.Terraform`, not `HashiCorp.Terraform`. Run `winget search terraform`
  if this happens again to confirm the exact current ID.
- **`docker push <ECR_REPO_URL>:latest` failed with "The system cannot find the file specified"**
  when the angle-bracket placeholder was typed literally -- `<` and `>` are redirection operators
  in cmd.exe, not just visual placeholder markers. Always substitute the real value from
  `terraform output ecr_repository_url` first.
- **`data.aws_region.current.name` is deprecated** (provider warning, not an error) in favor of a
  `region` attribute -- left as-is since it still works and the warning is cosmetic, but worth
  fixing to `data.aws_region.current.region` if the provider ever removes the old attribute.
- Runtime name is `calc_agent_terraform` -- check `list_agents.py` alongside every other deployed
  agent from this project.
