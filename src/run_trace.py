"""CLI entry point: run a trace and dump results to data/processed/."""

import argparse
import csv
import json
from pathlib import Path

from .explorer import Explorer
from .tracer import Tracer, ANCHOR_TXID, ANCHOR_VOUT, SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--dust-btc", type=float, default=1.0)
    ap.add_argument("--cluster-threshold", type=int, default=100)
    ap.add_argument("--txid", default=ANCHOR_TXID)
    ap.add_argument("--vout", type=int, default=ANCHOR_VOUT)
    ap.add_argument("--out-suffix", default="")
    ap.add_argument("--convention", choices=["fifo", "haircut", "poison"], default="fifo")
    args = ap.parse_args()

    PROCESSED.mkdir(parents=True, exist_ok=True)

    explorer = Explorer()
    tracer = Tracer(
        explorer,
        max_depth=args.depth,
        dust_sats=int(args.dust_btc * SATOSHI),
        cluster_threshold=args.cluster_threshold,
        convention=args.convention,
    )

    print(f"tracing from {args.txid}:{args.vout} depth={args.depth} dust={args.dust_btc} BTC convention={args.convention}")
    nodes = tracer.trace(args.txid, args.vout)
    summary = tracer.summary()

    suffix = args.out_suffix
    tree_path = PROCESSED / f"utxo-tree{suffix}.csv"
    summary_path = PROCESSED / f"summary{suffix}.json"

    fields = [
        "id", "depth", "parents", "txid", "vout", "address", "scriptpubkey_type",
        "amount_sats", "taint_sats", "block_height", "block_time",
        "terminal", "spent_in_tx", "spent_at_block", "spent_at_time",
        "dormancy_days", "cluster_input_count",
    ]
    with tree_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in tracer.to_rows():
            w.writerow(row)

    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nwrote {tree_path} ({len(nodes)} nodes)")
    print(f"wrote {summary_path}")
    print("\nsummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
