# cloudformation

Hand-written, raw CloudFormation template deploying the calculator agent to AgentCore Runtime.
No compiler, no construct library -- this is the exact resource shape `cdk synth` produced in
the `cdk/` module, written directly instead of generated. Fully self-contained: builds its own
Docker image, pushes to its own dedicated ECR repo, no dependency on any other
`01-agentcore-runtime` sub-method.

## Files

```
template.yaml          IAM role + policy + AWS::BedrockAgentCore::Runtime, hand-written
my_calc_agent.py         Same agent code as every other sub-method
requirements.txt         Agent's runtime deps (bedrock-agentcore, strands-agents, strands-agents-tools)
Dockerfile                Same vendor/ + DOCKER_CONTAINER=1 pattern validated in manual-container-build
invoke_cfn_agent.py        Same invoke pattern as every other module
vendor/                     Pre-fetched arm64 wheels (gitignored, regenerate with the command below)
```

## How to run end to end

```bash
cd 01-agentcore-runtime/cloudformation

# 1. Pre-fetch arm64 wheels (avoids the QEMU compile-from-source hang)
uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 --target vendor --only-binary=:all: -r requirements.txt

# 2. Build for arm64
docker build --platform linux/arm64 -t calc-agent-cloudformation .

# 3. Create this module's own ECR repo (one-time)
aws ecr create-repository --repository-name bedrock-agentcore-calc-agent-cloudformation --region us-east-1

# 4. Authenticate, tag, push
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 486517829337.dkr.ecr.us-east-1.amazonaws.com
docker tag calc-agent-cloudformation:latest 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-cloudformation:latest
docker push 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-cloudformation:latest

# 5. Deploy the template -- one CLI command, no Python wrapper script needed. CloudFormation's
#    engine itself handles create-vs-update idempotency.
aws cloudformation deploy --template-file template.yaml --stack-name CalcAgentCfnStack --capabilities CAPABILITY_NAMED_IAM

# 6. Get the runtime ID from the stack outputs
aws cloudformation describe-stacks --stack-name CalcAgentCfnStack --query "Stacks[0].Outputs" --output table

# 7. Invoke
python invoke_cfn_agent.py <AGENT_RUNTIME_ID> "What is 25 * 4?"
```

Safe to rerun step 5 any time after a template change -- CloudFormation diffs and only updates
what's different. To tear down: `aws cloudformation delete-stack --stack-name CalcAgentCfnStack`.

## What's different from cdk

- **No compiler.** `template.yaml` is the exact resource shape CDK's `cdk synth` produced in the
  `cdk/` module -- here it's written directly by hand instead of generated from Python.
- **No auto-generated IAM.** CDK's `Runtime` L2 construct wrote most of the execution role policy
  automatically. Every statement here (logs, X-Ray, CloudWatch, ECR pull, `bedrock:InvokeModel`)
  is explicit -- same content as `manual-container-build`'s hand-written Python policy dict,
  translated into a CloudFormation resource.
- **CloudFormation cannot build Docker images.** CDK's `fromAsset()` ran `docker build` as part
  of `cdk deploy`. This template only *references* an image URI -- the build/push (steps 1-4
  above) happens separately, by hand, before the template is ever deployed. This is the clearest
  demonstration in the whole repo of "CloudFormation orchestrates, it doesn't construct."
- **No Python deploy script.** Every other module has a `deploy_*.py` calling boto3.
  `aws cloudformation deploy` reads the template directly -- CloudFormation's own engine handles
  the create-vs-update decision, unlike our own scripts which had to check
  `find_existing_agent_runtime()` by hand.

## IAM permissions

Two gaps hit, both fixed via CloudShell as root, following the same pattern as every earlier
module:

1. **`cloudformation:DescribeStacks` AccessDenied** on the first `aws cloudformation deploy`.
   The existing `AgentCoreCdkDeployAccess` policy (created during `02-agentcore-cli`) was scoped
   to different stack name patterns. Fixed by creating `AgentCoreCloudFormationDeployAccess`,
   scoped to `arn:aws:cloudformation:us-east-1:486517829337:stack/CalcAgent*/*` -- covers this
   stack and any future `CalcAgent*`-named stack, not a blanket CloudFormation grant.
2. **Anticipated and avoided before hitting it:** the `ExecutionRole` resource has an explicit
   `RoleName: BedrockAgentCoreCfnExecutionRole` in the template, matching the `*BedrockAgentCore*`
   pattern already granted by earlier IAM-management policies. Without this, CloudFormation would
   have auto-generated a name like `CalcAgentCfnStack-ExecutionRole-XXXXX` that wouldn't match,
   causing a second AccessDenied immediately after fixing the first.

## Status
- [x] `template.yaml` written -- self-contained, own image, own ECR repo, own execution role
- [x] Docker image built and pushed to `bedrock-agentcore-calc-agent-cloudformation`
- [x] `cloudformation:DescribeStacks` AccessDenied hit and fixed (new scoped policy)
- [x] Stack deployed successfully (`CREATE_COMPLETE`)
- [x] Invoke confirmed working end to end

## Notes / gotchas
- Started this module pointing at `manual-container-build`'s already-pushed image (fastest path,
  no rebuild) -- switched to a fully self-contained version (own Dockerfile, own ECR repo) so
  this folder has zero dependency on any other `01-agentcore-runtime` sub-method and can run
  standalone even if every other folder were deleted. Worth the extra build/push steps.
- Runtime name is `calc_agent_cloudformation` -- check `list_agents.py` alongside the others.
