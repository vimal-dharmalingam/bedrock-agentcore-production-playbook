import aws_cdk as cdk

from cdk_stack import CalcAgentLambdaCdkStack

app = cdk.App()

CalcAgentLambdaCdkStack(
    app,
    "CalcAgentLambdaCdkStack",
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
