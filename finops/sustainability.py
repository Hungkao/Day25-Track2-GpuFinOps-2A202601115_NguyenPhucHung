"""Sustainability economics — energy and carbon as governed cost levers (deck §11).

Region selection cuts $ and carbon together; reasoning queries are an energy bomb.
"""
from __future__ import annotations

# Grid carbon intensity (gCO2 / kWh) — illustrative 2026 snapshot.
REGION_CARBON = {
    "us-east-1": 380,
    "us-west-2": 120,   # Oregon hydro
    "europe-north1": 30,  # Norway
    "europe-central2": 660,  # Poland (dirtiest)
    "us-east-wa": 90,
}
# Electricity price (USD / kWh) — illustrative.
REGION_PRICE_KWH = {
    "us-east-1": 0.12,
    "us-west-2": 0.07,
    "europe-north1": 0.09,
    "europe-central2": 0.18,
    "us-east-wa": 0.055,
}

REASONING_ENERGY_MULTIPLIER = 80.0  # deck: reasoning ~74-86x a small-model query


def wh_per_query(total_tokens: int, wh_per_1k_tokens: float = 0.30, is_reasoning: bool = False) -> float:
    """Energy for one query. Median Gemini prompt ~0.24 Wh; reasoning ~74-86x."""
    base = (total_tokens / 1000.0) * wh_per_1k_tokens
    return base * (REASONING_ENERGY_MULTIPLIER if is_reasoning else 1.0)


def carbon_g(wh: float, region: str = "us-east-1") -> float:
    """Grams CO2 for an energy amount in a region."""
    gco2_kwh = REGION_CARBON.get(region, 400)
    return (wh / 1000.0) * gco2_kwh


def energy_cost_usd(wh: float, region: str = "us-east-1") -> float:
    """Electricity cost of an energy amount in a region."""
    return (wh / 1000.0) * REGION_PRICE_KWH.get(region, 0.12)


def tokens_per_watt(total_tokens: int, wh: float, seconds: float = 1.0) -> float:
    """Energy efficiency of serving: tokens per watt (higher is better)."""
    watts = (wh * 3600.0) / seconds if seconds > 0 else 0.0
    return total_tokens / watts if watts > 0 else 0.0


def carbon_aware_schedule(
    total_kwh: float,
    current_region: str = "us-east-1",
    target_region: str = "europe-north1",
) -> dict:
    """Calculate carbon and electricity cost reduction when shifting workloads to cleaner regions."""
    cur_wh = total_kwh * 1000.0
    cur_carbon = carbon_g(cur_wh, current_region)
    tgt_carbon = carbon_g(cur_wh, target_region)
    cur_cost = energy_cost_usd(cur_wh, current_region)
    tgt_cost = energy_cost_usd(cur_wh, target_region)

    carbon_saved_g = cur_carbon - tgt_carbon
    carbon_reduction_pct = (carbon_saved_g / cur_carbon * 100.0) if cur_carbon > 0 else 0.0
    cost_saved_usd = cur_cost - tgt_cost

    return {
        "current_region": current_region,
        "target_region": target_region,
        "total_kwh": round(total_kwh, 2),
        "current_carbon_kg": round(cur_carbon / 1000.0, 3),
        "target_carbon_kg": round(tgt_carbon / 1000.0, 3),
        "carbon_saved_kg": round(carbon_saved_g / 1000.0, 3),
        "carbon_reduction_pct": round(carbon_reduction_pct, 1),
        "current_elec_cost_usd": round(cur_cost, 2),
        "target_elec_cost_usd": round(tgt_cost, 2),
        "elec_cost_saved_usd": round(cost_saved_usd, 2),
    }

