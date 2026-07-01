import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

META_GREY = "#888888"


def apply_figure_style(*, frame="open", font=None, sizes=(8, 7, 6), grid=False):
    import matplotlib as mpl
    if frame not in ("open", "boxed", "none"):
        raise ValueError(f"frame must be 'open'|'boxed'|'none', got {frame!r}")
    try:
        import os, sys, glob, matplotlib.font_manager as fm
        fdir = os.path.join(os.environ.get("CONDA_PREFIX") or sys.prefix, "fonts")
        if os.path.isdir(fdir):
            known = {f.fname for f in fm.fontManager.ttflist}
            for f in glob.glob(os.path.join(fdir, "*.ttf")):
                if f not in known:
                    fm.fontManager.addfont(f)
    except Exception:
        pass
    base, secondary, tick = sizes
    boxed = (frame == "boxed")
    rc = {
        "font.family": "sans-serif",
        "font.size": base,
        "axes.labelsize": base,
        "axes.titlesize": base,
        "legend.fontsize": secondary,
        "xtick.labelsize": tick,
        "ytick.labelsize": tick,
        "axes.linewidth": 0.6,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.size": 3, "ytick.major.size": 3,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "axes.spines.top": boxed, "axes.spines.right": boxed,
        "axes.spines.left": frame != "none", "axes.spines.bottom": frame != "none",
        "axes.grid": bool(grid),
        "legend.frameon": False,
        "figure.dpi": 200,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.titleweight": "normal",
        "axes.titlelocation": "left",
        "axes.labelweight": "normal",
        "lines.linewidth": 1.2,
        "patch.linewidth": 0.6,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    }
    if font:
        rc["font.sans-serif"] = [font, "DejaVu Sans"]
    mpl.rcParams.update(rc)


apply_figure_style(sizes=(9,8,7))

fig, ax = plt.subplots(figsize=(12.5, 7.4))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

def box(x, y, w, h, label, fc, ec=None, sub=None, fs=8.5, txtc="white", z=2, subdy=-2.0, labdy=1.6):
    ec = ec or fc
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6",
                 linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=z))
    ax.text(x+w/2, y+h/2 + (labdy if sub else 0), label, ha="center", va="center",
            fontsize=fs, color=txtc, fontweight="bold", zorder=z+1)
    if sub:
        ax.text(x+w/2, y+h/2 + subdy, sub, ha="center", va="center",
                fontsize=6.6, color=txtc, zorder=z+1)

def arrow(x1,y1,x2,y2,color,style="-|>",lw=1.8,ls="-",z=1,rad=0.0):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle=style,mutation_scale=14,
                 lw=lw,color=color,linestyle=ls,zorder=z,connectionstyle=f"arc3,rad={rad}"))

C_CS,C_TUN,C_HEAD,C_JS,C_SLURM,GREY = "#2b6cb0","#805ad5","#2f855a","#c05621","#4a5568",META_GREY

# Zones
ax.add_patch(FancyBboxPatch((1,6),29,86, boxstyle="round,pad=0.6,rounding_size=2",
             fc="#f0f5fb", ec=C_CS, lw=1.2, ls=(0,(4,3)), zorder=0))
ax.text(15.5, 89.5, "Claude Science", ha="center", fontsize=9.5, color=C_CS, fontweight="bold")
ax.add_patch(FancyBboxPatch((40,6),59,86, boxstyle="round,pad=0.6,rounding_size=2",
             fc="#f2fbf5", ec=C_HEAD, lw=1.2, ls=(0,(4,3)), zorder=0))
ax.text(69.5, 89.5, "AWS VPC — private subnet (no public IP)", ha="center",
        fontsize=9.5, color=C_HEAD, fontweight="bold")

# Claude Science internals
box(4, 69, 23, 12, "Control plane", C_CS, sub="host.compute · submit_job")
box(4, 51, 23, 12, "Data kernel", C_CS, sub="stage inputs · harvest outputs")
box(4, 31, 23, 13, "SSH layer", "#3182ce", sub="reads ssh_config →\nProxyCommand (SSM)", subdy=-2.6)
box(4, 13, 23, 11, "AWS creds (SSM)", GREY, sub="Customize → Credentials")

# Tunnel (single label, no cramped sub)
box(32, 42, 8.5, 16, "SSM\ntunnel", C_TUN, fs=8, txtc="white")

# Head / submit + services
box(43, 62, 25, 20, "ParallelCluster head / submit node", C_HEAD,
    sub="Ubuntu 22.04 · EFS home\n/shared/sw/schrodinger/2026-1", fs=8.2, subdy=-3.0)
box(46, 40, 19, 15, "jobserverd", C_JS, sub="gRPC/TLS :8030\nPKI client-cert auth", fs=9, z=3, subdy=-2.6)
box(72, 62, 24, 20, "Slurm controller", C_SLURM, sub="slurmctld\nlicense sensor (MMLIBS)", fs=8.2, subdy=-3.0)
box(72, 38, 24, 17, "Compute nodes", C_SLURM, sub="cpu-st / ml-cpu-dy\nFSx Lustre scratch", fs=8.2, subdy=-3.0)
box(46, 15, 19, 12, "SLM license\nserver", GREY, sub="MMLIBS tokens", fs=7.8, subdy=-3.2)

# Transport: SSH layer -> tunnel -> head
arrow(27, 37.5, 32, 48, C_TUN, lw=2.2)
arrow(40.5, 54, 43, 66, C_TUN, lw=2.2)
ax.text(34.5, 64.5, "SSH over SSM\n(ProxyCommand)", ha="center", va="center",
        fontsize=7, color=C_TUN, fontweight="bold")
arrow(15.5, 24, 15.5, 31, GREY, lw=1.4, ls=(0,(2,2)))

# Pattern A: exec on head node
arrow(27, 76, 43, 76, C_CS, lw=2.0)
ax.text(35, 79.4, "run jsc / testapp\non submit node", ha="center", va="bottom",
        fontsize=7.2, color=C_CS, fontweight="bold")

# head -> jobserver local gRPC
arrow(55.5, 62, 55.5, 55, C_JS, lw=2.0)
ax.text(58.6, 58.3, "local\ngRPC", ha="left", va="center", fontsize=6.6, color=C_JS)

# jobserver -> slurm
arrow(65, 49, 72, 65, C_SLURM, lw=2.0, rad=0.05)
ax.text(70.8, 53.5, "sbatch\n+ Qargs", ha="center", va="center", fontsize=6.8,
        color=C_SLURM, fontweight="bold")
# slurm ctrl -> compute
arrow(84, 62, 84, 55, C_SLURM, lw=2.0)
# license dashed links
arrow(74, 62, 63, 27, GREY, lw=1.4, ls=(0,(2,2)), rad=0.12)
ax.text(72.5, 33, "license\naccounting", ha="center", va="center", fontsize=6.4, color=GREY)
arrow(54, 40, 54, 27, GREY, lw=1.4, ls=(0,(2,2)))

fig.suptitle("Claude Science → AWS ParallelCluster Schrödinger jobserver over SSM",
             fontsize=11, fontweight="bold", y=0.985)
ax.text(50, 1.8, "One SSM/SSH tunnel:  the native compute provider runs jsc / testapp on the submit node, which "
        "hands jobs to jobserverd → Slurm; only result files come back",
        ha="center", va="center", fontsize=7.3, color="#333333")

fig.savefig("architecture.png", dpi=200, bbox_inches="tight")

# find and move the sbatch label, then verify text vs box
for t in fig.findobj(mpl.text.Text):
    if t.get_text().startswith("sbatch"):
        t.set_position((68.7, 47)); t.set_fontsize(6.6)
fig.savefig("architecture.png", dpi=200, bbox_inches="tight")
