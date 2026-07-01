# Architecture — Claude Science → AWS ParallelCluster Schrödinger jobserver over SSM

```
  Claude Science                          AWS VPC — private subnet (no public IP)
 ┌────────────────┐                      ┌──────────────────────────────────────┐
 │ Control plane  │                      │  ParallelCluster head / submit node   │
 │ host.compute   │                      │  (enrolled jobserver client, EFS home)│
 │ Data kernel    │   SSH over SSM       │                                       │
 │ SSH layer  ────┼──────────────────────▶  run jsc / testapp -HOST <queue>      │
 │  reads         │  ProxyCommand:        │            │                          │
 │  ssh_config    │  aws ssm start-session│            │ local gRPC/TLS :8030     │
 │ AWS creds(SSM) │                      │            ▼   (PKI client-cert)      │
 └────────────────┘                      │        jobserverd ──sbatch+Qargs──▶ Slurm
                                          │            │                     │    │
                                          │            │        MMLIBS       ▼    │
                                          │        SLM    ◀···· license  Compute  │
                                          │        license srv  sensor   nodes   │
                                          └──────────────────────────────────────┘

  One SSM/SSH tunnel: the native compute provider runs jsc/testapp on the submit
  node, which hands jobs to jobserverd → Slurm; only result files come back.
```

> ![Architecture](../assets/architecture.png)
>
> (Rendered PNG above; regenerate with `assets/make_architecture_diagram.py`.)

## The problem in one sentence

The cluster lives in a **private subnet with no public IP**, reachable only
through **AWS Systems Manager (SSM)**. Claude Science's native compute provider
speaks **SSH** (and managed byoc backends) — it has no "SSM transport" and no
"jobserver transport". So the entire integration hinges on one move: **reduce
the SSM channel to an ordinary SSH connection** that the platform can open, and
then let two things ride that one tunnel.

## The three layers you're actually connecting

There are three distinct hops, and it helps to keep them separate:

1. **Transport** — Claude Science → head/submit node. This is SSH, but the
   connection is *opened through* an SSM session (`aws ssm start-session` used
   as an SSH `ProxyCommand`). Once established, it behaves like any SSH target.
2. **Job control** — the Schrödinger **jobserver** (`jobserverd`) is the
   middleware that accepts Schrödinger jobs and dispatches them to Slurm. It
   listens on **gRPC/TLS port 8030** and authenticates clients with **per-user
   PKI certificates**. `jsc` and `testapp` are its clients.
3. **Scheduling** — the jobserver translates each Schrödinger job into an
   `sbatch` submission with the queue's `Qargs`, Slurm runs it on compute
   nodes, and a license sensor reserves MMLIBS tokens from the SLM (Schrödinger
   License Manager) server so a job only starts when both compute *and* license
resources are free.

## Run `jsc`/`testapp` on the submit node

Register the head node as a native SSH compute provider. `submit_job` opens the
SSM/SSH connection, stages inputs, and runs `jsc` / `testapp` **on the submit
node itself** — which is already an enrolled jobserver client with its
certificate persisted on the EFS-mounted home. You get the full Claude Science
job lifecycle for free: an approval modal, input staging, output harvesting as
artifacts with lineage, and non-blocking parking. Nothing Schrödinger-related
needs to run locally, and no certificate has to leave the cluster.

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

Grounded in the Schrödinger documentation and a field-captured BioTeam
verification note for this exact platform shape:

| Component | Value |
|---|---|
| Platform | AWS ParallelCluster 3.11.1 |
| OS | Ubuntu 22.04 (compute nodes) |
| Storage | FSx Lustre (compute scratch) + EFS (submit-host home / software) |
| Schrödinger Suite | 2026-1, installed at `/shared/sw/schrodinger/2026-1` |
| jobserver | `jobserverd` 73163, API v1.19.4, gRPC/TLS on `:8030` |
| Scheduler | Slurm with accounting DB + remote MMLIBS license checking |
| Example queues | `efs-hpc-cpu` (static), `efs-hpc-ml-cpu` (dynamic) |
| Module | `schrodinger/efs-jobserver/2026-1` |

Your values may differ; treat these as the reference shape, not as literals to
copy. The setup guide shows where each one plugs in.
