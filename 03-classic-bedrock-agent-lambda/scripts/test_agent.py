"""
Invokes the deployed classic Bedrock Agent end to end.

Usage:
    python test_agent.py AGENT_ID "What is 25 * 4?"

Uses the built-in TSTALIASID test alias, which always points at the agent's DRAFT
version -- no need to create a formal alias just to test.
"""
import json
import sys
import uuid

import boto3

REGION = "us-east-1"
ALIAS_ID = "TSTALIASID"


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python test_agent.py AGENT_ID "your prompt"')

    agent_id = sys.argv[1]
    prompt = sys.argv[2]

    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=ALIAS_ID,
        sessionId=str(uuid.uuid4()),
        inputText=prompt,
        enableTrace=True,
    )

    full_response = ""
    for event in response["completion"]:
        # enableTrace=True adds "trace" events alongside the normal "chunk" events -- this is
        # what shows the model's reasoning, which action group it picked, and the raw
        # Lambda input/output, instead of just the final answer.
        if "trace" in event:
            print("--- TRACE ---")
            print(json.dumps(event["trace"], indent=2, default=str))
            print()

        chunk = event.get("chunk")
        if chunk and "bytes" in chunk:
            full_response += chunk["bytes"].decode("utf-8")

    print("Agent response:", full_response)


if __name__ == "__main__":
    main()
