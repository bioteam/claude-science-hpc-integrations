# Architecture — Claude Science → private-subnet AWS HPC over SSM

```
  Claude Science                          AWS VPC — private subnet (no public IP)
 ┌────────────────┐                      ┌──────────────────────────────────────┐
 │ Control plane  │                      │  ParallelCluster / PCS login/head node│
 │ host.compute   │                      │  (Slurm controller, shared FS)        │
 │ Data kernel    │   SSH over SSM       │                                       │
 │ SSH layer  ────┼──────────────────────▶  sbatch / srun / sinfo / squeue       │
 │  reads         │  ProxyCommand:        │            │                          │
 │  ssh_config    │  aws ssm start-session│            │ sbatch                   │
 │ AWS creds(SSM) │                      │            ▼                          │
 └────────────────┘                      │        Slurm ──────────▶ compute nodes │
                                          │                          FSx / EFS     │
                                          └──────────────────────────────────────┘

  One SSM/SSH tunnel: the native compute provider opens SSH through an SSM
  session, then submits Slurm jobs on the login node; only result files come back.
```

> A polished PNG of this diagram can be regenerated with
> `assets/make_architecture_diagram.py` (matplotlib) for slides.

## The problem in one sentence

The cluster lives in a **private subnet with no public IP**, reachable only
through **AWS Systems Manager (SSM)**. Claude Science's native compute provider
speaks **SSH** — it has no "SSM transport". So the entire integration hinges on
one move: **reduce the SSM channel to an ordinary SSH connection** that the
platform can open, and run Slurm on the other end.

This is true for **AWS ParallelCluster and AWS PCS** alike — both put a Slurm
controller on a login/head node in a private subnet. The only requirement is that
**SSM access is enabled to that node** (SSM Agent running + an instance role that
allows Session Manager). Nothing below changes between the two.

## The two layers you're actually connecting

There are two distinct hops, and it helps to keep them separate:

1. **Transport** — Claude Science → head/login node. This is SSH, but the
   connection is *opened through* an SSM session (`aws ssm start-session` used
   as an SSH `ProxyCommand`). Once established, it behaves like any SSH target.
2. **Scheduling** — the head node is a **Slurm controller**. `submit_job`
   auto-wraps your script in `sbatch` (job name `operon-<id>`) so it runs on a
   compute node; `call_command` runs directly on the login node for control
   commands (`sinfo`, `squeue`, `sacct`). Result files harvest back as
   artifacts with lineage.

## Run jobs on the login node

Register the head node as a native SSH compute provider. `submit_job` opens the
SSM/SSH connection, stages inputs, submits through Slurm, and harvests outputs.
You get the full Claude Science job lifecycle for free: an approval modal, input
staging, output harvesting as artifacts with lineage, and non-blocking parking.
Nothing HPC-specific needs to run locally.

## The two conditions that can't be verified from inside a session

The SSM-over-SSH reduction depends on two things that are true or false on the
platform side, and **neither is checkable until you register the provider and
run a smoke test**:

1. **The platform's SSH layer must read the relevant `ssh_config`** — otherwise
   the `ProxyCommand` never takes effect.
2. **The host that opens the connection must carry the SSM tooling and your AWS
   credentials** — the AWS CLI, `session-manager-plugin`, and credentials with
   `ssm:StartSession` on the target instance. The connection is opened by the
   platform, *not* your laptop, so those must live where the platform connects
   from.

If both hold, the smoke test returns cleanly and you record the channel as
`verified`. If it hangs or returns `retry_after_user_action: true`, one of the
two isn't met — see the troubleshooting guide.

## Environment this is written against

Verified end-to-end 2026-07-01 against a live AWS ParallelCluster (with thanks
to Tenvie for cluster access). AWS PCS is expected to work the same for this
connector — it presents the same Slurm controller on a private-subnet login node
reached over SSM — but this recipe was verified only on ParallelCluster; on PCS,
confirm the login node is the sbatch submit host and that its instance role
allows SSM. Only the node/partition names below would differ.

| Component | Value |
|---|---|
| Platform | AWS ParallelCluster (Slurm-managed); AWS PCS expected to work the same (verified on ParallelCluster) |
| Login node | `ip-10-0-0-10`, login user `hpcuser` |
| Scheduler | Slurm 23.11.10 |
| Partitions | `cpu*` (20), `driver` (3), `cpu-highmem` (5), `gpu` (24), `gpu4x` (8), `ml-gpu-s` (3), `ml-cpu` (3), `qm` (10) |
| Static compute node | `cpu-st-1` (partition `cpu`, always-on) |
| Dynamic nodes | `*-dy-*` (ParallelCluster boots on demand; brief `CF` state) |
| Shared scratch | `/shared/scratch/<user>` (FSx Lustre) — used for `scratch_root` |
| Transport | SSH-over-SSM via `ssh_config` ProxyCommand — VERIFIED working |

Your values will differ; treat these as the reference shape, not literals to
copy. The setup guide shows where each one plugs in.
