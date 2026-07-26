# 06-ecs-fargate / cdk

The calculator agent as a real containerized, orchestrated, load-balanced service -- the first
module in this repo that's a genuine production topology, not a single instance or function.
Single method (CDK) per the pacing decision.

## How this differs from everything before it

- **The environment is a Docker image, built once, not assembled at boot.** `05-ec2` hit several
  bugs because its environment was hand-assembled by a shell script running live on a VM at
  boot time. Here, `container/Dockerfile` builds the exact same environment ahead of time --
  what you test locally (`docker build && docker run`) is byte-for-byte what runs in production.
  No boot script, no drift.
- **Two IAM roles per task, not one.** The *execution role* is used by the ECS agent itself to
  pull the image from ECR and write logs -- auto-created, untouched here. The *task role* is
  used by the running container's own AWS SDK calls (`bedrock:InvokeModel`) -- created
  explicitly in `cdk_stack.py` so it can be named to match this repo's `role/CalcAgent*`
  convention. Nothing else built so far has this two-role split.
- **A real Application Load Balancer, not a public IP on the compute itself.** `05-ec2` exposed
  the instance directly to the internet on its app port. Here, the ALB is the only public-facing
  thing; the Fargate task's security group only accepts traffic from the ALB's security group,
  not the internet directly -- the ALB pattern this repo's earlier modules were all
  simplifications of.
- **`ApplicationLoadBalancedFargateService`** is a single CDK L3 construct that wires up the
  cluster, task definition, service, ALB, target group, listener, and security groups together
  -- the idiomatic CDK way to stand up this whole topology, versus hand-wiring each piece the
  way `01-agentcore-runtime/cloudformation` had to for just an execution role.
- **`linux/amd64`, matching Fargate's default architecture** -- a native build on this Windows
  host, not a QEMU cross-platform build like every `01-agentcore-runtime`/arm64 module needed.
- **The image is built and pushed once, separately from `cdk deploy`** -- see below. Every other
  CDK module in this repo (`01/cdk`, `04-lambda/cdk`) used `from_asset()`, which rebuilds the
  image/zip on every single deploy. Here `cdk_stack.py` points at a fixed, already-pushed ECR
  tag via `ecs.ContainerImage.from_ecr_repository()` instead, so `cdk deploy` stays fast and
  doesn't touch Docker at all once the image exists -- a deliberate choice, not the default CDK
  pattern. (First attempt used `from_registry()` with a raw URI string instead -- see IAM
  section below for why that broke.)

## Files
- `container/app.py` / `container/requirements.txt` / `container/Dockerfile` -- the agent,
  packaged as a container (same FastAPI wrapper shape as `05-ec2/terraform/app.py`)
- `build_and_push.py` -- creates the ECR repo, builds the image (linux/amd64), pushes it. Run
  once, and again only when `container/` actually changes.
- `app.py` -- CDK entry point
- `cdk_stack.py` -- the `ApplicationLoadBalancedFargateService` stack, referencing the image
  `build_and_push.py` already pushed
- `cdk.json` / `requirements.txt` -- CDK tooling config and CDK library deps
- `invoke_ecs_agent.py` -- stdlib-only HTTP client hitting the ALB's `/invoke`

## How to run end to end

```bash
cd 06-ecs-fargate/cdk
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python build_and_push.py
cdk deploy
# wait ~2-3 min after deploy completes for the Fargate task to pass its target-group health check
python invoke_ecs_agent.py <ALB_DNS_NAME> "What is 25 * 4?"
```

Rerun `python build_and_push.py` (then `cdk deploy` again) only when `container/app.py` or its
`requirements.txt` actually change -- otherwise `cdk deploy` alone is enough for any
infrastructure-only change (task size, ALB config, IAM, etc.).

`<ALB_DNS_NAME>` is printed as the `LoadBalancerDNS` output at the end of `cdk deploy`, or:
```bash
aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'CalcAgent')].DNSName" --output text
```

To tear down: `cdk destroy` -- important to actually do this, since an ALB and a running Fargate
task both bill continuously, unlike Lambda or AgentCore Runtime.

## IAM permissions

`04-lambda/cdk` needed zero new grants for `always_learner` because CDK deploys go through the
bootstrap execution role via `sts:AssumeRole`. That held true here too -- CDK itself never hit
an `always_learner` AccessDenied. The real permission bug was inside the stack's own generated
IAM, not `always_learner`'s:

- **The execution role couldn't pull the image at all.** First version of `cdk_stack.py` used
  `ecs.ContainerImage.from_registry(image_uri_string)` -- a raw string, not a CDK-recognized ECR
  repository object. Because CDK had no repository reference to call `.grantPull()` on, the
  auto-created execution role ended up with *no* ECR permissions whatsoever. Every task launch
  failed identically: `ResourceInitializationError: unable to pull secrets or registry auth ...
  AccessDeniedException ... not authorized to perform: ecr:GetAuthorizationToken`. 15 tasks
  crash-looped before this was caught. Fix: `ecr.Repository.from_repository_name()` to get a
  real `IRepository` reference, then `ecs.ContainerImage.from_ecr_repository(repo, tag)` instead
  of `from_registry()` -- CDK then auto-grants the execution role `ecr:GetAuthorizationToken`
  plus repo-scoped `BatchGetImage`/`GetDownloadUrlForLayer`/`BatchCheckLayerAvailability`
  correctly, the same way `from_asset()` always did.
- **The stuck deploy couldn't just be killed and retried.** Once tasks started crash-looping,
  the `AWS::ECS::Service` resource sat in `CREATE_IN_PROGRESS` indefinitely -- and without
  `circuitBreaker` enabled on the service (a warning CDK prints but doesn't enforce), a
  never-stabilizing ECS deployment can take **up to 3 hours** to fail and roll back on its own.
  Killing the local `cdk deploy` process doesn't help either -- CloudFormation keeps working on
  AWS's side regardless of whether the CLI is watching. Fastest real fix: patch the *already-
  created* execution role directly via `aws iam put-role-policy` (found its exact physical name
  via `aws cloudformation describe-stack-resources`, since CloudFormation truncates long logical
  IDs when generating physical IAM names). ECS's automatic retry then succeeded within a minute,
  the stuck resource stabilized, and the stack reached `CREATE_COMPLETE` on its own -- no restart
  needed. Ran `cdk deploy` once more afterward to reconcile the code's real fix
  (`from_ecr_repository()`) against the deployed stack, then deleted the manual patch policy
  once CDK's own grant was confirmed present, so nothing manual was left governing the role.
- `always_learner` itself needed one new grant, for local debugging visibility (not for the
  deploy to work): `ecs:ListClusters`/`ListTasks`/`DescribeTasks`/`DescribeServices`/etc.
  Added to `AgentCoreConsoleEc2ReadAccess` (now a general compute-debugging bucket policy, not
  just EC2) -- but that policy was already at its 5-version cap, so the oldest version (`v1`,
  fully superseded) had to be deleted first before a new version could be created.

## Notes / gotchas
- The default target-group health check pings `/`, which this app doesn't have (only `/health`
  and `/invoke`) -- without `configure_health_check(path="/health")`, the ALB would mark the
  task permanently unhealthy and keep cycling it, a subtle failure that looks like "it deployed
  fine but never works."
- **No VPC was specified**, so `ApplicationLoadBalancedFargateService` created a brand new one
  from scratch -- 2 AZs, public + private subnets, an Internet Gateway, and **two NAT Gateways**
  (one per AZ, for the private subnets' internet/AWS API access). This alone accounted for most
  of the ~4 minutes before the ECS Service resource even started creating, and now bills
  continuously (~$32/month per NAT Gateway) regardless of traffic. `05-ec2` deliberately used the
  account's existing default VPC to avoid exactly this -- worth fixing here the same way if this
  module keeps running past the portfolio/demo stage.
- **Enable `circuitBreaker` before deploying anything experimental again.** Its entire purpose is
  to detect a crash-looping deployment and fail fast (minutes, not hours) -- CDK warns about its
  absence but doesn't default it on. Would have turned tonight's stuck deploy into a quick,
  automatic failure instead of a race against a 3-hour timeout.
- Costs money continuously (ALB hourly charge + NAT Gateways + Fargate vCPU/memory-hours) even
  at `desired_count=1` with no traffic -- `cdk destroy` when done, same discipline as `05-ec2`,
  more line items to remember here than anywhere else so far.
- `cpu=256`/`memory_limit_mib=512` (0.25 vCPU / 0.5GB) is the smallest Fargate task size that
  supports this combination -- deliberately minimal for a calculator agent.

## Status
- [x] `cdk deploy` run and service healthy behind the ALB
- [x] Invoke confirmed working end to end
- [x] IAM gaps documented above with real errors (the `from_registry()` vs `from_ecr_repository()`
      bug, the 3-hour circuit-breaker risk, and the `always_learner` ECS read-access gap)
