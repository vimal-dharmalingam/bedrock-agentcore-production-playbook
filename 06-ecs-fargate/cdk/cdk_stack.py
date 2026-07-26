import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_iam as iam
from constructs import Construct

# Points at the image build_and_push.py already built and pushed -- NOT ContainerImage.from_asset(),
# which would run `docker build` again on every single `cdk deploy`. Rerun build_and_push.py
# manually whenever container/ actually changes; this tag stays fixed otherwise.
REPO_NAME = "bedrock-agentcore-calc-agent-ecs-fargate"
IMAGE_TAG = "latest"


class CalcAgentEcsFargateStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECS has TWO roles per task, unlike anything built so far in this repo:
        # - execution role: used by the ECS agent itself to pull the image from ECR and write
        #   logs to CloudWatch. Auto-created by the pattern construct below; we don't touch it.
        # - task role: used by the RUNNING CONTAINER's own AWS SDK calls, i.e. what
        #   bedrock:InvokeModel needs. Created explicitly here so it can be named to match the
        #   "role/CalcAgent*" wildcard already granted elsewhere in this project.
        task_role = iam.Role(
            self, "TaskRole",
            role_name="CalcAgentEcsFargateTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        task_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:*",
                ],
            )
        )

        # Reference the repo build_and_push.py already created as a real CDK object -- NOT a
        # raw URI string. This is the piece that was missing: ContainerImage.from_registry()
        # takes a plain string, so CDK has no way to know it's an ECR repo it can grant pull
        # access to, and the auto-created execution role ends up with no ECR permissions at
        # all. from_ecr_repository() (below) gets an actual IRepository reference and CDK
        # wires the grant automatically, the same way from_asset() would have.
        repo = ecr.Repository.from_repository_name(self, "ExistingRepo", REPO_NAME)

        # ApplicationLoadBalancedFargateService is a single L3 construct that creates the
        # cluster, task definition, service, ALB, target group, listener, and security groups
        # all at once -- the idiomatic CDK way to stand up exactly this "containerized app
        # behind a load balancer" shape, instead of wiring each piece by hand the way
        # 01-agentcore-runtime/cloudformation had to for its execution role.
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "CalcAgentFargateService",
            service_name="calc-agent-ecs-fargate",
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                # from_ecr_repository() references an image that's ALREADY built and pushed
                # (by build_and_push.py) -- like from_registry(), this does not run
                # `docker build` as part of `cdk deploy`. Unlike from_registry(), CDK grants
                # the execution role ecr:GetAuthorizationToken + repo-scoped pull permissions
                # automatically, because it has a real repository reference to grant on.
                image=ecs.ContainerImage.from_ecr_repository(repo, IMAGE_TAG),
                container_port=8080,
                task_role=task_role,
            ),
        )

        # The construct's default target-group health check pings "/" -- this app only has
        # /health and /invoke, so point it at the real endpoint or the service never reports
        # healthy and the ALB keeps cycling tasks.
        service.target_group.configure_health_check(path="/health")

        cdk.CfnOutput(self, "LoadBalancerDNS", value=service.load_balancer.load_balancer_dns_name)
