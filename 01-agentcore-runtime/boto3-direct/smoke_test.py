"""
Smoke-test the deployed calculator agent -- reads AGENT_ARN from the environment and sends one
real prompt, asserting a response comes back. Used by both CI/CD pipelines (09-cicd-github-actions
and 09-cicd-codepipeline) as the final step proving a deploy actually works, not just that the
deploy API calls succeeded.

Extracted into its own file rather than an inline `python -c "..."` one-liner in either
workflow YAML, after 09-cicd-codepipeline's buildspec.yml hit a real bug: YAML's `>` (folded)
block scalar collapses newlines into spaces, silently turning multi-line Python into one invalid
line. A plain script file sidesteps that whole class of YAML block-scalar fragility.

Usage:
    AGENT_ARN=<arn> python smoke_test.py
"""
import os
import sys

from invoke_agent import invoke_agent


def main():
    agent_arn = os.environ.get("AGENT_ARN")
    if not agent_arn:
        print("Error: AGENT_ARN environment variable is required.")
        sys.exit(1)

    prompt = "What is 25 * 4?"
    print(f"Smoke testing {agent_arn}")
    result, _ = invoke_agent(agent_arn, prompt)
    print("Smoke test response:", result)

    if result is None:
        print("Smoke test FAILED: agent did not return a response")
        sys.exit(1)

    print("Smoke test PASSED")


if __name__ == "__main__":
    main()
