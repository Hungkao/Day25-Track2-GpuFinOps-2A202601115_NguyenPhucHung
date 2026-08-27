"""Efficiency metrics — the numbers that actually drive GPU cost.

Key teaching point (deck §5): nvidia-smi "GPU-Util %" is a *time-active* clock,
not an efficiency metric. A GPU can read 100% util while its MFU is ~20% — you
are paying the full GPU-hour for a fraction of the FLOPs you rented.
"""
from __future__ import annotations


def compute_mfu(achieved_tflops: float, peak_tflops: float) -> float:
    """Model FLOPs Utilization = achieved / peak (clamped to 0..1).

    Good training MFU is ~0.35-0.45; >0.50 is excellent. Returns 0 if peak<=0.
    """
    if peak_tflops <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_tflops / peak_tflops))


def compute_mbu(achieved_bw_tbs: float, peak_bw_tbs: float) -> float:
    """Model Bandwidth Utilization = achieved HBM BW / peak BW (clamped 0..1).

    The right metric for memory-bound decode; target ~0.60 on H100-80GB batch-1.
    """
    if peak_bw_tbs <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_bw_tbs / peak_bw_tbs))


def arithmetic_intensity(flops: float, bytes_moved: float) -> float:
    """FLOP / byte for a workload (the x-axis of the roofline model)."""
    if bytes_moved <= 0:
        return 0.0
    return flops / bytes_moved


def roofline_regime(intensity: float, ridge_point: float) -> str:
    """Below the ridge point a workload is memory-bound; at/above it is compute-bound.

    H100 ridge ~295 FLOP/byte (BF16). LLM decode (~1-2) is memory-bound; prefill
    (~455) is compute-bound — which is *why* prefill/decode disaggregation pays off.
    """
    return "compute-bound" if intensity >= ridge_point else "memory-bound"


def flag_util_lies(rows, util_threshold: float = 0.90, mfu_threshold: float = 0.30):
    """Return the rows where GPU-Util is high but MFU is low — money leaking.

    `rows` is an iterable of dicts each having 'gpu_util_pct' (0-100) and 'mfu' (0-1).
    These are GPUs you are billed full-rate for while they do little real compute.
    """
    out = []
    for r in rows:
        util = float(r.get("gpu_util_pct", 0)) / 100.0
        mfu = float(r.get("mfu", 0))
        if util >= util_threshold and mfu < mfu_threshold:
            out.append(r)
    return out


def idle_waste_usd(idle_hours: float, on_demand_hr: float) -> float:
    """Dollars burned by a GPU left running idle (training done, instance up)."""
    return max(0.0, idle_hours) * max(0.0, on_demand_hr)


def dollars_per_gb_vram(on_demand_hr: float, hbm_gb: float) -> float:
    """Cost efficiency of VRAM capacity: $/GB-hour."""
    if hbm_gb <= 0:
        return 0.0
    return on_demand_hr / hbm_gb


def recommend_mbu_rightsizing(
    achieved_bw_tbs: float,
    current_gpu: str,
    catalog: dict[str, dict],
    headroom_factor: float = 1.25,
) -> dict:
    """Recommend an optimal lower-cost GPU for memory-bound workloads based on bandwidth demand.

    Finds the cheapest GPU whose peak_bw_tbs >= achieved_bw_tbs * headroom_factor.
    """
    needed_bw = achieved_bw_tbs * headroom_factor
    cur_info = catalog.get(current_gpu, {})
    cur_price = float(cur_info.get("on_demand_hr", 0.0))

    candidates = []
    for gtype, info in catalog.items():
        bw = float(info.get("peak_bw_tbs", 0.0))
        price = float(info.get("on_demand_hr", 0.0))
        vram = float(info.get("hbm_gb", 0.0))
        if bw >= needed_bw and price < cur_price:
            candidates.append({
                "gpu_type": gtype,
                "peak_bw_tbs": bw,
                "on_demand_hr": price,
                "hbm_gb": vram,
                "vram_cost_per_gb": dollars_per_gb_vram(price, vram),
                "savings_pct": round((1.0 - price / cur_price) * 100.0, 1),
            })

    candidates.sort(key=lambda x: x["on_demand_hr"])
    best = candidates[0] if candidates else None
    return {
        "current_gpu": current_gpu,
        "current_price": cur_price,
        "needed_bw_tbs": round(needed_bw, 3),
        "recommended_gpu": best["gpu_type"] if best else current_gpu,
        "recommended_price": best["on_demand_hr"] if best else cur_price,
        "savings_pct": best["savings_pct"] if best else 0.0,
        "alternatives": candidates,
    }

