# manual-container-build

Deploys the calculator agent to AgentCore Runtime as a container image, built and pushed by
hand (no CLI automation, no CodeBuild) -- `docker build`, `docker push` to ECR, then boto3's
`create_agent_runtime` pointed at that image URI. Unlike `starter-toolkit-cli` (where
`agentcore launch` does all of this silently), every step here is explicit.

## Files
- `my_calc_agent.py` — same agent code as every other sub-method
- `requirements.txt` — same three runtime deps (bedrock-agentcore, strands-agents, strands-agents-tools)
- `Dockerfile` — hand-written, heavily commented (see gotchas below for why it looks the way it does)
- `deploy_container.py` — boto3: creates the execution IAM role (with ECR pull permissions),
  calls `create_agent_runtime`/`update_agent_runtime` with `containerConfiguration`
- `invoke_container_agent.py` — boto3 test invocation, same shape as every other invoke script

## How to run end to end

```bash
cd 01-agentcore-runtime/manual-container-build

# 1. Pre-download arm64 wheels on the HOST (not inside Docker -- see gotchas)
uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 --target vendor --only-binary=:all: -r requirements.txt

# 2. Build the image for arm64
docker build --platform linux/arm64 -t calc-agent-manual .

# 3. (Optional) sanity-check it locally before pushing
docker run --platform linux/arm64 --rm -p 8080:8080 -v %USERPROFILE%\.aws:/root/.aws:ro -e AWS_REGION=us-east-1 calc-agent-manual
curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d "{\"prompt\": \"What is 12 * 8?\"}"

# 4. Create the ECR repo (one-time)
aws ecr create-repository --repository-name bedrock-agentcore-calc-agent-manual --region us-east-1

# 5. Authenticate Docker to ECR, tag, push
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 486517829337.dkr.ecr.us-east-1.amazonaws.com
docker tag calc-agent-manual:latest 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-manual:latest
docker push 486517829337.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-calc-agent-manual:latest

# 6. Deploy to AgentCore Runtime
python deploy_container.py

# 7. Test it (deploy_container.py prints the exact command with the real runtime ID)
python invoke_container_agent.py <AGENT_RUNTIME_ID> "What is 25 * 4?"
```

Steps 4-7 are safe to rerun. Step 1-2 need rerunning any time `requirements.txt` or
`my_calc_agent.py` changes; then repeat 2, 5 (retag/push), and 6 (update) to redeploy.

## IAM permissions
No new customer-managed policy needed — reused the existing `BedrockAgentCoreCLIAccess` /
`BedrockAgentCoreFullAccess` grants by matching resource-naming patterns:
- ECR repo named `bedrock-agentcore-calc-agent-manual` — matches the `bedrock-agentcore-*` ECR wildcard.
- Execution role named `BedrockAgentCoreManualContainerExecutionRole` — matches the `*BedrockAgentCore*` IAM role pattern.
- Confirmed working: `ecr:CreateRepository`, role creation, and `create_agent_runtime` all
  succeeded with zero AccessDenied errors on the first real run.

The execution role's inline policy adds ECR pull permissions on top of the baseline
(logs/xray/cloudwatch/bedrock:InvokeModel) that `direct-code-zip`'s role has — a container-based
runtime needs to pull the image at startup, a code-zip runtime doesn't.

## Status
- [x] Dockerfile written and building successfully for linux/arm64
- [x] Image pushed to ECR
- [x] Execution role created with ECR pull permissions
- [x] `create_agent_runtime` with `containerConfiguration` succeeded
- [x] Invoke confirmed working end to end

## Notes / gotchas (the real value of doing this by hand)
- **Compiling under QEMU emulation is extremely slow.** First attempt ran `pip install` inside
  the arm64 container (via QEMU, since we're building on x86 Windows) and it hung for 30+
  minutes without finishing, because at least one dependency lacked a prebuilt arm64 wheel and
  pip fell back to compiling from source under emulation. Fix: resolve dependencies to a local
  `vendor/` folder on the host first using `uv --only-binary=:all:` (same trick as
  `direct-code-zip`), then just `COPY vendor/` into the image — no install step runs inside the
  emulated container at all.
- **`DOCKER_CONTAINER=1` is not just a toolkit convenience.** The auto-generated Dockerfile from
  `starter-toolkit-cli` set this env var with a comment about "host binding logic" — it was
  dropped from the first version of this Dockerfile as an assumed toolkit-only convenience.
  Without it, the container starts and looks healthy, but the `bedrock_agentcore` SDK's server
  binds to `127.0.0.1` (localhost-only) instead of `0.0.0.0`, so every external request gets
  "Empty reply from server." Confirmed by testing: setting `DOCKER_CONTAINER=1` at `docker run`
  time fixed it immediately; it's now baked into the Dockerfile permanently.
- **`docker build` can fail with "transferring dockerfile: 2B" / "no such file or directory"**
  if you're not actually `cd`'d into the folder containing the Dockerfile — Docker will
  silently pick up whatever's at the current working directory's build context. Always confirm
  `cd` before rebuilding.
- **Local `docker run` blocks the terminal with no output** until you hit it with curl from a
  second terminal — same behavior seen testing `starter-toolkit-cli` locally, not a hang.
- Runtime name is `calc_agent_manual_container` — check `list_agents.py` alongside your other
  deployed agents (`calc_agent_direct_zip`, the starter-toolkit one, etc.) to keep track of
  what's running and avoid unnecessary cost.
