"""
Run the trace under three taint conventions (FIFO / haircut / poison) and emit
a single comparison table for the article and the paper.

Outputs:
  data/processed/conventions-comparison.json
"""

import json
from pathlib import Path

from .explorer import Explorer
from .tracer import Tracer, ANCHOR_TXID, ANCHOR_VOUT, SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def run_one(convention: str) -> dict:
    explorer = Explorer()
    tracer = Tracer(explorer, max_depth=5, convention=convention)
    tracer.trace(ANCHOR_TXID, ANCHOR_VOUT)
    s = tracer.summary()

    # Largest tainted node at depth 5 (the "surviving frontier" headline)
    horizon_nodes = [n for n in tracer.nodes if n.terminal == "depth-pruned"]
    horizon_nodes.sort(key=lambda n: n.taint_sats, reverse=True)
    largest = horizon_nodes[0] if horizon_nodes else None

    horizon_total_sats = sum(n.taint_sats for n in horizon_nodes)

    return {
        "convention": convention,
        "n_nodes": s["n_nodes"],
        "n_unique_txs": s["n_unique_txs_in_tree"],
        "max_depth": s["max_depth_reached"],
        "horizon_tainted_btc": horizon_total_sats / SATOSHI,
        "fee_or_residual_btc": s["fee_taint_btc"],
        "terminal_attributed_taint_btc": s["terminal_attributed_taint_btc"],
        "conserves_anchor_taint": s["conserves_anchor_taint"],
        "largest_horizon_node": {
            "address": largest.address if largest else None,
            "tainted_btc": (largest.taint_sats / SATOSHI) if largest else 0,
            "utxo_value_btc": (largest.amount_sats / SATOSHI) if largest else 0,
        } if largest else None,
        "interpretation_risk": {
            "fifo": "Conservative: only the strict positional prefix of each input flows to the next-positioned output. Per-output taint can be zero even if the tx has tainted inputs.",
            "haircut": "Proportional: every output receives a fraction of the input taint pool equal to its share of total output value. Rounding pennies go to the fee.",
            "poison": "Maximalist: any tainted input marks every output as fully tainted. Inflation grows as un-tainted inputs join descendant txs.",
        }[convention],
    }


def main():
    rows = [run_one(c) for c in ("fifo", "haircut", "poison")]
    fifo, haircut, poison = rows
    out = {
        "rows": rows,
        "delta_vs_fifo_btc": {
            "haircut": haircut["horizon_tainted_btc"] - fifo["horizon_tainted_btc"],
            "poison": poison["horizon_tainted_btc"] - fifo["horizon_tainted_btc"],
        },
        "topology_diverges_at_horizon": (
            fifo["n_nodes"] != haircut["n_nodes"]
            or fifo["n_nodes"] != poison["n_nodes"]
        ),
        "note": (
            "Topology (set of UTXOs visited) is identical across the three "
            "conventions for this dataset because the dust-pruning threshold "
            "(1 BTC) is below the smallest tainted amount under every "
            "convention. At a higher dust threshold, poison would visit "
            "additional descendants because of its inflation."
        ),
    }
    out_path = PROCESSED / "conventions-comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"wrote {out_path}")
    for r in rows:
        print(f"  {r['convention']:>8}: horizon={r['horizon_tainted_btc']:>10.4f} BTC  "
              f"residual={r['fee_or_residual_btc']:>6.8f}  nodes={r['n_nodes']}")


if __name__ == "__main__":
    main()
