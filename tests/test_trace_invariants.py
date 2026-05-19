"""Sanity invariants on the committed trace dataset."""

import csv
import json
from pathlib import Path

from src.tracer import SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def _load_tree():
    with (PROCESSED / "utxo-tree.csv").open() as f:
        return list(csv.DictReader(f))


def _load_summary():
    with (PROCESSED / "headline-summary.json").open() as f:
        return json.load(f)


def test_tree_is_present():
    rows = _load_tree()
    assert len(rows) > 0
    assert rows[0]["id"] == "0"
    assert int(rows[0]["depth"]) == 0
    assert int(rows[0]["taint_sats"]) == 10_000 * SATOSHI


def test_taint_conservation_at_terminals_in_tree():
    """In-tree terminal-row sum equals anchor taint on this dataset.

    Holds because the canonical Pizza-Day FIFO trace has zero fee-absorbed
    taint (the depth-3 consolidation tx paid zero fee). On other datasets
    or under haircut on non-zero-fee data this would not hold by itself
    — use ``test_taint_conservation_algorithmic`` for the convention-agnostic
    invariant.
    """
    rows = _load_tree()
    terminal_taint = sum(int(r["taint_sats"]) for r in rows if r["terminal"])
    assert terminal_taint == 10_000 * SATOSHI


def test_taint_conservation_algorithmic():
    """The fee-absorbed bucket plus in-tree terminals must equal anchor taint.

    This is the algorithmic invariant the tracer guarantees for FIFO and
    haircut. The fee bucket is recorded outside the CSV (it has no
    corresponding UTXO node) so we pull it from the summary sidecar.
    """
    rows = _load_tree()
    summary = _load_summary()
    fifo_row = next(
        r for r in summary["conventions_comparison"]["rows"]
        if r["convention"] == "fifo"
    )
    fee_taint_btc = fifo_row["fee_or_residual_btc"]
    terminal_taint_sats = sum(int(r["taint_sats"]) for r in rows if r["terminal"])
    terminal_taint_btc = terminal_taint_sats / SATOSHI
    assert abs((terminal_taint_btc + fee_taint_btc) - 10_000) < 1e-8
    assert fifo_row["conserves_anchor_taint"] is True


def test_poison_documented_as_non_conserving():
    """Poison must be explicitly flagged as non-conserving in the summary."""
    summary = _load_summary()
    poison_row = next(
        r for r in summary["conventions_comparison"]["rows"]
        if r["convention"] == "poison"
    )
    assert poison_row["conserves_anchor_taint"] is False
    assert poison_row["horizon_tainted_btc"] > 10_000


def test_no_taint_exceeds_value():
    rows = _load_tree()
    for r in rows:
        assert int(r["taint_sats"]) <= int(r["amount_sats"]), (
            f"node {r['id']} has taint > amount: {r}"
        )


def test_anchor_has_jercos_recipient():
    rows = _load_tree()
    assert rows[0]["address"] == "17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ"


def test_depth_horizon_respected():
    rows = _load_tree()
    for r in rows:
        assert int(r["depth"]) <= 5
