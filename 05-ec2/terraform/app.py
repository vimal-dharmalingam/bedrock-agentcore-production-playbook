"""
FastAPI wrapper around the same Strands calculator agent used in every other module.

Why a web server here and nowhere else: every prior module (AgentCore Runtime, Lambda) had a
managed invoke API in front of the agent -- InvokeAgentRuntime, lambda.invoke(). EC2 is just a
VM; nothing calls the agent for you. Something has to listen on a port and be reachable, so this
module wraps the agent in the smallest reasonable HTTP server and runs it as a systemd service
(see user_data.sh.tpl) so it survives reboots and crashes.
"""
from fastapi import FastAPI
from pydantic import BaseModel
from strands import Agent
from strands_tools import calculator

SYSTEM_PROMPT = "You are a helpful assistant that can perform calculations. Use the calculate tool for any math problems."
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

app = FastAPI()
agent = Agent(model=MODEL_ID, tools=[calculator], system_prompt=SYSTEM_PROMPT)


class InvokeRequest(BaseModel):
    prompt: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoke")
def invoke(request: InvokeRequest):
    result = agent(request.prompt)
    return {
        "response": result.message.get("content", [{}])[0].get("text", str(result))
    }
