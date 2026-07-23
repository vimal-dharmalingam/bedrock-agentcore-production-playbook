# console — not started

Plan: deploy the calculator agent to AgentCore Runtime purely through the AWS Management
Console — no CLI, no script, no IaC template. The one sub-method that's pure click-through,
matching how `03-classic-bedrock-agent-lambda` was deliberately built by hand first before
automating anything.

## Rough plan for tomorrow
1. Build and push a container image to ECR by hand first (reuse the exact same steps as
   `manual-container-build` -- the console still needs a real image to point at, it doesn't
   build one for you either).
2. AWS Console → Amazon Bedrock → AgentCore → Runtime → Create.
3. Walk through every field by hand: name, container image (browse ECR), execution role
   (create new vs. select existing -- try reusing `BedrockAgentCoreCfnExecutionRole` or similar
   to see whether the console enforces any naming/trust-policy assumptions the CLI/IaC paths
   didn't surface), network mode, protocol.
4. Test invoke directly from the console's built-in test panel, if one exists, before falling
   back to `invoke_console_agent.py`.
5. Document every screen/decision point in this README -- this module's value is the click path
   itself, not code, so the README needs to be more narrative/annotated than the others.
6. Compare against every other method's execution role policy once created -- does the console
   auto-generate one differently from CDK's L2 construct or from what we wrote by hand?

## Status
- [ ] Not started -- planned for next session
