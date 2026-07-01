#!/bin/bash
#SBATCH --job-name=cs-slurm-demo
#SBATCH --partition=cpu
#SBATCH --ntasks=1
#SBATCH --time=00:02:00
#SBATCH --output=cs-demo-%j.out
echo "hello from $(hostname) — Slurm job $SLURM_JOB_ID on $SLURM_JOB_PARTITION"
srun hostname
sleep 20
echo "finished at $(date -u +%FT%TZ)"
