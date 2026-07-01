---
name: schrodinger-aws-hpc-ssm-connector
description: >-
  Connect Claude Science to a remote Schrödinger Suite jobserver running on an
  AWS ParallelCluster (or any Slurm HPC) that is reachable only through AWS SSM,
  and submit/monitor/harvest Schrödinger jobs from it. Use this skill whenever
  the user mentions Schrödinger, jobserver, jsc, testapp, Maestro, Glide,
  Desmond, FEP+, or MMLIBS licensing on a remote cluster; whenever they want to
  reach an HPC head node "over SSM", "through Session Manager", "in a private
  subnet", or via an ssh_config ProxyCommand; or whenever an SSH compute provider
  that proxies over SSM fails to connect. It covers reducing SSM to an SSH
  transport, registering the SSH-over-SSM compute provider, the AWS credential /
  PATH pitfalls that break the ProxyCommand, the jobserver PKI-certificate
  lifecycle, and how "-HOST" routes a job through the jobserver to Slurm (not
  straight to Slurm). Reach for it even if the user only says "my Schrödinger
  cluster" or "the jobserver box" without naming SSM explicitly.
---

# Claude Science → Schrödinger jobserver on AWS ParallelCluster (over SSM)

This skill is a field-verified playbook for wiring Claude Science to a
Schrödinger **jobserver** on an AWS ParallelCluster (or any Slurm cluster) whose
head/submit node is reachable **only through AWS Systems Manager (SSM)**. It was
built and confirmed end-to-end against a live cluster (Schrödinger 2026-1,
`jobserverd` 73163 / API v1.19.4, ParallelCluster + Slurm), so the failure modes
and fixes here are the ones that actually bite, not just the ones the manuals
predict.

## The one idea

Claude Science's native compute provider speaks **SSH**, not SSM. So the whole
integration is: **reduce the SSM channel to an ordinary SSH connection** using an
`aws ssm start-session` `ProxyCommand` in `ssh_config`, register the head node as
an SSH compute provider, and run `jsc`/`testapp` on it through the provider.

```
Claude Science ──SSH──▶ [ ProxyCommand: aws ssm start-session ] ──SSM──▶ head/submit node
                                                                            │
                                                        jsc / testapp -HOST │ (gRPC/TLS :8030)
                                                                            ▼
                                                                      jobserverd ──sbatch──▶ Slurm
```

## How jobs run

Run `jsc`/`testapp` **on the submit node** through the SSH-over-SSM provider —
full lifecycle (submit, monitor, harvest), with the jobserver certificate
staying on the cluster. This is the supported path for a stock Claude Science
deployment, which has **no** Schrödinger client installed locally, so everything
runs cluster-side and only result files come back.

## Start here — the setup order

Work through the reference files in this order. Each is self-contained; read the
one you need rather than all five.

1. **`references/architecture.md`** — the mental model: the SSM→SSH reduction,
   the jobserver gRPC/PKI layer, the Slurm layer, and the two conditions that
   can only be confirmed by a live smoke test.
2. **`references/01-setup-ssm-ssh.md`** — the `ssh_config` entry (SSM
   `ProxyCommand`), least-privilege IAM, provider registration, and the
   reachability smoke test. **Read the PATH section** —
   it is the #1 reason the connection fails on a desktop install.
3. **`references/02-secrets-and-credentials.md`** — the three secret types (AWS
   creds for SSM, the SSH key, the jobserver PKI certificate), and the
   static-key constraint of the Credentials store.
4. **`references/03-run-and-test.md`** — the `testapp` validation pattern, how
   `-HOST` routes through the jobserver, the two-Slurm-layer trap, expected
   state transitions, result harvesting, and collecting a `jsc postmortem` bundle.
5. **`references/04-troubleshooting.md`** — symptom→cause→fix: the SSM/ProxyCommand
   failure modes, the weak-RSA/OpenSSL-3 cert failure, version-match, and ports.
6. **`references/05-least-privilege-iam.md`** — a Terraform plan for a dedicated
   IAM user that can *only* start an SSM session to one instance, making the
   unavoidable static key safe to store. Read this before registering AWS creds.

**Template:** `templates/ssh_config.template` — fill in the `<PLACEHOLDER>`s.
**Asset:** `assets/user_claude_science_ssm.tf` — the least-privilege IAM plan.

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

### 3. `-HOST` routes THROUGH the jobserver, not straight to Slurm

`testapp -HOST <queue>` contacts `jobserverd:8030` over gRPC; the **jobserver**
does the `sbatch`. The job appears in `jsc info` (jobserver-tracked); your shell
script never calls `sbatch`. A straight-to-Slurm job would not show in `jsc info`
at all.

### 4. The two-Slurm-layer trap

On ParallelCluster there can be **two** Slurm layers: (a) the jobserver's own
Slurm cluster where `-HOST` jobs actually run — often **invisible** to the login
node's `squeue` — track these with `jsc info`/`jsc list`, not `squeue`; and (b)
the compute provider's own `sbatch` wrapper (job name `operon-<id>`) if the SSH
host you registered is itself a Slurm controller. A `submit_job` running a
`-HOST` command can therefore produce two Slurm jobs. For pure `jsc`/`testapp`
control, prefer `call_command` (runs directly, no wrapper); use `submit_job` when
you want the input-staging + result-harvest machinery.

### 5. Trust `jsc info`, not the wrapper exit code

`testapp`/`jsc` output piped under `set -e`/`set -u` (or a trailing shell glob)
can make the **job script** exit non-zero even when the Schrödinger job
`Status: Completed`. Read the state from `jsc info <id>`, not the script's exit
code.

### 6. Provider needs a `scratch_root` before `submit_job` works

`submit_job` refuses with *"has no scratch_root configured. Probe it first."*
until the provider has a staging directory set (Settings → Compute). Use a
writable shared path such as `/shared/scratch/<user>`.

### 7. Schrödinger may not be a module

Don't assume `module load schrodinger/...`. On many installs you set it directly:
`export SCHRODINGER=/shared/sw/schrodinger/<release>`. Check
`ls /shared/sw/schrodinger/` for installed releases; `jsc` is at `$SCHRODINGER/jsc`.

## The verified submit → wait → harvest loop

```python
# repl tool
c = host.compute.create("ssh:<provider-name>")
job = c.submit_job(
    command=(
        "export SCHRODINGER=/shared/sw/schrodinger/<release>\n"
        "$SCHRODINGER/testapp -HOST <queue> -t 90 -l MMLIBS:4 -j validate > testapp.out 2>&1\n"
        "SJID=$(grep -oE 'JobId: [0-9a-f-]+' testapp.out | awk '{print $2}')\n"
        "$SCHRODINGER/jsc info \"$SJID\" > jsc_info.txt 2>&1"),
    intent="Schrödinger testapp validation via jobserver → Slurm",
    outputs=["testapp.out", "jsc_info.txt"],
    timeout_seconds=600,
)
print(job.job_id)   # end the cell, then end the turn
# → wait_for_notification returns compute_done → save_artifacts(payload["featured_files"])
```

Note: `submit_job` does **not** take `login_shell=` (that is a `call_command`
argument) — set `SCHRODINGER` inside the script instead.

## Jobserver certificate model (summary)

Auth is two-phase: an initial **SSH-authenticated enrollment** (`jsc cert get
<host>:8030`, one password prompt) that writes a per-user cert to
`~/.schrodinger/jobserver.config`, then **pure PKI** for all later calls. The
cert is version-agnostic (one cert works across releases). The cert lives on the
cluster and needs no capture for this workflow. Full detail and
the weak-RSA/OpenSSL-3 rotation fix are in the references.
