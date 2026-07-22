# 02 - AgentCore CLI (npm-based, CDK-backed)

Same calculator agent as `01-agentcore-runtime/`, redeployed using the newer
`@aws/agentcore` CLI (successor to the deprecated Python starter toolkit).

Key differences from `01-agentcore-runtime/starter-toolkit-cli/`:
- Distributed via npm, not pip
- Deploys through a generated AWS CDK app (real CloudFormation stack, state-tracked)
- Supports more frameworks (LangGraph, LangChain, Google ADK, OpenAI Agents) beyond Strands
- Adds local dev server with hot-reload, observability, and eval tooling out of the box

## Status
- [x] CLI installed and prerequisites verified (Node, uv, CDK, `cdk bootstrap` via CloudShell as root)
- [x] Project scaffolded (`agentcore create --name CalcAgentCli --framework Strands --protocol HTTP --model-provider Bedrock --memory none`)
- [x] Calculator tool ported into generated `main.py` (kept scaffold's `add_numbers` custom tool + added Strands' built-in `calculator`)
- [x] Tested locally (`agentcore dev`) — confirmed working via web inspector
- [x] Deployed (`agentcore deploy`) — real CDK/CloudFormation deploy to AgentCore Runtime succeeded
- [x] Verified with `agentcore invoke` — working
- [ ] Screenshot/log of `agentcore status` saved for portfolio evidence

## Notes
- `cdk bootstrap` needs broad IAM permissions `always_learner` doesn't have — ran it once via
  AWS CloudShell logged in as root instead (bootstrapping is a one-time, account-wide, admin-level
  step, not something a regular dev IAM user needs ongoing access to).
- New CLI requires `uv` for Python dependency management (separate from the project's own venv/pip setup).
- After editing `pyproject.toml` to add a new dependency, the existing `.venv` doesn't auto-update —
  had to manually run `uv sync` inside `app/CalcAgentCli/`.
- Windows console hit `UnicodeEncodeError` when the model's response included emoji, because the
  default terminal codepage isn't UTF-8. Fixed with `PYTHONIOENCODING=utf-8` (set as a permanent
  system environment variable to avoid re-setting it per terminal session).
- Both `bedrock-agentcore-starter-toolkit` (old, pip) and `@aws/agentcore` (new, npm) register the
  same `agentcore` command — uninstalled the old one to avoid collisions.
