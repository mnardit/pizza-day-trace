"""
Anchor tx input composition analysis.

The pizza tx has 131 inputs, all from Hanyecz's address `1XPTgDRhN8RFnzniWCddobD9iKZatrvH4`.
For each input, we look up the UTXO it came from to get:
  - original creation block & timestamp (when Hanyecz received it)
  - age at time of spending (how many days Hanyecz held it before paying for pizza)
  - whether the originating tx was a coinbase (mining reward)

Outputs:
  data/processed/anchor-inputs.csv
  data/processed/anchor-summary.json
"""

import csv
import json
from collections import Counter
from pathlib import Path

from .explorer import Explorer
from .tracer import ANCHOR_TXID, SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    explorer = Explorer()
    anchor = explorer.tx(ANCHOR_TXID)
    anchor_time = anchor["status"]["block_time"]
    anchor_height = anchor["status"]["block_height"]

    rows = []
    for i, vin in enumerate(anchor["vin"]):
        prev_txid = vin.get("txid")
        prev_vout = vin.get("vout")
        prev_value = vin.get("prevout", {}).get("value", 0)
        prev_addr = vin.get("prevout", {}).get("scriptpubkey_address")

        # Fetch source tx to get its creation timestamp and coinbase flag
        prev_tx = explorer.tx(prev_txid)
        prev_block_time = prev_tx["status"].get("block_time")
        prev_block_height = prev_tx["status"].get("block_height")
        is_coinbase = bool(prev_tx.get("vin", [{}])[0].get("is_coinbase", False))

        age_days = None
        if prev_block_time and anchor_time:
            age_days = round((anchor_time - prev_block_time) / 86400, 2)

        rows.append({
            "input_idx": i,
            "prev_txid": prev_txid,
            "prev_vout": prev_vout,
            "prev_address": prev_addr,
            "value_sats": prev_value,
            "value_btc": prev_value / SATOSHI,
            "prev_block_height": prev_block_height,
            "prev_block_time": prev_block_time,
            "is_coinbase": is_coinbase,
            "age_days_at_spend": age_days,
        })

    # Sort by chronology for narrative timeline (oldest first)
    rows_chrono = sorted(rows, key=lambda r: r["prev_block_height"] or 0)

    out_csv = PROCESSED / "anchor-inputs.csv"
    fields = list(rows[0].keys())
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_chrono)

    # Summary stats
    n = len(rows)
    n_coinbase = sum(1 for r in rows if r["is_coinbase"])
    n_dust = sum(1 for r in rows if r["value_sats"] == 1_000_000)  # 0.01 BTC
    total_btc = sum(r["value_sats"] for r in rows) / SATOSHI

    # Value buckets
    buckets = Counter()
    for r in rows:
        v = r["value_btc"]
        if v == 0.01:
            buckets["0.01 BTC"] += 1
        elif v < 1:
            buckets["<1 BTC"] += 1
        elif v < 50:
            buckets["1-50 BTC"] += 1
        elif v == 50:
            buckets["exactly 50 BTC"] += 1
        elif v < 100:
            buckets["50-100 BTC"] += 1
        elif v < 200:
            buckets["100-200 BTC"] += 1
        elif v < 500:
            buckets["200-500 BTC"] += 1
        elif v < 1000:
            buckets["500-1000 BTC"] += 1
        else:
            buckets[">=1000 BTC"] += 1

    # Largest single input
    largest = max(rows, key=lambda r: r["value_sats"])
    # Oldest input (longest accumulation)
    oldest = max(rows, key=lambda r: r["age_days_at_spend"] or 0)

    # Age distribution
    ages = [r["age_days_at_spend"] for r in rows if r["age_days_at_spend"] is not None]
    summary = {
        "n_inputs": n,
        "n_inputs_coinbase_direct": n_coinbase,
        "n_inputs_0_01_btc_crumbs": n_dust,
        "n_inputs_exactly_50_btc": buckets.get("exactly 50 BTC", 0),
        "total_value_btc": total_btc,
        "buckets": dict(buckets),
        "anchor_height": anchor_height,
        "anchor_time": anchor_time,
        "largest_input_btc": largest["value_btc"],
        "largest_input_age_days": largest["age_days_at_spend"],
        "oldest_input_age_days": oldest["age_days_at_spend"],
        "oldest_input_btc": oldest["value_btc"],
        "median_age_days": sorted(ages)[len(ages) // 2] if ages else None,
        "mean_age_days": round(sum(ages) / len(ages), 2) if ages else None,
    }

    out_json = PROCESSED / "anchor-summary.json"
    with out_json.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"wrote {out_csv} ({n} inputs)")
    print(f"wrote {out_json}")
    print("\nanchor summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
