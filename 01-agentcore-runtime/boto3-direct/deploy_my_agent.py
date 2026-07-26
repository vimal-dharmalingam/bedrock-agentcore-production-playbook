#!/usr/bin/env python3

from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
import os

def deploy():
    """Deploy the LangGraph agent"""
    boto_session = Session()
    region = boto_session.region_name
    
    agentcore_runtime = Runtime()
    
    # Check for required ENTRYPOINT environment variable
    #entrypoint = os.getenv("ENTRYPOINT")
    entrypoint = "my_calc_agent.py"  # Hardcoded for testing purposes
    if not entrypoint:
        print("Error: ENTRYPOINT environment variable is required.")
        print("Please set it before running this script:")
        print("export ENTRYPOINT=deployment/my_agent.py")
        exit(1)
    
    agent_name = entrypoint.split(".")[0]
    
    print(f"Deploying LangGraph agent to {region}...")
    
    # Configure
    agentcore_runtime.configure(
        entrypoint=entrypoint,
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="requirements.txt", 
        region=region,
        agent_name=agent_name
    )
            
    # Launch. auto_update_on_conflict=True is what makes this idempotent/CI-CD-friendly: the
    # first run creates the agent, every run after that updates the existing one in place
    # instead of failing with ConflictException("agent already exists").
    result = agentcore_runtime.launch(auto_update_on_conflict=True)
    print(f"✅ Agent deployed: {result.agent_arn}")

    # If running inside a GitHub Actions job, expose the ARN as a step output so a later
    # step (e.g. a smoke-test invoke) can read it without re-deploying or hardcoding it.
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"agent_arn={result.agent_arn}\n")

    return result

if __name__ == "__main__":
    deploy()