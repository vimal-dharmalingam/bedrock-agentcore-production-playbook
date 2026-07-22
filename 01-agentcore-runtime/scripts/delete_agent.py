import os
import sys
import boto3

agent_runtime_id = os.getenv("AGENT_RUNTIME_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")

if not agent_runtime_id:
    raise SystemExit("Please provide an agent runtime ID. Use: AGENT_RUNTIME_ID=... python delete_agent.py")

client = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
client.delete_agent_runtime(agentRuntimeId=agent_runtime_id)
print(f"Delete initiated for agent runtime: {agent_runtime_id}")