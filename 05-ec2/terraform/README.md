# 05-ec2 / terraform

The calculator agent hosted on a raw EC2 instance -- the first compute target in this repo with
no managed invoke API in front of it. Single method per the pacing decision (breadth across
`05`-`09` matters more than exhaustive depth on any one target).

## How this differs from everything before it

Every prior module -- AgentCore Runtime, Lambda -- had AWS provide the "how do I call this"
part: `InvokeAgentRuntime`, `lambda.invoke()`. EC2 is just a VM. Nothing calls the agent for you,
so this module has to build that part too:

- **`app.py`** wraps the same Strands calculator agent in a tiny FastAPI server (`/invoke`,
  `/health`) -- something has to listen on a port.
- **`user_data.sh.tpl`** is EC2's bootstrap mechanism (cloud-init) -- runs once at first boot,
  installs Python, writes a **systemd service** so the agent process survives reboots and
  crashes and restarts automatically, exactly like a production service would need to.
- **Terraform's job here is genuine IaaS provisioning** -- AMI selection, a security group, an
  IAM instance profile -- not just pointing at an artifact someone else built (a container image
  in `01/terraform`, a zip in `04-lambda/terraform`). This is the first module where Terraform is
  doing infrastructure work rather than deployment-orchestration work.

## Files
- `app.py` / `requirements.txt` -- the agent, as a FastAPI app
- `user_data.sh.tpl` -- bootstrap script, rendered by Terraform's `templatefile()` with the
  agent code, requirements, port, and region baked in as literal text before the instance ever
  sees it (no S3 upload step needed -- small enough to embed directly in user-data)
- `main.tf` / `variables.tf` / `outputs.tf` -- AMI lookup, default-VPC networking, security
  group, IAM role + instance profile, the instance itself
- `invoke_ec2_agent.py` -- plain HTTP client (stdlib only, no boto3) hitting `/invoke`

## How to run end to end

```bash
cd 05-ec2/terraform
terraform init
terraform apply
# wait ~60-90s after apply completes for user-data to finish installing deps and starting the service
python invoke_ec2_agent.py <PUBLIC_IP> "What is 25 * 4?"
```

`<PUBLIC_IP>` comes from `terraform output public_ip`. To tear down: `terraform destroy` --
important to actually do this when done, since an EC2 instance (unlike Lambda or AgentCore
Runtime) bills by the hour whether or not it's being invoked.

## IAM permissions

This module needed a materially different set of actions than anything before it -- the account
was also already at the **10-managed-policy-per-user ceiling** (hit in `04-lambda/terraform`)
by the time this module started, so every fix here extended an existing policy via
`create-policy-version` rather than creating a new one. `ec2-policy-merged.json` and
`bedrock-agent-lambda-policy-merged.json` in this folder are the actual merged documents applied
via CloudShell, kept as real portfolio artifacts rather than deleted after use.

Gaps hit, roughly in order:

1. **`ec2:DescribeImages` / `ec2:DescribeVpcAttribute`** -- AMI lookup and default-VPC data
   sources. Added to the existing `AgentCoreConsoleEc2ReadAccess` policy (from the `console`
   AgentCore Runtime module) rather than a new one.
2. **`ec2:CreateSecurityGroup`** and **`iam:CreateRole`** -- two separate policies needed
   extending. The IAM one is the more interesting lesson: `BedrockAgentLambdaAccess`'s role-
   management statement was scoped to `role/CalcAgentLambda*`, which `CalcAgentEc2ExecutionRole`
   didn't match. Broadened the pattern to `role/CalcAgent*` (dropping "Lambda") so it now covers
   this and any future `CalcAgent*`-prefixed role -- future-proofing instead of re-hitting this
   per compute target.
3. **`ec2:DescribeInstanceTypes`** -- a post-create read-back call, same "provider reads back
   more than it wrote" pattern as Lambda's `GetFunctionCodeSigningConfig` gap.
4. **`ec2:DescribeVolumes`** plus a full batch of instance-lifecycle read/write actions added in
   one pass (`DescribeNetworkInterfaces`, `DescribeInstanceCreditSpecifications`,
   `DescribeIamInstanceProfileAssociations`, `StopInstances`/`StartInstances`,
   `ModifyInstanceAttribute`, `AssociateIamInstanceProfile`, etc.) -- rather than discovering
   each one individually across more `terraform refresh` cycles, added the realistic full set an
   `aws_instance` resource needs across its whole lifecycle (create, refresh, update, destroy,
   plus manual stop/start) in a single policy version.

## Notes / gotchas

- **A comment inside `user_data.sh.tpl` broke the entire boot script**, and took the longest to
  diagnose of anything in this project so far. The template's own top comment described the
  mechanism using literal `${app_py_content}` syntax -- but `templatefile()` doesn't know the
  difference between a bash `#` comment and real code, so it substituted the multi-line file
  content right into the middle of that comment line. Since a `#` comment only extends to the
  end of its physical line, every subsequent line of the injected content became real,
  un-commented bash input, and the heredocs further down were never actually reached. Root
  cause was found by rendering the template locally and running it through plain `bash`,
  reproducing the exact error from the EC2 console log byte-for-byte -- confirming it before
  touching AWS again, rather than guessing through another deploy cycle.
- **AL2023's unversioned `python3` package is 3.9**, too old for `strands-agents` (requires
  `>=3.10`). Installs `python3.11` explicitly instead.
- **`user_data_replace_on_change = true` is required.** Terraform's default behavior for a
  `user_data` change is an in-place stop/modify/start on the existing instance -- but user-data
  only executes once, at first boot, via cloud-init. An in-place update changes what's *stored*
  as the instance's user-data without ever re-running it, so a "successful" apply can silently
  leave the instance running its old, broken boot state. This flag forces a full replace instead.
- **`exec > >(tee /var/log/user-data.log) 2>&1` beats a plain `>` redirect** for debugging here,
  since there's no SSH or SSM access by design -- the EC2 console's "Get system log" is the only
  window into what happened, and a plain file redirect sends output where the console can't see
  it. `set -x` alongside it pinpoints the exact failing command instead of just its aftermath.
- **No SSH port opened at all** -- the security group only allows the app port. Real debugging
  used the console's system log, not an interactive shell, on purpose.
- **No Elastic IP** -- every `terraform apply -replace` (or a manual stop/start) gives the
  instance a new public IP. Always re-fetch it (`terraform output public_ip` or
  `aws ec2 describe-instances`) before invoking.
- **Boot-time `pip install` means a ~60-90s gap** on first boot between `terraform apply`
  finishing and the agent being reachable -- a manual stop/start is much faster (~15-20s) since
  the venv and packages already exist on the EBS volume.
- **Costs money by the hour** even when idle, unlike every serverless module before it. Stop it
  (`aws ec2 stop-instances`) between uses rather than leaving it running, or `terraform destroy`
  when fully done experimenting.
- Uses the **default VPC and a public subnet** with a public IP directly on the instance, for
  simplicity. A real deployment would put this behind an ALB in a private subnet with a NAT
  gateway -- worth calling out in interviews as the known simplification here.

## Manual stop/start (outside Terraform)

```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=calc-agent-ec2" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].InstanceId" --output text
aws ec2 stop-instances --instance-ids <INSTANCE_ID>
aws ec2 wait instance-stopped --instance-ids <INSTANCE_ID>
aws ec2 start-instances --instance-ids <INSTANCE_ID>
aws ec2 wait instance-running --instance-ids <INSTANCE_ID>
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --query "Reservations[0].Instances[0].PublicIpAddress" --output text
```

## Status
- [x] `terraform apply` run and instance reachable
- [x] Invoke confirmed working end to end (`25 * 4 = 100`)
- [x] IAM gaps documented above with real errors
- [x] Manual stop/start confirmed as a cheap way to pause billing between uses
