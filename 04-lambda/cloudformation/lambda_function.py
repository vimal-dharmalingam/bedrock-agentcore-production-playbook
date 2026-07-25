from strands import Agent
from strands_tools import calculator

SYSTEM_PROMPT = "You are a helpful assistant that can perform calculations. Use the calculate tool for any math problems."
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

agent = None


def get_agent():
    global agent
    if agent is None:
        agent = Agent(model=MODEL_ID, tools=[calculator], system_prompt=SYSTEM_PROMPT)
    return agent


def lambda_handler(event, context):
    prompt = event.get("prompt", "Hello!")
    agent_instance = get_agent()
    result = agent_instance(prompt)

    return {
        "response": result.message.get("content", [{}])[0].get("text", str(result))
    }
