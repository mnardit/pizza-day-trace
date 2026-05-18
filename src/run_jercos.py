"""
Deposit history of the pizza recipient address.

Address: 17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ

Mempool reports:
  - funded_txo_count = 14 (the address received 14 times)
  - spent_txo_count = 1 (the famous 10K-BTC spend; everything else is unspent)
  - the other 13 inbound UTXOs are post-2010 dust deposits — some on May-22
    anniversaries — that have never been moved.

For each deposit we record: tx, block_height, block_time, value, sender(s), and
heuristic flags for symbolic amounts (e.g. 546-sat P2PKH dust-limit deposits,
deposits that landed on May 22).

Outputs:
  data/processed/jercos-deposits.csv
  data/processed/jercos-summary.json
"""

import csv
import datetime as dt
import json
from pathlib import Path

from .explorer import Explorer
from .tracer import SATOSHI

JERCOS_ADDR = "17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ"
ANCHOR_TXID = "a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d"

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    explorer = Explorer()
    addr_info = explorer.address(JERCOS_ADDR)
    txs = explorer.address_all_txs(JERCOS_ADDR)

    deposits = []
    for tx in txs:
        # Find outputs going to JERCOS_ADDR
        for i, vout in enumerate(tx.get("vout", [])):
            if vout.get("scriptpubkey_address") != JERCOS_ADDR:
                continue
            value_sats = vout["value"]
            senders = sorted({
                vin.get("prevout", {}).get("scriptpubkey_address")
                for vin in tx.get("vin", [])
                if vin.get("prevout", {}).get("scriptpubkey_address")
            })
            bt = tx["status"].get("block_time")
            bh = tx["status"].get("block_height")
            date_utc = dt.datetime.fromtimestamp(bt, dt.UTC).isoformat() if bt else None

            # Symbolic-amount heuristics
            symbolic = []
            if value_sats == 522:
                symbolic.append("522 sats (May 22 reference)")
            if str(value_sats).startswith("522"):
                symbolic.append(f"begins with 522: {value_sats}")
            if value_sats in (1_000, 10_000, 100_000):
                symbolic.append(f"round dust: {value_sats}")
            if bt:
                d = dt.datetime.fromtimestamp(bt, dt.UTC)
                if d.month == 5 and d.day == 22:
                    symbolic.append(f"sent on May 22 ({d.year})")

            deposits.append({
                "txid": tx["txid"],
                "vout": i,
                "block_height": bh,
                "block_time": bt,
                "date_utc": date_utc,
                "value_sats": value_sats,
                "value_btc": value_sats / SATOSHI,
                "is_anchor_tx": tx["txid"] == ANCHOR_TXID,
                "senders": "|".join(senders) if senders else "",
                "n_senders": len(senders),
                "symbolic_notes": "; ".join(symbolic),
            })

    # Sort chronologically
    deposits.sort(key=lambda d: d["block_height"] or 0)

    # Confirm which deposits are still unspent
    outspends_all = []
    for d in deposits:
        outspends = explorer.tx_outspends(d["txid"])
        spent = outspends[d["vout"]].get("spent", False)
        outspends_all.append({**d, "spent": spent})

    out_csv = PROCESSED / "jercos-deposits.csv"
    fields = list(outspends_all[0].keys()) if outspends_all else []
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(outspends_all)

    n_unspent = sum(1 for o in outspends_all if not o["spent"])
    n_spent = sum(1 for o in outspends_all if o["spent"])
    total_dust_sats = sum(o["value_sats"] for o in outspends_all if not o["spent"])

    # Group dust by year (excluding anchor)
    by_year = {}
    for o in outspends_all:
        if o["is_anchor_tx"]:
            continue
        if not o.get("date_utc"):
            continue
        y = o["date_utc"][:4]
        by_year.setdefault(y, []).append(o)

    by_year_summary = {
        y: {
            "n_deposits": len(deps),
            "total_value_sats": sum(d["value_sats"] for d in deps),
            "total_value_btc": sum(d["value_sats"] for d in deps) / SATOSHI,
            "smallest_sats": min(d["value_sats"] for d in deps),
            "largest_sats": max(d["value_sats"] for d in deps),
        }
        for y, deps in sorted(by_year.items())
    }

    summary = {
        "address": JERCOS_ADDR,
        "address_funded_txo_count": addr_info["chain_stats"]["funded_txo_count"],
        "address_spent_txo_count": addr_info["chain_stats"]["spent_txo_count"],
        "address_funded_sats": addr_info["chain_stats"]["funded_txo_sum"],
        "address_funded_btc": addr_info["chain_stats"]["funded_txo_sum"] / SATOSHI,
        "n_deposits_total": len(deposits),
        "n_deposits_unspent": n_unspent,
        "n_deposits_spent": n_spent,
        "total_unspent_dust_sats": total_dust_sats,
        "total_unspent_dust_btc": total_dust_sats / SATOSHI,
        "by_year": by_year_summary,
    }

    out_json = PROCESSED / "jercos-summary.json"
    with out_json.open("w") as f:
        json.dump(summary, f, indent=2)

    print(f"wrote {out_csv} ({len(deposits)} deposits)")
    print(f"wrote {out_json}")
    print("\njercos summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
