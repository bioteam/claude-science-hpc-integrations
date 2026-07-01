import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def apply_figure_style(sizes=(9, 8, 7)):
    base, secondary, tick = sizes
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.size": base, "axes.labelsize": base, "axes.titlesize": base,
        "legend.fontsize": secondary, "xtick.labelsize": tick, "ytick.labelsize": tick,
        "figure.dpi": 200, "savefig.dpi": 300, "savefig.bbox": "tight",
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })


apply_figure_style()

fig, ax = plt.subplots(figsize=(12.5, 7.0))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(x, y, w, h, label, fc, ec=None, sub=None, fs=8.5, txtc="white", z=2, subdy=-2.4, labdy=1.8):
    ec = ec or fc
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6",
                 linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=z))
    ax.text(x+w/2, y+h/2 + (labdy if sub else 0), label, ha="center", va="center",
            fontsize=fs, color=txtc, fontweight="bold", zorder=z+1)
    if sub:
        ax.text(x+w/2, y+h/2 + subdy, sub, ha="center", va="center",
                fontsize=6.8, color=txtc, zorder=z+1)


def arrow(x1, y1, x2, y2, color, style="-|>", lw=1.8, ls="-", z=1, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                 lw=lw, color=color, linestyle=ls, zorder=z, connectionstyle=f"arc3,rad={rad}"))


C_CS, C_TUN, C_HEAD, C_SLURM, C_NODE, GREY = "#2b6cb0", "#805ad5", "#2f855a", "#c05621", "#4a5568", "#888888"

# Zones
ax.add_patch(FancyBboxPatch((1, 6), 29, 86, boxstyle="round,pad=0.6,rounding_size=2",
             fc="#f0f5fb", ec=C_CS, lw=1.2, ls=(0, (4, 3)), zorder=0))
ax.text(15.5, 89.5, "Claude Science", ha="center", fontsize=9.5, color=C_CS, fontweight="bold")
ax.add_patch(FancyBboxPatch((40, 6), 59, 86, boxstyle="round,pad=0.6,rounding_size=2",
             fc="#f2fbf5", ec=C_HEAD, lw=1.2, ls=(0, (4, 3)), zorder=0))
ax.text(69.5, 89.5, "AWS VPC \u2014 private subnet (no public IP)", ha="center",
        fontsize=9.5, color=C_HEAD, fontweight="bold")

# Claude Science internals
box(4, 69, 23, 12, "Control plane", C_CS, sub="host.compute \u00b7 submit_job")
box(4, 51, 23, 12, "Data kernel", C_CS, sub="stage inputs \u00b7 harvest outputs")
box(4, 31, 23, 13, "SSH layer", "#3182ce", sub="reads ssh_config \u2192\nProxyCommand (SSM)", subdy=-3.0)
box(4, 13, 23, 11, "AWS creds (SSM)", GREY, sub="Customize \u2192 Credentials")

# Tunnel
box(32, 42, 8.5, 16, "SSM\ntunnel", C_TUN, fs=8, txtc="white")

# Head node + Slurm layers
box(43, 62, 27, 20, "ParallelCluster or PCS\nlogin / head node", C_HEAD,
    sub="Slurm controller (slurmctld)\nshared FS \u00b7 scratch_root", fs=7.9, subdy=-4.4, labdy=2.8)
box(46, 36, 21, 16, "sbatch / srun", C_SLURM, sub="submit_job auto-wraps\nas sbatch (operon-<id>)", fs=8.8, z=3, subdy=-3.0)
box(74, 60, 22, 22, "Slurm scheduler", C_SLURM, sub="squeue \u00b7 sacct\nstatic + dynamic\npartitions", fs=8.4, subdy=-3.6)
box(74, 34, 22, 18, "Compute nodes", C_NODE, sub="cpu-st-* (always-on)\ncpu-dy-* / gpu-dy-*\nFSx / EFS scratch", fs=8.4, subdy=-3.6)

# Transport: SSH layer -> tunnel -> head
arrow(27, 37.5, 32, 48, C_TUN, lw=2.2)
arrow(40.5, 54, 43, 66, C_TUN, lw=2.2)
ax.text(34.5, 64.5, "SSH over SSM\n(ProxyCommand)", ha="center", va="center",
        fontsize=7, color=C_TUN, fontweight="bold")
arrow(15.5, 24, 15.5, 31, GREY, lw=1.4, ls=(0, (2, 2)))

# submit/exec on head node
arrow(27, 76, 43, 76, C_CS, lw=2.0)
ax.text(35, 79.6, "submit Slurm jobs\non login node", ha="center", va="bottom",
        fontsize=7.2, color=C_CS, fontweight="bold")

# head -> sbatch
arrow(56.5, 62, 56.5, 52, C_SLURM, lw=2.0)
# sbatch -> scheduler
arrow(67, 45, 74, 66, C_SLURM, lw=2.0, rad=0.06)
ax.text(72.4, 52.5, "sbatch", ha="center", va="center", fontsize=6.8,
        color=C_SLURM, fontweight="bold")
# scheduler -> compute
arrow(85, 60, 85, 52, C_NODE, lw=2.0)
ax.text(88.3, 56, "dispatch", ha="left", va="center", fontsize=6.6, color=C_NODE)
# results back
arrow(74, 40, 40.5, 50, C_CS, lw=1.6, ls=(0, (3, 2)), rad=-0.16)
ax.text(58, 30.5, "result files harvested\nas artifacts (lineage)", ha="center", va="center",
        fontsize=6.8, color=C_CS)

fig.suptitle("Claude Science \u2192 private-subnet AWS ParallelCluster / PCS (Slurm) over SSM",
             fontsize=11, fontweight="bold", y=0.985)
ax.text(50, 1.6, "One SSM/SSH tunnel:  the native compute provider opens SSH through an SSM session, "
        "submits Slurm jobs on the login/head node, and only result files come back "
        "\u2014 works for AWS ParallelCluster or PCS with SSM enabled",
        ha="center", va="center", fontsize=7.3, color="#333333")

fig.savefig("architecture.png", dpi=200, bbox_inches="tight")

# NOTE: the repo root keeps a copy of this diagram at
# assets/claude-science-ssm-architecture.png (used by the top-level README and
# Connecting-Claude-Science-to-AWS.md). If you regenerate this PNG, refresh that
# copy too:  cp architecture.png ../../../assets/claude-science-ssm-architecture.png
