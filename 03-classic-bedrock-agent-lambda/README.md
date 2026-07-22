# 03 - Classic Bedrock Agents + Lambda Action Group

Different architecture from `01-agentcore-runtime` and `02-agentcore-cli` — this uses
**Amazon Bedrock Agents** (a separate, older AWS feature, not AgentCore at all). AWS manages
the reasoning/orchestration loop; you only supply a Lambda function as the "tool" the agent
calls out to. No Strands framework, no container, no AgentCore Runtime involved.

## Architecture
```
User prompt → Bedrock Agent (model + instructions)
                  → decides it needs the calculator tool
                  → invokes your Lambda function (the Action Group)
                  → Lambda returns the result
                  → Bedrock Agent replies to the user
```

## Folder layout
```
03-classic-bedrock-agent-lambda/
├── README.md              # this file — workflow + rerun steps, kept up to date
├── lambda/
│   └── calculator_lambda.py   # the Lambda function code
├── schema/
│   └── calculator-schema.json # OpenAPI schema describing the Lambda's function to Bedrock
├── iam/
│   └── bedrock-agent-lambda-policy.json  # permissions granted to always_learner for this module
└── scripts/
    ├── create_agent.py    # boto3: create the Bedrock Agent + action group
    └── test_agent.py      # boto3: invoke_agent, end-to-end test
```

## Workflow (do in order)

1. **Grant IAM permissions** — `always_learner` needs Bedrock Agent management permissions +
   Lambda create/manage permissions, separate from everything granted in modules 01/02.
2. **Write and deploy the Lambda function** (`lambda/calculator_lambda.py`) — plain Python,
   no Strands, just a handler that does arithmetic and returns Bedrock's expected response shape.
3. **Write the OpenAPI schema** (`schema/calculator-schema.json`) describing the Lambda's
   function so the Bedrock Agent knows it exists, what it's called, and what inputs it takes.
4. **Create the Bedrock Agent** — model, instructions, and an Action Group wiring the schema
   to the Lambda. Also needs a resource-based policy on the Lambda allowing
   `bedrock.amazonaws.com` to invoke it.
5. **Test end to end** — first via the Bedrock console's built-in test window, then via
   `scripts/test_agent.py` (boto3 `invoke_agent`) for programmatic verification.

## How to rerun from scratch

### 1. IAM permissions (one-time per AWS account)
Policy JSON lives at `iam/bedrock-agent-lambda-policy.json`. Create + attach it via CloudShell,
logged in as root (this account's `always_learner` IAM user is deliberately narrow-scoped, so
creating new customer-managed policies needs to be done as root/admin — same pattern used in
modules 01/02):
```bash
# paste the contents of iam/bedrock-agent-lambda-policy.json into a file in CloudShell, e.g.:
cat > bedrock-agent-lambda-policy.json << 'EOF'
<paste policy JSON here>
EOF

aws iam create-policy --policy-name BedrockAgentLambdaAccess --policy-document file://bedrock-agent-lambda-policy.json
aws iam attach-user-policy --user-name always_learner --policy-arn arn:aws:iam::486517829337:policy/BedrockAgentLambdaAccess
aws iam list-attached-user-policies --user-name always_learner
```

### 2-3. Deploy Lambda + create the Bedrock Agent + action group (one script, idempotent)
`scripts/create_agent.py` does everything in order: creates the Lambda execution role, deploys
`lambda/calculator_lambda.py`, creates the Bedrock Agent's service role, creates the agent,
creates the action group from `schema/calculator-schema.json`, grants Bedrock permission to
invoke the Lambda, then calls `prepare_agent`. Safe to rerun — skips anything that already
exists, updates Lambda code if the function is already there.
```bash
cd 03-classic-bedrock-agent-lambda/scripts
python create_agent.py
```
Prints the `agentId` at the end — needed for testing.

### 4. Test
Bedrock console: AWS Console → Bedrock → Agents → `ClassicCalculatorAgent` → Test window
(right-hand panel) → type a prompt like "What is 25 * 4?".

boto3, from the same `scripts/` folder:
```bash
python test_agent.py AGENT_ID "What is 25 * 4?"
```
(uses the built-in `TSTALIASID` test alias — no need to create a formal alias just to test)

## Status
- [x] IAM permissions granted (`BedrockAgentLambdaAccess` attached to `always_learner`)
- [x] Lambda function written (`lambda/calculator_lambda.py`) — uses a restricted `ast`-based
      evaluator instead of raw `eval()`
- [x] Function schema written (`schema/calculator-schema.json`)
- [x] `create_agent.py` / `test_agent.py` written as the programmatic (boto3) path — not yet
      run; agent was built via the Bedrock console instead, for step-by-step learning
- [x] Lambda function created via Lambda console, agent + action group created via Bedrock
      console (agent name `ClassicCalculatorAgent`, agent ID `HLDXKUB71Z`)
- [x] Tested via Bedrock console — working
- [ ] Tested via boto3 (`test_agent.py`) — run `python test_agent.py HLDXKUB71Z "What is 25 * 4?"`
      from `scripts/` to verify the programmatic path too

## Console vs. script — what actually happened
Built this one manually via the AWS Console rather than running `create_agent.py`, to learn each
concept step by step (Lambda creation, agent creation, action group wiring) rather than have a
script do it all at once. `create_agent.py`/`test_agent.py` are still in the repo as the
"here's how you'd automate this" companion — worth running them against a *second*, differently-
named agent later to prove the automation path independently, rather than assuming it works
just because the manual path did.

## Platform status (important context, added after building this)
AWS renamed this service "Bedrock Agents Classic" and put it into maintenance mode effective
**July 30, 2026**. Existing agents/APIs keep working indefinitely (no end-of-life date), but
accounts with no prior `CreateAgent` usage are blocked from creating new agents after that date.
This account (486517829337) is allowlisted since the agent in this module was created before
the cutoff. Model catalog is frozen as of the cutoff date; no new features planned.

AWS's recommended path forward is **Amazon Bedrock AgentCore**, with two options:
1. **AgentCore managed harness** — config-based (`agentcore add harness`), the closer analog to
   what this module built, but running on AgentCore's infrastructure (memory, gateway,
   observability included). Not yet explored in this repo — worth its own future module,
   conceptually the "declarative" middle ground between this Classic approach and the
   fully-custom-code Strands approach used in `01-agentcore-runtime`/`02-agentcore-cli`.
2. **Code-defined agents on AgentCore** — what modules 01/02 already are.

## Notes / gotchas
- The Bedrock console does **not** automatically grant Bedrock permission to invoke the Lambda
  when you save the action group (contrary to what you might assume) — had to add it manually
  via `aws lambda add-permission` with `--principal bedrock.amazonaws.com` and a `--source-arn`
  scoped to the specific agent ARN.
- Classic mistake worth documenting: ran `add-permission` once with the literal placeholder text
  `AGENT_ID` still in the `--source-arn` instead of the real agent ID. It succeeded (syntactically
  valid ARN-shaped string), silently creating a permission that could never actually match a real
  Bedrock request. Diagnosed via `aws lambda get-policy` showing the literal wrong value, fixed
  with `remove-permission` + `add-permission` again with the correct ID. Lesson: always verify
  with `get-policy` after granting resource-based permissions, don't assume success from lack of
  an error.
- `add-permission` fails with `ResourceConflictException` if a statement with the same
  `--statement-id` already exists — even if its content is wrong. It won't overwrite; you must
  `remove-permission` first.
