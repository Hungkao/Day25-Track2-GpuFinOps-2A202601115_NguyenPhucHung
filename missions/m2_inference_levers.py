"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # Extension 4 tracking: reasoning vs non-reasoning
    reasoning_reqs = reasoning_tokens = 0
    reasoning_cost = non_reasoning_cost = 0.0
    reasoning_wh = non_reasoning_wh = 0.0

    # Extension 3 tracking: cache statistics
    cached_req_count = 0
    total_cached_tokens = 0
    total_input_tokens = 0

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        total_input_tokens += inp
        total_cached_tokens += cached
        if cached > 0:
            cached_req_count += 1

        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        req_base = pricing.request_cost(inp, out, lin, lout)
        base_cost += req_base

        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        req_opt = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += req_opt

        # Energy consumption per request
        req_wh = sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)

        if is_reasoning:
            reasoning_reqs += 1
            reasoning_tokens += (inp + out)
            reasoning_cost += req_opt
            reasoning_wh += req_wh
        else:
            non_reasoning_cost += req_opt
            non_reasoning_wh += req_wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # Extension 3 economics
    cache_worth_it = pricing.cache_is_worth_it(
        avg_cache_reads=3.5,
        write_cost_per_m=0.25,
        read_discount=0.10,
        base_input_price_per_m=3.00,
    )
    cache_be_reads = pricing.cache_break_even_reads(0.25, 3.00, 0.10)

    # Extension 4 reasoning breakdown
    n_requests = len(rows)
    reasoning_req_pct = (reasoning_reqs / n_requests * 100) if n_requests else 0.0
    reasoning_cost_pct = (reasoning_cost / opt_cost * 100) if opt_cost else 0.0
    reasoning_wh_pct = (reasoning_wh / (reasoning_wh + non_reasoning_wh) * 100) if (reasoning_wh + non_reasoning_wh) else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        print("\n[Extension 3] Prompt Caching Economics:")
        print(f"  Cached requests: {cached_req_count}/{n_requests} ({cached_req_count/n_requests:.1%})")
        print(f"  Cached tokens: {total_cached_tokens:,} / {total_input_tokens:,} input tokens ({total_cached_tokens/total_input_tokens:.1%})")
        print(f"  Cache break-even threshold: {cache_be_reads:.2f} reads (Current policy worth it: {cache_worth_it})")

        print("\n[Extension 4] Reasoning Token Budget Analysis:")
        print(f"  Reasoning traffic: {reasoning_reqs} requests ({reasoning_req_pct:.1f}% of total)")
        print(f"  Reasoning cost   : ${reasoning_cost:,.2f}/day ({reasoning_cost_pct:.1f}% of optimized bill)")
        print(f"  Reasoning energy : {reasoning_wh:,.1f} Wh/day ({reasoning_wh_pct:.1f}% of inference energy)")
        print(f"  Recommendation   : Implement confidence threshold routing -> only trigger reasoning when confidence < 0.85.")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_analysis": {
            "reasoning_reqs": reasoning_reqs,
            "reasoning_cost_daily": round(reasoning_cost, 2),
            "reasoning_cost_pct": round(reasoning_cost_pct, 1),
            "reasoning_wh_daily": round(reasoning_wh, 1),
            "reasoning_wh_pct": round(reasoning_wh_pct, 1),
        },
        "cache_analysis": {
            "cached_tokens": total_cached_tokens,
            "cache_worth_it": cache_worth_it,
            "break_even_reads": round(cache_be_reads, 2),
        }
    }


if __name__ == "__main__":
    run()

