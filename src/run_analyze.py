"""
Aggregate analysis: build a final summary.json that ties together the trace,
anchor inputs, jercos deposits, depth-5 frontier outspend status, and the
depth-3 consolidation address's full history into article-ready metrics.

Outputs:
  data/processed/headline-summary.json
"""

import csv
import datetime as dt
import json
from pathlib import Path

from .explorer import Explorer
from .tracer import SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
CONSOLIDATION_ADDR = "1PrwYMffhu1XJyVXs6Ba67NidGZVjbGHCq"


def _check_frontier_outspends(explorer: Explorer, tree_rows: list[dict]) -> list[dict]:
    out = []
    for r in tree_rows:
        if r["terminal"] != "depth-pruned":
            continue
        outspends = explorer.tx_outspends(r["txid"])
        vout = int(r["vout"])
        if vout >= len(outspends):
            status = "not-found"
            spent_in = None
            spent_block = None
        else:
            os = outspends[vout]
            if os.get("spent"):
                status = "spent-beyond-horizon"
                spent_in = os.get("txid")
                spent_block = (os.get("status") or {}).get("block_height")
            else:
                status = "still-unspent-today"
                spent_in = None
                spent_block = None
        out.append({
            "node_id": int(r["id"]),
            "txid": r["txid"],
            "vout": vout,
            "address": r["address"],
            "amount_btc": int(r["amount_sats"]) / SATOSHI,
            "taint_btc": int(r["taint_sats"]) / SATOSHI,
            "frontier_status": status,
            "spent_in_tx": spent_in,
            "spent_at_block": spent_block,
        })
    return out


def _consolidation_address_history(explorer: Explorer) -> dict:
    info = explorer.address(CONSOLIDATION_ADDR)
    txs = explorer.address_all_txs(CONSOLIDATION_ADDR)
    # Sort by (block_height, in-block position) — a tx cannot spend an output that
    # appears later in the same block, so position breaks block-time ties correctly.
    txs_with_pos = []
    for tx in txs:
        bh = tx["status"].get("block_height") or 0
        pos = explorer.tx_position_in_block(tx["txid"], bh) if bh else 0
        txs_with_pos.append((bh, pos, tx))
    txs_with_pos.sort(key=lambda x: (x[0], x[1]))
    history = []
    for bh, pos, tx in txs_with_pos:
        bt = tx["status"].get("block_time")
        date_iso = dt.datetime.fromtimestamp(bt, dt.UTC).isoformat() if bt else None
        inputs_val_by_addr = sum(
            v.get("prevout", {}).get("value", 0)
            for v in tx.get("vin", [])
            if v.get("prevout", {}).get("scriptpubkey_address") == CONSOLIDATION_ADDR
        )
        outputs_val_by_addr = sum(
            v["value"]
            for v in tx.get("vout", [])
            if v.get("scriptpubkey_address") == CONSOLIDATION_ADDR
        )
        # Counterparties: addresses on the other side of this tx
        if inputs_val_by_addr > 0:
            role = "spend"
            amount = inputs_val_by_addr
            counterparties = sorted({
                v.get("scriptpubkey_address")
                for v in tx.get("vout", [])
                if v.get("scriptpubkey_address") and v.get("scriptpubkey_address") != CONSOLIDATION_ADDR
            })
        else:
            role = "receive"
            amount = outputs_val_by_addr
            counterparties = sorted({
                v.get("prevout", {}).get("scriptpubkey_address")
                for v in tx.get("vin", [])
                if v.get("prevout", {}).get("scriptpubkey_address")
                and v.get("prevout", {}).get("scriptpubkey_address") != CONSOLIDATION_ADDR
            })
        fee_sats = (
            sum(v.get("prevout", {}).get("value", 0) for v in tx.get("vin", []))
            - sum(v["value"] for v in tx.get("vout", []))
        )
        history.append({
            "txid": tx["txid"],
            "block_height": bh,
            "block_position": pos,
            "date_utc": date_iso,
            "role": role,
            "amount_btc": amount / SATOSHI,
            "n_inputs": len(tx.get("vin", [])),
            "n_outputs": len(tx.get("vout", [])),
            "fee_btc": fee_sats / SATOSHI,
            "counterparties": counterparties,
        })
    return {
        "address": CONSOLIDATION_ADDR,
        "lifetime_tx_count": info["chain_stats"]["tx_count"],
        "funded_txo_count": info["chain_stats"]["funded_txo_count"],
        "spent_txo_count": info["chain_stats"]["spent_txo_count"],
        "total_received_btc": info["chain_stats"]["funded_txo_sum"] / SATOSHI,
        "total_spent_btc": info["chain_stats"]["spent_txo_sum"] / SATOSHI,
        "current_balance_btc": (
            info["chain_stats"]["funded_txo_sum"] - info["chain_stats"]["spent_txo_sum"]
        ) / SATOSHI,
        "history": history,
    }


def _provenance() -> dict:
    """Minimum reproducibility manifest baked into headline-summary.json."""
    import subprocess
    import sys

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent.parent
        ).decode().strip()
    except Exception:
        commit = None
    return {
        "repo_commit_sha": commit,
        "python_version": sys.version.split()[0],
    }


def main():
    explorer = Explorer()
    tree = list(csv.DictReader((PROCESSED / "utxo-tree.csv").open()))
    inputs = list(csv.DictReader((PROCESSED / "anchor-inputs.csv").open()))
    deposits = list(csv.DictReader((PROCESSED / "jercos-deposits.csv").open()))

    trace_summary = json.load((PROCESSED / "summary.json").open())
    anchor_summary = json.load((PROCESSED / "anchor-summary.json").open())
    jercos_summary = json.load((PROCESSED / "jercos-summary.json").open())
    conventions = json.loads(
        (PROCESSED / "conventions-comparison.json").read_text()
    ) if (PROCESSED / "conventions-comparison.json").exists() else None

    chain_tip = explorer.chain_tip()
    chain_tip_height = chain_tip if isinstance(chain_tip, int) else int(chain_tip)
    provenance = _provenance()

    consolidation_node = next(
        (n for n in tree if int(n["depth"]) == 3 and int(n["taint_sats"]) == 10_000 * SATOSHI),
        None,
    )

    consolidation_summary = {
        "consolidation_event_node": None,
        "consolidation_address_history": _consolidation_address_history(explorer),
    }
    if consolidation_node:
        consolidation_summary["consolidation_event_node"] = {
            "depth": int(consolidation_node["depth"]),
            "tx": consolidation_node["txid"],
            "address": consolidation_node["address"],
            "consolidated_amount_btc": int(consolidation_node["amount_sats"]) / SATOSHI,
            "tainted_portion_btc": int(consolidation_node["taint_sats"]) / SATOSHI,
            "non_pizza_portion_btc": (
                (int(consolidation_node["amount_sats"]) - int(consolidation_node["taint_sats"]))
                / SATOSHI
            ),
            "block_height": int(consolidation_node["block_height"]),
            "block_time": int(consolidation_node["block_time"]),
            "block_time_iso": dt.datetime.fromtimestamp(
                int(consolidation_node["block_time"]), dt.UTC
            ).isoformat(),
            "days_after_anchor": round(
                (int(consolidation_node["block_time"]) - 1274552191) / 86400, 2
            ),
        }

    frontier = _check_frontier_outspends(explorer, tree)

    may22_anniversary_deposits = [
        d for d in deposits
        if d["date_utc"]
        and d["date_utc"][5:10] == "05-22"
        and d["is_anchor_tx"] != "True"
    ]
    dust_546 = [d for d in deposits if int(d["value_sats"]) == 546]

    fee_sats = sum(int(r["value_sats"]) for r in inputs) - 10000 * SATOSHI

    # Address-overlap finding: 18ZChqRsb7eKgH8wLg9Pfkkezux34pf6eo appears both as
    # a node in the descendant tree (node 3, the 5,777 BTC half after the first
    # re-shuffle) and as a counterparty in 3 of the 4 lifetime transactions of
    # the consolidation address. We surface it because it ties multiple addresses
    # to the same likely actor without invoking external clustering heuristics.
    linked_addr = "18ZChqRsb7eKgH8wLg9Pfkkezux34pf6eo"
    linked_addr_in_tree = any(r["address"] == linked_addr for r in tree)
    linked_addr_in_consol = sum(
        1 for h in consolidation_summary["consolidation_address_history"]["history"]
        if linked_addr in h["counterparties"]
    )

    out = {
        "chain_tip_at_trace_time": chain_tip_height,
        "provenance": provenance,
        "conventions_comparison": conventions,
        "anchor": {
            "txid": "a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d",
            "block_height": anchor_summary["anchor_height"],
            "block_time_utc_iso": "2010-05-22T18:16:31Z",
            "block_time_unix": anchor_summary["anchor_time"],
            "fee_sats": fee_sats,
            "fee_btc": fee_sats / SATOSHI,
            "n_inputs": anchor_summary["n_inputs"],
            "n_inputs_0_01_btc_crumbs": anchor_summary["n_inputs_0_01_btc_crumbs"],
            "largest_input_btc": anchor_summary["largest_input_btc"],
            "largest_input_age_days_at_spend": anchor_summary["largest_input_age_days"],
            "oldest_input_age_days_at_spend": anchor_summary["oldest_input_age_days"],
            "mean_input_age_days": anchor_summary["mean_age_days"],
            "recipient": "17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ",
        },
        "trace": {
            "convention": "strict positional FIFO with 1 BTC dust pruning and 100-input cluster termination",
            "max_depth_traced": trace_summary.get("max_depth_reached"),
            "n_nodes": trace_summary["n_nodes"],
            "n_unique_addresses": trace_summary["n_unique_addresses"],
            "n_unique_txs": trace_summary["n_unique_txs_in_tree"],
            "terminal_attributed_taint_btc": trace_summary["terminal_attributed_taint_btc"],
            "conserves_anchor_taint": trace_summary["conserves_anchor_taint"],
            "by_terminal_btc": trace_summary["by_terminal_btc"],
            "depth_pruning_horizon": True,
        },
        "consolidation": consolidation_summary,
        "depth_horizon_frontier": frontier,
        "jercos_address": {
            "address": jercos_summary["address"],
            "funded_txo_count": jercos_summary["address_funded_txo_count"],
            "spent_txo_count": jercos_summary["address_spent_txo_count"],
            "total_funded_btc": jercos_summary["address_funded_btc"],
            "n_apparent_deposits_unspent": jercos_summary["n_deposits_unspent"],
            "total_unspent_dust_btc": jercos_summary["total_unspent_dust_btc"],
            "anniversary_deposits_may22": [
                {"date": t["date_utc"][:10], "value_sats": int(t["value_sats"])}
                for t in may22_anniversary_deposits
            ],
            "deposits_at_546_sats": len(dust_546),
            "deposits_by_year": jercos_summary["by_year"],
        },
        "linked_address_signal": {
            "address": linked_addr,
            "appears_as_descendant_node": linked_addr_in_tree,
            "consolidation_counterparty_appearances": linked_addr_in_consol,
            "note": (
                "This address is both the depth-2 successor of the 5,777 BTC pizza "
                "half and a counterparty to 3 of the 4 lifetime transactions of the "
                "consolidation address. The chain-only evidence is consistent with a "
                "single actor controlling both addresses; we do not invoke external "
                "clustering heuristics to make that claim."
            ),
        },
        "headline_findings": [
            f"The famous Pizza Day transaction itself paid {fee_sats / SATOSHI:.2f} BTC in fees — rarely foregrounded in the coverage surveyed in analysis/prior-art.md.",
            f"Of 131 inputs, {anchor_summary['n_inputs_0_01_btc_crumbs']} were 0.01 BTC \"crumbs\" — typical of consolidated mining residue, not coinbase outputs directly.",
            f"Largest single input was {anchor_summary['largest_input_btc']} BTC, only {anchor_summary['largest_input_age_days']} days old at the moment of spending.",
            "The two FIFO-tainted branches that fed the 2010-07-07 02:56 UTC consolidation had each been dormant for about 45 days by then. They were then consolidated, in a single transaction, with 18 other UTXOs of non-pizza-tainted provenance under this convention, into one 11,022 BTC output at 1PrwYMffhu1XJyVXs6Ba67NidGZVjbGHCq.",
            "That consolidation address has only 4 lifetime transactions, all in May–July 2010, and a zero balance today — a one-off transit point, not an exchange wallet.",
            f"At the depth-5 horizon, all 10,000 BTC of pizza taint sits in 3 frontier UTXOs. The trace stops there by convention; their next-hop status is reported separately in `depth_horizon_frontier`.",
            f"The recipient address 17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ has been funded {jercos_summary['address_funded_txo_count']} times in its life but spent only once — the famous 10K-BTC pizza payment. The other {jercos_summary['n_deposits_unspent']} deposits are unspent dust; some land on May-22 anniversaries.",
            f"Two of the apparent anniversary deposits (2023-05-22 and 2024-05-22) are exactly 546 satoshis — the Bitcoin Core relay default dust threshold for P2PKH — among the smallest deposits a standard wallet will broadcast.",
            f"Address {linked_addr} appears both as the depth-2 successor of the 5,777 BTC pizza half and as a counterparty in 3 of 4 lifetime transactions of the consolidation address — chain-only evidence consistent with a single actor controlling both, though we do not invoke external clustering heuristics to confirm.",
        ],
    }

    out_path = PROCESSED / "headline-summary.json"
    with out_path.open("w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"wrote {out_path}")
    print()
    print("headline findings:")
    for i, h in enumerate(out["headline_findings"]):
        print(f"  {i + 1}. {h}")
    print()
    print("depth-horizon frontier status:")
    for f in frontier:
        print(f"  node {f['node_id']} {f['address']} {f['taint_btc']:.2f} BTC tainted → {f['frontier_status']}")


if __name__ == "__main__":
    main()
