# 03 · Job-submission & validation runbook

Prerequisite: the smoke test in `01-setup-ssm-ssh.md` returned cleanly (the
provider is registered and reachable). This runbook lands a real Schrödinger
job through the jobserver and validates the full chain — jobserver → Slurm →
license → completion.

The BioTeam-recommended validation pattern is `testapp`, which submits a
trivial job that exercises jobserver dispatch, Slurm scheduling, and MMLIBS
license checkout without needing any input structure:

```
$SCHRODINGER/testapp -HOST <queue> -t 90 -l MMLIBS:4 -j <job-name>
```

- `-HOST <queue>` — a queue from `jsc hosts list` (e.g. `efs-hpc-cpu`)
- `-t 90` — run for 90 seconds
- `-l MMLIBS:4` — request 4 MMLIBS license tokens (verifies SLM license integration)
- `-j <name>` — a job name you can track

---

## How a job routes: `-HOST` goes through the jobserver, not straight to Slurm (verified)

This is the single most important thing to understand, and it was confirmed by
live testing on 2026-07-01.

**`-HOST <queue>` routes through the jobserver.** The `<queue>` names an entry
in the Schrödinger hosts file that the jobserver owns; each such entry is a Slurm
batch-queue definition, e.g.:

```
name: efs-hpc-cpu
host: jobserver.example.internal
queue: SLURM2.1
qargs: --partition=cpu --ntasks=%NPROC%
schrodinger: /shared/sw/schrodinger/2026-1
```

When you run `testapp -HOST hpc-cpu`, the client contacts `jobserverd:8030` over
gRPC, and **the jobserver** performs the `sbatch` to the partition in `qargs`.
Your shell script never calls `sbatch`/`srun`. Proof: the job appears in
`jsc info <id>` (jobserver-tracked) with `Command Line: ... testapp -HOST
hpc-cpu ...`, and a script that contains no scheduler commands still schedules
and completes. A job submitted straight to Slurm would **not** show up in `jsc
info` at all.

### The two-Slurm-layer trap

On this deployment there are **two independent Slurm layers**, and it is easy to
conflate them:

1. **The jobserver's own Slurm cluster** — behind `jobserver.example.internal`.
   This is where `-HOST` jobs actually run. The **login node you SSH into cannot
   see these jobs** in its `squeue`/`sacct` — during a verified `-HOST hpc-cpu`
   run, the login node's `squeue` showed *nothing* while `jsc info` reported
   `Status: Running`. Track these jobs with `jsc info` / `jsc list`, not
   `squeue`.
2. **The compute provider's own `sbatch` wrapper** — if the SSH host you
   registered has Slurm on it, `submit_job` auto-detects it and wraps your job
   **script** in its own `sbatch` (job name `operon-<id>`) on the *login node's*
   scheduler. That wrapper is unrelated to Schrödinger routing — it is just how
   the provider runs your script.

So a `submit_job` that runs `testapp -HOST hpc-cpu` produces **two** Slurm jobs:
the provider's `operon-*` wrapper on the login-node cluster, and the jobserver's
dispatch on its own cluster. Both worked in testing — but the `operon-*` wrapper
is redundant overhead for a command whose only job is to hand off to the
jobserver.

### Recommended submission path

Because `-HOST` already delegates all scheduling to the jobserver, you do **not**
need the provider to `sbatch` your wrapper on the login node:

- **For `jsc`/`testapp` control and monitoring** (hosts list, info, submit,
  status), use **`call_command`** — it runs the command **directly on the login
  node** (no `operon-*` wrapper) and the jobserver owns the actual scheduling.
  This is the cleanest path for launching and tracking Schrödinger jobs.
- **Use `submit_job`** when you specifically want the provider's **input-staging
  + result-harvest** machinery (pull output files back as artifacts — verified
  working, see "Harvesting results" below). Be aware it adds the login-node
  `sbatch` wrapper.
- **To avoid the double-`sbatch` entirely**, register the provider against a
  submit target that is *not* a Slurm controller (or a login/head partition), so
  `submit_job` runs the `jsc`/`testapp` command directly and the jobserver is the
  only scheduler in the path.

> **Watch the exit code.** `testapp`/`jsc` output piped under `set -e`/`set -u`
> (or a trailing shell glob) can make the **job script** exit non-zero even when
> the Schrödinger job `Status: Completed`. Trust `jsc info <id>` Status, not the
> wrapper script's exit code.

---

## Running jobs via the native compute provider

`jsc`/`testapp` run **on the login/submit node**, which is already an enrolled
jobserver client. For control + monitoring use `call_command` (runs directly on
the node, no wrapper); use `submit_job` only when you want result-harvest (see
the routing section above).

> **Environment note (this deployment):** Schrödinger is **not** an environment
> module here. Set it directly: `export SCHRODINGER=/shared/sw/schrodinger/2026-1`
> (installed releases: 2025-2, 2025-4, 2026-1). On clusters where it *is* a
> module, use `module load <schrodinger-module>` instead.

### Step 1 — confirm queues

```python
# repl tool
c = host.compute.create("ssh:pcluster-ssm")
print(c.call_command(
    "export SCHRODINGER=/shared/sw/schrodinger/2026-1; $SCHRODINGER/jsc hosts list",
    intent="List jobserver queues before submitting", login_shell=True))
```

Expect a `Configured hosts:` block listing the jobserver host:port and its
queues. Verified output included `hpc-cpu`, `hpc-gpu`, `hpc-gpu4x`,
`hpc-ml-gpu-s`, `hpc-ml-cpu`, `hpc-qm`, `hpc-schrod-driver`,
`hpc-cpu-highmem`, `slurm-fep-master`, plus `localhost`.

### Step 2 — submit a validation job

> **Prerequisite:** the provider must have a **`scratch_root`** configured
> (Settings → Compute) before `submit_job` will run — it stages the job there.
> Without it, `submit_job` refuses with *"has no scratch_root configured. Probe
> it first."* Verified value here: `/shared/scratch/$USER` (FSx Lustre). Also
> note: `submit_job` does **not** accept `login_shell=` (that is a
> `call_command` argument) — put `export SCHRODINGER=...` in the script instead.

```python
# repl tool
job_script = r'''#!/bin/bash
# NOTE: avoid `set -e`/pipefail around testapp/jsc — a nonzero from the pipe/glob
# can mask a Completed job. Trust `jsc info` Status instead.
export SCHRODINGER=/shared/sw/schrodinger/2026-1
JOB=testapp.2026-1.cpu.$(date +%s)
echo "JOBNAME=$JOB"
$SCHRODINGER/testapp -HOST hpc-cpu -t 90 -l MMLIBS:4 -j "$JOB" > testapp.out 2>&1
echo "testapp rc=$?"; cat testapp.out
# jobserver-side tracking (NOT squeue — the login node can't see the jobserver's slurm)
SJID=$(grep -oE 'JobId: [0-9a-f-]+' testapp.out | awk '{print $2}')
$SCHRODINGER/jsc info "$SJID" 2>&1 > jsc_info.txt
cat jsc_info.txt
'''
job = c.submit_job(
    command=job_script,
    intent="testapp validation on hpc-cpu — 90s, 4 MMLIBS tokens",
    outputs=["testapp.out", "jsc_info.txt", {"glob": "*.log", "visibility": "hidden"}],
    timeout_seconds=600,
)
print(job.job_id)   # end the cell, then end the turn
```

### Step 3 — park and harvest

End the turn; the `compute_done` notification returns
`{job_id, status, exit_code, featured_files, ...}`. Then publish:

```python
# python tool
save_artifacts(payload["featured_files"], language="bash")
```

### Step 4 — read the state transitions

**Track jobserver-dispatched jobs with `jsc`, not `squeue`.** On this deployment
the jobserver runs jobs on *its own* Slurm cluster, which the login node's
`squeue`/`scontrol` cannot see (verified: login-node `squeue` was empty while
`jsc info` showed `Running`). So the authoritative monitor is:

**`$SCHRODINGER/jsc info <job-id>`** (and `jsc list -a`) — client-side job
tracking; progresses `Created → Running → Completed`, with the compute host it
landed on. Verified transition: a `-HOST hpc-cpu` job completed in ~1m on
`cpu-st-c8idxlarge-1`. If the job fails, the per-job log is at
`~/.schrodinger/job_server/logs/queue-submission-<job-id>.log`.

**When you *can* see it in Slurm (`squeue`/`scontrol`)** — i.e. when the client
and jobserver share the same visible Slurm cluster — a static-partition job goes
`R` immediately; a dynamic-partition job shows `CF` (CONFIGURING) while
ParallelCluster boots a fresh instance:

```
JOBID   PARTITION                       NAME  ST   TIME  NODES  NODELIST(REASON)
166290       cpu   testapp.2026-1.cpu.mmlibs_4  R   0:18      1  cpu-st-c8idxlarge-1
166289    ml-cpu   testapp.2026-1.ml-cpu.mmli  CF   0:18      1  ml-cpu-dy-c8id2xlarge-1
```

and two `scontrol show job <jobid>` fields confirm the Slurm ↔ jobserver link:

```
Licenses=mmlibs@schrodinger_...:4          # Slurm reserved 4 MMLIBS tokens
Comment=SchrodingerJobId=<uuid>            # jobserver's job id, linked to Slurm
```

> Do not confuse these with the compute provider's own `operon-<id>` wrapper job
> on the login-node scheduler (see the routing section) — that is the provider
> running your *script*, not the Schrödinger job's dispatch.

### Expected results

- CPU (static) queue job → `RUNNING` immediately, completes in ~90 s.
- Dynamic queue job → may sit `PENDING`/`CONFIGURING` a few minutes while the
  instance boots, then runs.
- `jsc info` reports `Completed`; `testapp` exits `0`.

> **Partial-failure signature to watch for:** if Slurm submission and license
> accounting succeed but `testapp`/`jsc info` hang or error with a gRPC TLS
> failure, you're almost certainly hitting the weak-RSA client-cert issue — see
> `04-troubleshooting.md`.

---

## Harvesting results (verified)

Pulling job output files back into Claude Science as artifacts works through the
provider's `submit_job` harvest. Verified 2026-07-01: a `testapp` run with
`-a -f 3 -A` produced extra output files plus a Schrödinger **result archive**
(`<jobserver-jobid>.tgz`), all harvested back intact.

- Declare what to pull with `outputs=[...]` globs on `submit_job`.
- The `compute_done` payload lists `featured_files`; save them:
  ```python
  # python tool
  save_artifacts(payload["featured_files"], language="bash")
  ```
- The Schrödinger result archive is named by the **jobserver JobId**
  (`0dd747aa-...-.tgz`) and is a valid gzip tarball of the job's outputs.

For real products, Schrödinger writes results into the job directory / uploads
them to the jobserver filestore; pull them with the product's `-LOCAL` or the
job's downloaded output, then declare those paths in `outputs`.

---

## Collecting a postmortem (verified)

When a job fails — or when you simply want a full diagnostic bundle for support —
`jsc postmortem` packages everything about a job into a single archive: the
launch log, jobserver logs for that job, supervisor logs, output logs, the
`schrodinger.hosts` file, SLM license-server diagnostics, and server/client
sysinfo. This works over the same compute provider as any other job.

```bash
#!/bin/bash
export SCHRODINGER=/shared/sw/schrodinger/<release>
# Collect a postmortem for a completed/failed job by its jobserver JobId.
$SCHRODINGER/jsc postmortem <jobserver-jobid> > pm.log 2>&1
```

Submit it with a `*.zip` output glob and harvest as usual:

```python
# repl tool
pm = c.submit_job(
    command=open("pm_script.sh").read(),
    intent="jsc postmortem for <jobserver-jobid>",
    outputs=["*.zip", "pm.log"],
    timeout_seconds=300,
)
# → compute_done → save_artifacts(payload["featured_files"], language="bash")
```

Verified 2026-07-01: `jsc postmortem <jobid>` for a completed `testapp` job
produced `<jobserver-jobid>-postmortem.zip` (~23 KB, 24 entries), harvested and
downloaded intact.

**Two things to know:**

- **Redaction is ON by default.** `jsc postmortem` replaces sensitive strings
  (the job name, and anything it recognises as sensitive) before zipping — the
  log prints e.g. `cs-e2e => JOBNAME`. Keep it on for anything you'll share.
  Flags: `--without-redaction` (include everything unredacted),
  `--replace <string>` (add your own strings to scrub), `--no-zip` (emit a
  directory instead of a zip), `--with-subjobs` (by default only abnormally
  terminated subjobs are included).
- **`jsc postmortem` writes the zip to the current working directory — do NOT
  `cd` elsewhere in the submit script.** The provider harvests the job's cwd, so
  a `cd "$(mktemp -d)"` (or any `cd`) puts the zip outside the harvest root and
  `outputs=["*.zip"]` catches nothing. Run `jsc postmortem` in place; the archive
  lands where `submit_job` can pull it.

---

## Real workloads

Once `testapp` validates, submit real Schrödinger jobs the same way — replace
the `testapp` line with the product command (Glide, Desmond, Jaguar, FEP+,
etc.), staging input structures with `inputs=[{src, dst_filename}]` and
harvesting result files with `outputs=[...]`. Target the queue whose `Qargs`
match the resource profile (CPU vs. GPU, memory) as shown by `jsc hosts list`.
