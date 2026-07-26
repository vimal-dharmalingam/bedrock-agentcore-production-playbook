"""
Calculator agent -- the "00" baseline. Runs directly with `python`, no Docker, no AWS deploy
target at all. Every other module in this repo (01-09) ships this exact same agent logic
somewhere in AWS; this is the control case everything else gets compared against.

Same FastAPI wrapper shape as every later module (05-ec2, 06-ecs-fargate, 07-app-runner):
a Strands Agent with a calculator tool, exposed over /health and POST /invoke. Bedrock is a
real remote API call even here -- there's no "offline" mode -- so this still needs working AWS
credentials (any profile with bedrock:InvokeModel) and the model enabled in us-east-1.

Usage:
    python app.py
    # then, in another terminal:
    python invoke_local_agent.py "What is 25 * 4?"
"""
from fastapi import FastAPI
from pydantic import BaseModel
from strands import Agent
from strands_tools import calculator

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

app = FastAPI()
agent = Agent(model=MODEL_ID, tools=[calculator])


class InvokeRequest(BaseModel):
    prompt: str


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/invoke")
def invoke(request: InvokeRequest):
    result = agent(request.prompt)
    return {"response": str(result)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
