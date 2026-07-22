#https://github.com/aws-samples/sample-getting-started-with-amazon-agentcore/blob/main/01-agentcore-runtime/README.md
#"us.anthropic.claude-haiku-4-5-20251001-v1:0"
# import os

# try:
#     from bedrock_agentcore import BedrockAgentCoreApp
# except ImportError:
#     class BedrockAgentCoreApp:
#         def __init__(self):
#             pass

#         def entrypoint(self, func):
#             return func

#         def run(self):
#             print("Bedrock Agent Core runtime is not installed. Running local demo instead.")
#             return None

# from strands import Agent
# from strands_tools import calculator

# # System prompt for the agent
# SYSTEM_PROMPT = "You are a helpful assistant that can perform calculations. Use the calculate tool for any math problems."

# # Model configuration from environment variable.
# # Set MODEL_ID in your shell if you want to override this value.
# #MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
# MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
# # Global agent instance for reuse across invocations
# agent = None


# def create_agent(tools):
#     """Create agent with lazy loading pattern for performance"""
#     global agent
#     if agent is None:
#         agent = Agent(
#             model=MODEL_ID,
#             tools=[tools],
#             system_prompt=SYSTEM_PROMPT,
#         )
#     return agent


# # Initialize the Bedrock Agent Core application
# app = BedrockAgentCoreApp()


# @app.entrypoint
# def invoke(payload):
#     """AgentCore Runtime entry point"""
#     try:
#         agent_instance = create_agent(calculator)
#         prompt = payload.get("prompt", "Hello!")
#         result = agent_instance(prompt)
#         return {
#             "response": result.message.get("content", [{}])[0].get("text", str(result))
#         }
#     except Exception as exc:
#         return {"response": f"Error: {exc}"}


# print("123")

# if __name__ == "__main__":
#     print("Running local demo...")
#     demo_result = invoke({"prompt": "What is 25 * 5?"})
#     print(demo_result)

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
import os
from strands_tools import calculator

# System prompt for the agent
SYSTEM_PROMPT = "You are a helpful assistant that can perform calculations. Use the calculate tool for any math problems."

# Model configuration from environment variable
#MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Global agent instance for reuse across invocations
agent = None

def create_agent(tools):
    """Create agent with lazy loading pattern for performance"""
    global agent
    if agent is None:
        agent = Agent(
            model=MODEL_ID,
            tools=[tools],
            system_prompt=SYSTEM_PROMPT
        )
    return agent

# Initialize the Bedrock Agent Core application
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """AgentCore Runtime entry point"""
    agent = create_agent(calculator)
    prompt = payload.get("prompt", "Hello!")
    result = agent(prompt)
    
    return {
        "response": result.message.get('content', [{}])[0].get('text', str(result))
    }

if __name__ == "__main__":
    app.run()