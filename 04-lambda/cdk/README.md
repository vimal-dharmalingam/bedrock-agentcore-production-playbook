# 04-lambda / cdk

Same calculator agent as `zip-deploy/`, deployed via Python CDK instead of raw boto3. Much
simpler than `01-agentcore-runtime/cdk`: no arm64 requirement, no container-vs-code-zip
artifact choice, no chicken-and-egg ECR problem -- Lambda's `Function` L2 construct is one of
the oldest, most mature constructs in `aws-cdk-lib`.

## Files
- `lambda_src/lambda_function.py`, `lambda_src/requirements.txt` -- source, tracked in git
- `build_lambda_asset.py` -- prefetches x86_64 wheels into `build/` (gitignored) alongside a
  copy of the handler, so CDK has a ready-to-zip folder. Same `uv --only-binary=:all:` trick as
  every container module, just x86_64 instead of arm64 -- no Docker needed at all here.
- `app.py` / `cdk_stack.py` / `cdk.json` / `requirements.txt` (CDK tool deps) -- standard CDK
  app layout, same shape as `01-agentcore-runtime/cdk`.
- `invoke_lambda_agent.py` -- same `lambda.invoke()` pattern as `zip-deploy/`.

## How to run end to end

```bash
cd 04-lambda/cdk
python build_lambda_asset.py
pip install -r requirements.txt
cdk synth
cdk deploy
python invoke_lambda_agent.py "What is 25 * 4?"
```

## What's different from zip-deploy

- CDK's `Function` L2 construct auto-creates the execution role with basic Lambda logging
  permissions -- same one gap as every CDK module so far: `bedrock:InvokeModel` still isn't
  auto-granted, added explicitly via `function.add_to_role_policy(...)`.
- No new `always_learner` IAM gaps hit deploying this -- `cdk deploy` operates through the
  CDK bootstrap's own execution roles (assumed via `sts:AssumeRole`, already granted back in
  `02-agentcore-cli`), so creating a brand-new IAM role inside this stack didn't need any new
  direct grant the way scripting it by hand always does.

## Status
- [x] Deployed and invoked successfully, zero new IAM gaps

## Notes / gotchas
- Confirms the general pattern from all of `01-agentcore-runtime`: CDK deploys are cheaper on
  IAM permissions than raw boto3 or CloudFormation, because the actual privileged work happens
  under the bootstrap's own roles, not the calling user's identity.
