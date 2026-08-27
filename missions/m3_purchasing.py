"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []

    # Extension 5: Track energy for interruptible jobs to evaluate carbon scheduling
    interruptible_kwh = 0.0

    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        jdays = int(num(j.get("days", 30)))
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        watts = num(c.get("watts", 500))
        on_demand_cost = gpu_hours * od

        # Extension 1: Multi-factor tier recommendation
        tier = pricing.recommend_tier(hpd, interruptible, gpu_type=gtype, job_days=jdays)
        if tier == "spot":
            irate = pricing.DEFAULT_INTERRUPT_RATES.get(gtype, 0.05)
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od, interrupt_rate=irate)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        if interruptible:
            # kWh = gpu_hours * watts / 1000
            interruptible_kwh += (gpu_hours * watts) / 1000.0

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost),
                     "interruptible": interruptible})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    # Extension 5: Carbon-aware scheduling calculation
    carbon_analysis = sustainability.carbon_aware_schedule(
        total_kwh=interruptible_kwh,
        current_region="us-east-1",
        target_region="europe-north1"
    )

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\n[Extension 5] Carbon-Aware Scheduling (Interruptible Training Workloads):")
        print(f"  Interruptible Energy : {carbon_analysis['total_kwh']:,.1f} kWh/month")
        print(f"  us-east-1 Carbon     : {carbon_analysis['current_carbon_kg']:,.1f} kg CO2e (${carbon_analysis['current_elec_cost_usd']:,.2f} electricity)")
        print(f"  europe-north1 Carbon : {carbon_analysis['target_carbon_kg']:,.1f} kg CO2e (${carbon_analysis['target_elec_cost_usd']:,.2f} electricity)")
        print(f"  Environmental Impact : Saved {carbon_analysis['carbon_saved_kg']:,.1f} kg CO2e ({carbon_analysis['carbon_reduction_pct']:.1f}% reduction)")

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
        "carbon_analysis": carbon_analysis,
    }


if __name__ == "__main__":
    run()

