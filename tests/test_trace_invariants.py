"""Sanity invariants on the committed trace dataset."""

import csv
from pathlib import Path

from src.tracer import SATOSHI

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def _load_tree():
    with (PROCESSED / "utxo-tree.csv").open() as f:
        return list(csv.DictReader(f))


def test_tree_is_present():
    rows = _load_tree()
    assert len(rows) > 0
    assert rows[0]["id"] == "0"
    assert int(rows[0]["depth"]) == 0
    assert int(rows[0]["taint_sats"]) == 10_000 * SATOSHI


def test_taint_conservation_at_terminals():
    rows = _load_tree()
    terminal_taint = sum(int(r["taint_sats"]) for r in rows if r["terminal"])
    # All taint must be accounted for at some terminal bucket
    assert terminal_taint == 10_000 * SATOSHI


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
