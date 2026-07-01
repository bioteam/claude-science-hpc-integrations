---
name: aws-hpc-slurm-ssm-connector
description: >-
  Connect Claude Science to a private-subnet AWS HPC cluster (AWS ParallelCluster,
  AWS PCS, or any Slurm head/login node) reachable ONLY through AWS Systems Manager
  (SSM), by reducing the SSM channel to an ordinary SSH connection the native
  compute provider can open. Works for AWS ParallelCluster and AWS PCS (same
  design; verified on ParallelCluster) as long as SSM access is enabled to the
  login/head node. Use whenever the user
  wants to reach an HPC head/login node "over SSM", "through Session Manager", "in
  a private subnet", or via an ssh_config ProxyCommand; mentions AWS ParallelCluster,
  AWS PCS, or a Slurm cluster behind SSM; or when an SSH compute provider that
  proxies over SSM fails to connect
  (e.g. "Connection closed by UNKNOWN port 65535"). Covers the SSM->SSH transport,
  the AWS credential / PATH pitfalls that break the ProxyCommand on a desktop app,
  registering the SSH-over-SSM provider, a least-privilege IAM user that makes the
  unavoidable static key safe to store, and the plain submit -> wait -> harvest
  Slurm loop. Reach for it even if the user only says "my private AWS cluster".
---

# Claude Science → private-subnet AWS HPC over SSM

This skill is a field-verified playbook for wiring Claude Science to an HPC
cluster — an **AWS ParallelCluster** or **AWS PCS** (Parallel Computing Service)
running **Slurm**, or any Slurm head/submit node — whose only ingress is **AWS
Systems Manager (SSM)**. There is no public IP and no bastion; you reach the box
today only with `aws ssm start-session`. It was built and confirmed end-to-end
against a live AWS ParallelCluster (Slurm 23.11.10), so the failure modes and
fixes here are the ones that actually bite.

**ParallelCluster or PCS — the method is the same.** Both present a Slurm
controller on a login/head node inside a private subnet; this connector only
cares that (a) the node runs `slurmctld` and (b) SSM access is enabled to it (the
SSM Agent is running and the instance role allows Session Manager). Everything
below applies to either environment unchanged — PCS-managed clusters have SSM on
their login nodes by default.

## The one idea

Claude Science's native compute provider speaks **SSH**, not SSM. So the whole
integration is: **reduce the SSM channel to an ordinary SSH connection** using an
`aws ssm start-session` `ProxyCommand` in `ssh_config`, register the head node as
an SSH compute provider, and submit Slurm jobs through it.

```
Claude Science ──SSH──▶ [ ProxyCommand: aws ssm start-session ] ──SSM──▶ head / login node
                                                                            │
                                                                    sbatch  │
                                                                            ▼
                                                                    Slurm ──▶ compute nodes
```

## How jobs run

Register the head node as a native SSH compute provider. `submit_job` opens the
SSM/SSH connection, stages inputs, and — because the head node is a Slurm
controller — **auto-wraps your script in `sbatch`** (job name `operon-<id>`), so
it runs on a compute node. `call_command` runs directly on the login node (no
`sbatch` wrapper) — use it for scheduler control commands (`sinfo`, `squeue`,
`sacct`) and quick checks. Only result files come back as artifacts.

## Start here — the setup order

Work through the reference files in this order. Each is self-contained; read the
one you need rather than all five.

1. **`references/architecture.md`** — the mental model: the SSM→SSH reduction,
   the Slurm layer, and the two conditions that can only be confirmed by a live
   smoke test.
2. **`references/01-setup-ssm-ssh.md`** — the `ssh_config` entry (SSM
   `ProxyCommand`), least-privilege IAM, provider registration, and the
   reachability smoke test. **Read the PATH section** — it is the #1 reason the
   connection fails on a desktop install.
3. **`references/02-secrets-and-credentials.md`** — the two secret types (AWS
   creds for SSM, the SSH key), and the static-key constraint of the Credentials
   store.
4. **`references/03-run-and-test.md`** — the plain-Slurm validation pattern
   (`sbatch`/`srun`), `call_command` vs `submit_job`, the `scratch_root`
   requirement, monitoring with `squeue`/`sacct`, and result harvesting.
5. **`references/04-troubleshooting.md`** — symptom→cause→fix: the SSM/ProxyCommand
   failure modes (PATH, `--profile`, `Connection closed by UNKNOWN port 65535`),
   Slurm-visibility gotchas, and ports.
6. **`references/05-least-privilege-iam.md`** — a Terraform plan for a dedicated
   IAM user that can *only* start an SSM session to one instance, making the
   unavoidable static key safe to store. Read this before registering AWS creds.

**Template:** `templates/ssh_config.template` — fill in the `<PLACEHOLDER>`s.
**Asset:** `assets/user_claude_science_ssm.tf` — the least-privilege IAM plan.
**Diagram:** `assets/architecture.png` (regenerate with `assets/make_architecture_diagram.py`).
**Verified captures:** `assets/captures/` — real (sanitized) terminal output from
the smoke test, an `sbatch`/`squeue`/`sacct` run, and a `submit_job` round-trip.

## Hard-won lessons (read these even if you skim everything else)

These are the things that cost real debugging time and are easy to get wrong.

### 1. The `ProxyCommand` fails silently on a macOS desktop app — it's PATH

Symptom: provider probe fails with `Connection closed by UNKNOWN port 65535`,
**identical with and without `--profile`**. That "identical" is the tell: the
ProxyCommand dies *before credentials are read*, so it is not a credential
problem — it is **PATH**. A macOS GUI app inherits `launchd`'s minimal PATH
(`/usr/bin:/bin`), which does not include Homebrew, so `aws` (and the
`session-manager-plugin` it calls by name) aren't found. Fix: prepend PATH
**inside** the ProxyCommand — an absolute path to `aws` alone is not enough
because `aws` still calls the plugin by name:

```
ProxyCommand sh -c "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH \
    aws ssm start-session --profile <aws-profile> --target %h \
    --document-name AWS-StartSSHSession --parameters 'portNumber=%p' --region <region>"
```

To see the *real* hidden error (ssh swallows ProxyCommand stderr), reproduce the
app's stripped env in a terminal:
`env -i /bin/sh -c '/full/path/to/aws ssm start-session --target <id> ...'`.

### 2. `--profile` vs. injected creds depends on WHERE the connection opens

On a **desktop install** the ProxyCommand runs on the user's own machine and the
AWS CLI reads `~/.aws/credentials` — so `--profile <name>` **is required** and
must name a real local profile. Only drop `--profile` if the connection is opened
in an environment where Claude Science injects AWS creds as env vars. Don't guess
— use the `env -i` test above to find out which case you're in.

### 3. Provider needs a `scratch_root` before `submit_job` works

`submit_job` refuses with *"has no scratch_root configured. Probe it first."*
until the provider has a staging directory set (Settings → Compute). Use a
writable shared path such as `/shared/scratch/<user>` (on ParallelCluster or PCS
this is typically FSx Lustre or an EFS/NFS mount visible to every compute node).

### 4. `call_command` runs on the login node; `submit_job` goes through `sbatch`

If the head node you registered is a Slurm controller, `submit_job` auto-detects
it and wraps your **script** in its own `sbatch` (job name `operon-<id>`), so the
script body runs on a compute node — put `srun`/`sbatch` directives inside it and
it schedules normally. `call_command` runs the command **directly on the login
node** with no wrapper — use it for `sinfo`/`squeue`/`sacct` and other control
commands. Match your tool to the job: `submit_job` when you want input-staging +
result-harvest, `call_command` for quick scheduler queries.

### 5. `submit_job` does not take `login_shell=`

`login_shell=True` is a `call_command` argument. For `submit_job`, put any
environment setup (`module load ...`, `export ...`) inside the job script itself.

## The verified submit → wait → harvest loop

```python
# repl tool
c = host.compute.create("ssh:<provider-name>")
job = c.submit_job(
    command=(
        "#!/bin/bash\n"
        "echo submit_host=$(hostname)\n"
        "srun hostname > compute_node.txt\n"        # runs on the allocated compute node
        "echo done=$(date -u +%FT%TZ) >> compute_node.txt\n"),
    intent="Plain Slurm validation job via SSM connector",
    outputs=["compute_node.txt"],
    timeout_seconds=600,
)
print(job.job_id)   # end the cell, then end the turn
# → wait_for_notification returns compute_done → save_artifacts(payload["featured_files"])
```

## The two conditions that can't be verified from inside a session

The SSM-over-SSH reduction depends on two things that are true or false on the
platform side, and **neither is checkable until you register the provider and
run a smoke test**:

1. **The platform's SSH layer must read the relevant `ssh_config`** — otherwise
   the `ProxyCommand` never takes effect.
2. **The host that opens the connection must carry the SSM tooling and your AWS
   credentials** — the AWS CLI, `session-manager-plugin`, and credentials with
   `ssm:StartSession` on the target instance.

If both hold, the smoke test (`01-setup-ssm-ssh.md`) returns cleanly and you
record the channel as `verified`. If it hangs or returns
`retry_after_user_action: true`, one of the two isn't met — see the
troubleshooting guide. Do not loop retries.
