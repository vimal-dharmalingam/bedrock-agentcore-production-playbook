"""
The calculator agent, restructured for plain AWS Lambda instead of AgentCore Runtime.

Biggest structural difference from every 01-agentcore-runtime module: there's no
BedrockAgentCoreApp, no @app.entrypoint decorator, no app.run() starting an HTTP server on
port 8080. Lambda doesn't need any of that -- the Lambda service itself handles receiving
invocations and calling your handler function directly. This file is just a plain function.
"""
from strands import Agent
from strands_tools import calculator

SYSTEM_PROMPT = "You are a helpful assistant that can perform calculations. Use the calculate tool for any math problems."
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Global agent instance -- same lazy-init reuse-across-invocations pattern as every other
# module. On Lambda this matters even more: a "warm" container reuses this global between
# invocations, avoiding rebuilding the Agent object every single call.
agent = None


def get_agent():
    global agent
    if agent is None:
        agent = Agent(model=MODEL_ID, tools=[calculator], system_prompt=SYSTEM_PROMPT)
    return agent


def lambda_handler(event, context):
    """
    Lambda's required entrypoint shape: (event, context) -> return value.
    `event` is whatever payload the caller sent (see invoke_lambda_agent.py) -- no HTTP
    request/response wrapping to deal with, Lambda already did that translation for us if
    invoked via API Gateway/Function URL, or it's just the raw dict if invoked directly via
    boto3's `invoke`, which is what we're doing here.
    """
    prompt = event.get("prompt", "Hello!")
    agent_instance = get_agent()
    result = agent_instance(prompt)

    return {
        "response": result.message.get("content", [{}])[0].get("text", str(result))
    }
