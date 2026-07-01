# 03 · Job-submission & validation runbook

Prerequisite: the smoke test in `01-setup-ssm-ssh.md` returned cleanly (the
provider is registered and reachable). This runbook lands a real Slurm job
through the connector and validates the full chain — provider → `sbatch` →
compute node → harvested results.

The recommended validation pattern is a trivial batch job that exercises Slurm
scheduling and result harvesting without needing any input data: `srun hostname`
plus a short `sleep`, writing one small output file.

---

## `call_command` vs. `submit_job` — which to use

If the head node you registered is a **Slurm controller** (the usual case for a
ParallelCluster login node), the two entry points behave differently:

- **`call_command`** runs the command **directly on the login node**, no
  scheduler wrapper. Use it for control/monitoring — `sinfo`, `squeue`, `sacct`,
  `scontrol`, quick `ls` — and for launching your own `sbatch` explicitly.
- **`submit_job`** auto-detects the Slurm controller and **wraps your script in
  its own `sbatch`** (job name `operon-<id>`), so the script body runs on a
  compute node. Use it when you want the provider's **input-staging +
  result-harvest** machinery. The wrapped script can contain `srun`/`sbatch`
  directives and schedules normally.

> `submit_job` does **not** accept `login_shell=` (that's a `call_command`
> argument). Put any `module load` / `export` setup inside the job script.

---

## Step 1 — confirm partitions

```python
# repl tool
c = host.compute.create("ssh:pcluster-ssm")
print(c.call_command("sinfo -s", intent="List Slurm partitions", login_shell=True))
```

Expect the partition table from the smoke test. Verified live (see
`assets/captures/01-reachability-smoke-test.txt`): `cpu*`, `driver`,
`cpu-highmem`, `gpu`, `gpu4x`, `ml-gpu-s`, `ml-cpu`, `qm`. A `*` marks the
default partition; `-st-` nodes are static (always-on), `-dy-` nodes are
dynamic (ParallelCluster boots them on demand — expect a brief `CF`
CONFIGURING state on first use).

## Step 2 — submit a validation job

> **Prerequisite:** the provider must have a **`scratch_root`** configured
> (Settings → Compute) before `submit_job` will run — it stages the job there.
> Without it, `submit_job` refuses with *"has no scratch_root configured. Probe
> it first."* Verified value here: `/shared/scratch/<user>` (FSx Lustre).

```python
# repl tool
job_script = r"""#!/bin/bash
echo "submit_host=$(hostname)"
echo "job_id=${SLURM_JOB_ID:-<none>}"
srun hostname                                   # runs on the allocated compute node
sleep 5
{
  echo "run_utc=$(date -u +%FT%TZ)"
  echo "compute_node=$(srun hostname 2>/dev/null | head -1)"
  echo "slurm_job_id=${SLURM_JOB_ID:-NA}"
} > slurm_result.txt
cat slurm_result.txt
"""
job = c.submit_job(
    command=job_script,
    intent="Plain Slurm validation job (srun hostname + result file) via SSM connector",
    outputs=["slurm_result.txt"],
    timeout_seconds=600,
)
print(job.job_id)   # end the cell, then end the turn
```

## Step 3 — park and harvest

End the turn; the `compute_done` notification returns
`{job_id, status, exit_code, featured_files, ...}`. Then publish:

```python
# python tool
save_artifacts(payload["featured_files"], language="bash")
```

**Verified round trip (2026-07-01, Tenvie cluster** — full capture in
`assets/captures/03-submit-job-roundtrip.txt`**):** `status: success`,
`exit_code: 0`, and the harvested `slurm_result.txt` showed the job had run on a
compute node, not the login node:

```
run_utc=2026-07-01T16:55:51Z
compute_node=cpu-st-1
slurm_job_id=181286
```

## Step 4 — monitor with `squeue` / `sacct` (not from the harvest)

When you launch with an explicit `sbatch` via `call_command`, track the job on
the login node's scheduler directly. Verified transition (capture in
`assets/captures/02-sbatch-squeue-sacct.txt`):

```
$ sbatch --parsable cs_demo.sbatch
Submitted batch job 181287
$ squeue -u $USER
   JOBID PARTITION          NAME    USER ST  TIME NODES NODELIST(REASON)
  181287       cpu  cs-slurm-demo hpcuser  R  0:02     1 cpu-st-1
$ sacct -j 181287 --format=JobID,JobName,Partition,State,ExitCode,Elapsed,NodeList
  181287    cs-slurm-demo  cpu  COMPLETED  0:0  00:00:21  cpu-st-1
```

- A **static-partition** job (`cpu-st-*`) goes `R` (RUNNING) almost immediately.
- A **dynamic-partition** job shows `CF` (CONFIGURING) for a few minutes while
  ParallelCluster boots a fresh instance, then runs.
- `sacct` after completion reports `State=COMPLETED`, `ExitCode=0:0`.

A reusable batch script is bundled at `assets/captures/cs_demo.sbatch`.

---

## Real workloads

Once the validation job passes, submit real work the same way — replace the
script body with your command, staging input files with
`inputs=[{src, dst_filename}]` and harvesting result files with `outputs=[...]`.
Inside the script, request resources with normal `#SBATCH` directives or `srun`
flags, and target the partition whose nodes match the resource profile (CPU vs.
GPU, memory) as shown by `sinfo`. For GPU work, submit to `gpu`/`gpu4x`/`ml-gpu-s`
and add `--gres=gpu:N` (or the cluster's configured GRES) in the script.
