"""
Same calculator agent, same FastAPI wrapper shape as 05-ec2/terraform/app.py -- the agent code
itself doesn't change between compute targets, only how it's packaged and run. This time it
ships inside a Docker image instead of being installed by a boot script.
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
