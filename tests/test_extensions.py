import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing, metrics, sustainability


def test_cache_is_worth_it_and_break_even():
    # When write cost is zero, 1 read is enough
    assert pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost_per_m=0.0) is True
    assert pricing.cache_is_worth_it(avg_cache_reads=0.5, write_cost_per_m=0.0) is False

    # Break-even calculation with storage/write cost:
    # write_cost = 0.27, base_price = 3.0, read_discount = 0.1 (90% off -> saves 2.70 per 1M tokens)
    # break_even = 0.27 / 2.70 = 0.10 reads
    be_reads = pricing.cache_break_even_reads(write_cost_per_m=0.27, base_input_price_per_m=3.0, read_discount=0.10)
    assert abs(be_reads - 0.10) < 1e-6
    assert pricing.cache_is_worth_it(avg_cache_reads=0.15, write_cost_per_m=0.27, base_input_price_per_m=3.0) is True
    assert pricing.cache_is_worth_it(avg_cache_reads=0.05, write_cost_per_m=0.27, base_input_price_per_m=3.0) is False


def test_recommend_tier_with_gpu_type_and_duration():
    # Standard baseline behavior preserved
    assert pricing.recommend_tier(20, False) == "reserved"
    assert pricing.recommend_tier(10, True) == "spot"
    assert pricing.recommend_tier(4, False) == "on_demand"

    # Multi-factor enhancements:
    # High duty cycle but short project duration (< 14 days) avoids multi-year lock-in
    assert pricing.recommend_tier(24, False, gpu_type="H100", job_days=7) == "on_demand"
    assert pricing.recommend_tier(24, False, gpu_type="H100", job_days=90) == "reserved"

    # GPU-specific interruption risk evaluation
    assert pricing.recommend_tier(12, True, gpu_type="H100") == "spot"


def test_mbu_rightsizing_and_vram_cost():
    catalog = {
        "H100": {"on_demand_hr": 2.50, "peak_bw_tbs": 3.35, "hbm_gb": 80},
        "A100": {"on_demand_hr": 1.79, "peak_bw_tbs": 2.00, "hbm_gb": 80},
        "A10G": {"on_demand_hr": 1.00, "peak_bw_tbs": 0.60, "hbm_gb": 24},
        "L4":   {"on_demand_hr": 0.80, "peak_bw_tbs": 0.30, "hbm_gb": 24},
    }

    # Dollars per GB VRAM
    vram_cost_h100 = metrics.dollars_per_gb_vram(2.50, 80)
    assert abs(vram_cost_h100 - 0.03125) < 1e-6
    assert metrics.dollars_per_gb_vram(1.0, 0) == 0.0

    # Right-sizing an underutilized GPU where achieved bandwidth is low (e.g. 0.4 TB/s on H100)
    # Needed bandwidth with 1.25x headroom = 0.50 TB/s -> fits on A10G (0.60 TB/s) or A100 (2.0 TB/s)
    # Cheapest fit is A10G ($1.00/hr vs $2.50/hr H100 -> 60% savings)
    rec = metrics.recommend_mbu_rightsizing(achieved_bw_tbs=0.4, current_gpu="H100", catalog=catalog)
    assert rec["recommended_gpu"] == "A10G"
    assert rec["recommended_price"] == 1.00
    assert rec["savings_pct"] == 60.0


def test_carbon_aware_schedule():
    # Test shifting 1,000 kWh from us-east-1 (380 g/kWh) to europe-north1 (30 g/kWh)
    res = sustainability.carbon_aware_schedule(total_kwh=1000.0, current_region="us-east-1", target_region="europe-north1")
    assert res["current_carbon_kg"] == 380.0
    assert res["target_carbon_kg"] == 30.0
    assert res["carbon_saved_kg"] == 350.0
    assert abs(res["carbon_reduction_pct"] - 92.1) < 0.1
    assert res["current_elec_cost_usd"] == 120.0
    assert res["target_elec_cost_usd"] == 90.0
    assert res["elec_cost_saved_usd"] == 30.0


def test_reasoning_energy_and_cost():
    # 1000 tokens reasoning vs non-reasoning
    normal_wh = sustainability.wh_per_query(1000, is_reasoning=False)
    reasoning_wh = sustainability.wh_per_query(1000, is_reasoning=True)
    assert abs(reasoning_wh - normal_wh * 80.0) < 1e-6
