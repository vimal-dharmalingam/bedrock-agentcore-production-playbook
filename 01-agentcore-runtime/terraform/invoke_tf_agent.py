"""
Invokes the Terraform-deployed agent. Same invocation pattern as every other module.

Usage:
    python invoke_tf_agent.py AGENT_RUNTIME_ID "What is 25 * 4?"
"""
import json
import sys
import uuid

import boto3

REGION = "us-east-1"


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python invoke_tf_agent.py AGENT_RUNTIME_ID "your prompt"')

    agent_runtime_id = sys.argv[1]
    prompt = sys.argv[2]

    sts = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    agent_runtime_arn = f"arn:aws:bedrock-agentcore:{REGION}:{account_id}:runtime/{agent_runtime_id}"

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=str(uuid.uuid4()) + "-padding-to-reach-min-length",
        payload=payload,
        qualifier="DEFAULT",
    )

    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode("utf-8"))
    print("Agent response:", "".join(content))


if __name__ == "__main__":
    main()
