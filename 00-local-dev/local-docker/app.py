"""
Calculator agent -- identical logic to 00-local-dev/local-python/app.py, packaged into the same
Dockerfile shape reused starting in 04-lambda/06-ecs-fargate/07-app-runner. The point of this
submodule isn't different agent code, it's proving the image itself runs correctly *before* any
AWS deploy target enters the picture -- if it's broken here, it'll be broken everywhere else too.
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
