# 04-lambda / zip-deploy

Deploys the calculator agent as a plain AWS Lambda function -- completely outside AgentCore
Runtime. Same underlying model call (Claude via Bedrock), same Strands `Agent` + `calculator`
tool, but a fundamentally different hosting model: Lambda's request/response handler pattern
instead of AgentCore Runtime's always-listening HTTP server.

## Files
- `lambda_function.py` -- the agent, restructured as a plain `lambda_handler(event, context)`
  function. No `BedrockAgentCoreApp`, no `@app.entrypoint`, no server to start.
- `requirements.txt` -- just `strands-agents` + `strands-agents-tools`. No `bedrock-agentcore`
  (that SDK is AgentCore-Runtime-specific) and no `boto3` (Lambda's Python runtime ships with
  it preinstalled).
- `build_lambda_package.py` -- zips the function + dependencies for x86_64 (not arm64 -- see
  notes below), no Docker involved at all.
- `deploy_lambda.py` -- boto3: creates a Lambda-specific execution role, creates/updates the
  function.
- `invoke_lambda_agent.py` -- boto3 `lambda.invoke()`, much simpler than any AgentCore invoke
  script.

## How to run end to end

```bash
cd 04-lambda/zip-deploy
python build_lambda_package.py
python deploy_lambda.py
python invoke_lambda_agent.py "What is 25 * 4?"
```

Safe to rerun all three -- rebuilds the zip fresh, and `deploy_lambda.py` updates the existing
function/role if they already exist rather than failing.

## IAM permissions
`03-classic-bedrock-agent-lambda` already had a Lambda-scoped policy, but it was scoped to
function names matching `CalcAgent*` (PascalCase, that module's naming convention). This
module's function is `calc_agent_lambda` (lowercase, matching every AgentCore Runtime module's
snake_case convention) -- different case, so the existing wildcard didn't cover it. Rather than
rename to fit the old pattern, created a new policy (`AgentCoreLambdaComputeTargetAccess`) scoped
to `arn:aws:lambda:us-east-1:486517829337:function:calc_agent_*` -- matches this project's actual
naming convention going forward, useful for `05` through `09` too.

## Status
- [x] Files written
- [x] `lambda:CreateFunction` AccessDenied hit and fixed (case-mismatch with existing policy)
- [x] Deployed and invoked successfully

## Notes / gotchas
- Skipping a console-based sub-method for this compute target on purpose -- Lambda's console is
  extremely well-trodden territory (day-one AWS tutorial material), unlike AgentCore Runtime's
  console which was genuinely novel and surfaced 4 new IAM gaps. The "navigate a console and
  debug what it needs" skill is already proven on the harder case.
- Per the pacing decision, `04` onward will get 1-2 solid methods each (prove it works + one IaC
  tool) rather than the full 8-method depth `01-agentcore-runtime` got
  -- breadth across compute targets matters more than exhaustive depth on any one now.
