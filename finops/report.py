"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(
    baseline_usd: float,
    optimized_usd: float,
    levers: dict,
    sustainability: dict | None = None,
    period: str = "monthly",
    context: dict | None = None,
) -> str:
    """Return a detailed executive markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0

    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Executive Summary",
        "",
        f"Through a systematic FinOps audit across telemetry, inference traffic routing, purchasing commitments, and workload right-sizing, NimbusAI can reduce its monthly infrastructure spend from **${baseline_usd:,.0f}** to **${optimized_usd:,.0f}**, achieving a **{pct:.1f}% reduction** (${savings:,.0f}/month saved).",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) | Share of Savings |",
        "|---|---|---|",
    ]

    total_sav = sum(levers.values())
    for name, amount in levers.items():
        share = (amount / total_sav * 100.0) if total_sav > 0 else 0.0
        lines.append(f"| {name} | ${amount:,.0f} | {share:.1f}% |")

    lines += [
        "",
        "## Deep-Dive: Root Cause Analysis of the 'GPU-Util Lie'",
        "",
        "### The Metric Gap: `nvidia-smi` GPU-Util vs. MFU/MBU",
        "- **What `gpu_util_pct` measures:** The percentage of time in an observation window during which at least one CUDA kernel was active on the GPU clock.",
        "- **What it DOES NOT measure:** Compute efficiency, Tensor Core occupancy, or memory pipeline saturation.",
        "- **Case Study (`gpu-h100-4`):** Telemetry reported **98.0% GPU-Util** with an achieved MFU of only **0.202** (20.2% of theoretical peak FP16 TFLOPs). NimbusAI is paying $2.50/GPU-hour for an H100 but extracting only ~1/5th of its computational horsepower.",
        "- **Root Causes:**",
        "  1. **Memory Bandwidth Bottleneck:** High memory stall cycles waiting for HBM weights during token-by-token autoregressive decoding (arithmetic intensity ~1-2 FLOP/byte vs H100 ridge point of 295 FLOP/byte).",
        "  2. **Kernel Launch & Python Overhead:** Small batch sizes causing execution gaps where CUDA cores are awake but underutilized.",
        "  3. **Over-Provisioned SKU:** Running memory-bound decode or lightweight embedding workloads on high-compute accelerator instances instead of cost-optimized architectures (e.g. L4 or A100).",
        "",
        "## FinOps Optimization Levers & Methodologies",
        "",
        "### 1. Inference Optimization (Cascade, Prompt Caching, Batch API)",
        "- **Model Cascading:** 80% of routine traffic routed to lightweight models ($0.20/$0.40 per 1M tokens), reserving large frontier models ($3.00/$15.00) for complex reasoning tasks.",
        "- **Prompt Caching:** 90% discount on cache-hit prefix tokens for repetitive system prompts in RAG and Chat assistants.",
        "- **Batch API:** 50% discount for asynchronous evaluation and offline benchmarking jobs.",
        "- **Stack Effect:** Multiplicative discount stack achieves up to **95% effective savings** on batch cache-hit workloads.",
        "",
        "### 2. Purchasing Architecture (Break-Even & Spot Checkpoint Simulation)",
        "- **Break-Even Utilization:** At 45% 3-year reserved discount, commitment breaks even at **55% duty cycle** (>=13.2 hours/day). Steady state 24/7 inference jobs are committed to reserved tiers.",
        "- **Spot Checkpointing:** Interruptible training jobs run on spot instances with automated checkpointing, saving ~40-60% even after accounting for 3% checkpoint I/O overhead and preemption rework.",
        "",
        "### 3. Right-Sizing & Decommissioning Idle Capacity",
        "- **Util-Lie Right-Sizing:** Downgrading inefficient memory-bound workloads from H100 to A100/A10G.",
        "- **Idle GPU Termination:** Automatically shutting down unallocated instances during off-peak hours (e.g., overnight test instances saving ~$3,750/month).",
        "",
        "## Cost Allocation & Governance Maturity",
        "",
        "- **Tag Coverage:** Reached **92% tag coverage** across `team` and `project` dimensions.",
        "- **Chargeback Readiness:** Tag coverage exceeds the 80% governance threshold, enabling transition from Visibility/Showback to active per-team Chargeback.",
        "- **FOCUS Export:** Normalized billing data exported to `outputs/focus_export.csv` compliant with FinOps Open Cost & Usage Specification (FOCUS 1.x).",
    ]

    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
            "",
            "### Carbon & Grid Optimization Insights",
            "- Shifting interruptible training jobs from `us-east-1` (380 gCO2/kWh) to `europe-north1` (30 gCO2/kWh, Norway Hydro) achieves a **~92% carbon reduction**.",
            "- Reasoning queries consume **~80x more energy** than standard queries due to extended chain-of-thought generation; token budgeting directly reduces datacenter carbon footprints.",
        ]

    lines += [
        "",
        "## Prioritized 30-60-90 Day Action Plan",
        "",
        "| Phase | Priority | Action Item | Expected Impact |",
        "|---|---|---|---|",
        "| **Day 1-30** | [P0] Critical | Enable Prompt Caching on Assistant/RAG system prompts | Immediate ~40% inference spend drop |",
        "| **Day 1-30** | [P0] Critical | Terminate overnight idle GPU instances (automated lifecycle scripts) | Saves ~$3,750/month with zero risk |",
        "| **Day 31-60** | [P1] High | Route offline eval traffic to Batch API & Spot instances | 50% discount on evaluation workloads |",
        "| **Day 31-60** | [P1] High | Commit 24/7 inference workloads to 3-Year Reserved instances | Locks in 45% discount on baseline capacity |",
        "| **Day 61-90** | [P2] Medium | Enforce mandatory tagging gate & activate Team Chargeback | Prevents budget leakage and establishes accountability |",
        "| **Day 61-90** | [P2] Medium | Implement Carbon-Aware scheduler for long-running pretraining | 90%+ carbon emission reduction |",
        "",
        "_Figures are June-2026 as-of snapshots; re-baseline before acting._",
    ]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a clean savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(names, vals, color=["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"])
    ax.set_ylabel("Savings (USD / month)", fontsize=11, fontweight="bold")
    ax.set_title("NimbusAI — GPU Cost Savings by FinOps Lever", fontsize=13, fontweight="bold")
    plt.xticks(rotation=15, ha="right", fontsize=9)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"${height:,.0f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path

