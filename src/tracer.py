"""
Topological UTXO tracer with FIFO taint, dedup by (txid, vout), and explicit pruning.

Why topological order, not BFS-by-depth:
  Reconvergence means multiple "depth waves" can deposit taint into the same UTXO at
  different times in a BFS-by-depth scheme. The blockchain itself provides a natural
  topological ordering: a tx can only spend UTXOs from earlier blocks (and earlier
  positions within the same block). So we process spending transactions in
  (block_height, tx_position) order and each is processed exactly once with the full
  combined taint of its inputs.

Algorithm:
  1. Initialize: anchor UTXO is tainted at depth 0.
  2. Discover: from every currently-tainted UTXO that is spent, collect the spending tx.
  3. Sort the collected spending txs by block_height (and tx_position as tiebreaker).
  4. Process each tx in order:
     - Build per-input taint vector (sum of tainted UTXOs that match).
     - If tx has >= CLUSTER_THRESHOLD inputs, terminate the tainted inputs as cluster-absorbed.
     - Otherwise run FIFO. Output UTXOs with positive taint become new tainted UTXOs;
       their depth = max(depth of contributing inputs) + 1.
     - If depth >= MAX_DEPTH or taint < DUST_SATS, terminate appropriately.
  5. Loop until no new spending txs to process.

Caveats:
  - Reconvergence is handled natively because all tainted inputs to a tx are visible
    before that tx is processed, given the topological ordering.
  - Taint conservation across the whole tree is not proved by the algorithm. The
    `fifo_distribute` routine walks only the explicit outputs of each transaction;
    if strict FIFO assigned tainted satoshis to the implicit fee remainder of a
    descendant tx, that taint would be silently dropped rather than landing in a
    `fee` terminal bucket. The conservation check in `summary()` is an empirical
    invariant on the actual dataset, not a guarantee for arbitrary inputs.
"""

from collections import defaultdict
from dataclasses import dataclass, field

SATOSHI = 100_000_000
DUST_SATS = 1 * SATOSHI            # 1 BTC pruning threshold
CLUSTER_INPUT_THRESHOLD = 100      # treat as cluster

ANCHOR_TXID = "a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d"
ANCHOR_VOUT = 0


class Terminal:
    STILL_UNSPENT = "still-unspent"
    CLUSTER_ABSORBED = "cluster-absorbed"
    DUST_PRUNED = "dust-pruned"
    DEPTH_PRUNED = "depth-pruned"
    FEE_ABSORBED = "fee-absorbed"


Convention = str  # 'fifo' | 'haircut' | 'poison'


def distribute(vins, vouts, input_taints, convention: Convention = "fifo"):
    """
    Distribute taint from inputs to outputs under one of three conventions.

    All three return ``(output_taints, fee_taint)`` so the caller can record any
    taint attributed to the residual (fee) bucket.

    **Conservation is not uniform across conventions.**

    - **FIFO** conserves numeric input taint exactly:
      ``sum(output_taints) + fee_taint == sum(input_taints)``.
    - **Haircut** conserves numeric input taint modulo integer-satoshi
      rounding (residual sub-satoshi remainders are parked in ``fee_taint``).
    - **Poison** does **not** conserve numeric input taint. By design it
      attributes the full output value to every output of any transaction
      with at least one tainted input, even when the input taint is small.
      It is an upper-bound convention; the numeric taint output can exceed
      numeric taint input.

    Conventions:

    - **fifo** (strict positional). Each input is a value range whose first
      ``taint`` satoshis are tainted and the rest are clean. Outputs are filled
      left-to-right; for each input we donate its tainted portion first, then
      its clean portion. After all outputs are filled, anything still in the
      ``remaining`` cursor that was tainted lands in the fee.

    - **haircut** (proportional). The tainted fraction ``T/V`` of the inputs
      applies uniformly to every output and to the fee. Output ``i`` receives
      ``floor(vouts[i].value * T / V)``; the remainder lands in the fee.

    - **poison**. If any input is tainted, every output is fully tainted and
      the fee is fully tainted. Used as an outer-bound convention; never
      tighter than the truth.
    """
    if convention == "fifo":
        return _fifo_distribute(vins, vouts, input_taints)
    if convention == "haircut":
        return _haircut_distribute(vins, vouts, input_taints)
    if convention == "poison":
        return _poison_distribute(vins, vouts, input_taints)
    raise ValueError(f"unknown taint convention: {convention!r}")


def _fifo_distribute(vins, vouts, input_taints):
    output_taints = [0] * len(vouts)
    remaining = [
        {"clean": v["prevout"]["value"] - input_taints[i], "tainted": input_taints[i]}
        for i, v in enumerate(vins)
    ]
    cursor = 0
    for out_idx, vout in enumerate(vouts):
        need = vout["value"]
        while need > 0 and cursor < len(remaining):
            r = remaining[cursor]
            if r["tainted"] > 0:
                take = min(r["tainted"], need)
                output_taints[out_idx] += take
                r["tainted"] -= take
                need -= take
                if need == 0:
                    break
            if r["clean"] > 0:
                take = min(r["clean"], need)
                r["clean"] -= take
                need -= take
            if r["tainted"] == 0 and r["clean"] == 0:
                cursor += 1
    # Anything still tainted in the unconsumed tail of `remaining` is fee taint.
    fee_taint = sum(r["tainted"] for r in remaining[cursor:])
    return output_taints, fee_taint


def _haircut_distribute(vins, vouts, input_taints):
    total_in = sum(v["prevout"]["value"] for v in vins)
    total_taint = sum(input_taints)
    total_out = sum(v["value"] for v in vouts)
    output_taints = []
    distributed = 0
    if total_in == 0:
        return [0] * len(vouts), 0
    for vout in vouts:
        t = (total_taint * vout["value"]) // total_in
        output_taints.append(t)
        distributed += t
    fee_taint = total_taint - distributed
    # Sanity: fee_taint should equal floor(total_taint * fee / total_in).
    # Rounding leftovers caused by floor() also end up in fee_taint, which is
    # acceptable for a forensic upper-bound bucket (it never falsifies conservation).
    return output_taints, fee_taint


def _poison_distribute(vins, vouts, input_taints):
    has_taint = any(t > 0 for t in input_taints)
    if not has_taint:
        return [0] * len(vouts), 0
    # Poison: every output and the fee are fully tainted, regardless of the
    # numeric input taint. By convention we attribute output_value satoshis of
    # taint per output, plus fee_value satoshis to the fee.
    output_taints = [v["value"] for v in vouts]
    total_in = sum(v["prevout"]["value"] for v in vins)
    total_out = sum(v["value"] for v in vouts)
    fee = max(0, total_in - total_out)
    return output_taints, fee


# Back-compat shim: existing tests still use fifo_distribute() returning a list.
def fifo_distribute(vins, vouts, input_taints):
    """Legacy signature: returns only output_taints. New code should use ``distribute``."""
    output_taints, _fee = _fifo_distribute(vins, vouts, input_taints)
    return output_taints


@dataclass
class Node:
    id: int
    depth: int
    txid: str
    vout: int
    address: str | None
    scriptpubkey_type: str | None
    amount_sats: int
    taint_sats: int
    block_height: int | None
    block_time: int | None
    parents: list[int] = field(default_factory=list)
    terminal: str | None = None
    spent_in_tx: str | None = None
    spent_at_block: int | None = None
    spent_at_time: int | None = None
    dormancy_days: float | None = None
    cluster_input_count: int | None = None


class Tracer:
    def __init__(self, explorer, max_depth: int = 5,
                 dust_sats: int = DUST_SATS,
                 cluster_threshold: int = CLUSTER_INPUT_THRESHOLD,
                 convention: Convention = "fifo"):
        self.explorer = explorer
        self.max_depth = max_depth
        self.dust_sats = dust_sats
        self.cluster_threshold = cluster_threshold
        self.convention = convention
        self.nodes: list[Node] = []
        self.utxo_index: dict[tuple[str, int], int] = {}
        self.warnings: list[str] = []
        # Per-tx fee taint accumulated across the trace. Recorded so that
        # taint conservation is algorithmic rather than empirical.
        self.fee_taint_by_tx: dict[str, int] = {}
        self.total_fee_taint_sats: int = 0

    def _add_or_update_node(self, depth, txid, vout, vout_data,
                            amount_sats, taint_to_add, block_height, block_time,
                            parent_ids: list[int]):
        key = (txid, vout)
        if key in self.utxo_index:
            nid = self.utxo_index[key]
            n = self.nodes[nid]
            n.taint_sats += taint_to_add
            for p in parent_ids:
                if p not in n.parents:
                    n.parents.append(p)
            # Depth: take the minimum (shortest path to anchor)
            n.depth = min(n.depth, depth)
            return nid, False
        nid = len(self.nodes)
        n = Node(
            id=nid,
            depth=depth,
            txid=txid,
            vout=vout,
            address=vout_data.get("scriptpubkey_address") if vout_data else None,
            scriptpubkey_type=vout_data.get("scriptpubkey_type") if vout_data else None,
            amount_sats=amount_sats,
            taint_sats=taint_to_add,
            block_height=block_height,
            block_time=block_time,
            parents=list(parent_ids),
        )
        self.nodes.append(n)
        self.utxo_index[key] = nid
        return nid, True

    def trace(self, anchor_txid: str = ANCHOR_TXID, anchor_vout: int = ANCHOR_VOUT):
        anchor_tx = self.explorer.tx(anchor_txid)
        anchor_out = anchor_tx["vout"][anchor_vout]
        self._add_or_update_node(
            depth=0,
            txid=anchor_txid,
            vout=anchor_vout,
            vout_data=anchor_out,
            amount_sats=anchor_out["value"],
            taint_to_add=anchor_out["value"],
            block_height=anchor_tx["status"]["block_height"],
            block_time=anchor_tx["status"]["block_time"],
            parent_ids=[],
        )

        while True:
            pending = self._collect_pending_spends()
            if not pending:
                break
            # Sort by (block_height, in-block tx position). The position is the
            # authoritative same-block tiebreaker because Bitcoin only allows a tx
            # to spend earlier-positioned outputs from its own block.
            pending.sort(key=lambda t: (t[1], t[2]))
            for spend_txid, _height, _pos in pending:
                self._process_tx(spend_txid)

        # Mark remaining un-spent live nodes
        for n in self.nodes:
            if n.terminal is None:
                if n.spent_in_tx is None:
                    # never spent (or spent in a tx we didn't process due to depth)
                    if n.depth >= self.max_depth:
                        n.terminal = Terminal.DEPTH_PRUNED
                    else:
                        n.terminal = Terminal.STILL_UNSPENT
        self._compute_dormancy()
        return self.nodes

    def _collect_pending_spends(self) -> list[tuple[str, int, int]]:
        """Find spending txs of all currently-tainted, not-yet-terminal, not-yet-spent UTXOs.

        Returns: list of (spend_txid, block_height, in_block_position) tuples for
        deterministic topological sorting.
        """
        pending: dict[str, tuple[int, int]] = {}  # spend_txid -> (block_height, position)
        for n in self.nodes:
            if n.terminal is not None:
                continue
            if n.spent_in_tx is not None:
                continue
            if n.taint_sats < self.dust_sats:
                n.terminal = Terminal.DUST_PRUNED
                continue
            if n.depth >= self.max_depth:
                n.terminal = Terminal.DEPTH_PRUNED
                continue
            outspends = self.explorer.tx_outspends(n.txid)
            if n.vout >= len(outspends):
                n.terminal = Terminal.STILL_UNSPENT
                continue
            os = outspends[n.vout]
            if not os.get("spent"):
                n.terminal = Terminal.STILL_UNSPENT
                continue
            spend_txid = os["txid"]
            bh = os.get("status", {}).get("block_height") if isinstance(os.get("status"), dict) else None
            if bh is None:
                bh = self.explorer.tx(spend_txid)["status"].get("block_height", 0)
            pos = self.explorer.tx_position_in_block(spend_txid, bh)
            if spend_txid not in pending:
                pending[spend_txid] = (bh, pos)
        return [(txid, bh, pos) for txid, (bh, pos) in pending.items()]

    def _process_tx(self, spend_txid: str):
        spend_tx = self.explorer.tx(spend_txid)
        vins = spend_tx.get("vin", [])
        vouts = spend_tx.get("vout", [])
        block_height = spend_tx["status"].get("block_height")
        block_time = spend_tx["status"].get("block_time")

        # Identify tainted inputs
        input_taints = [0] * len(vins)
        matched_parents: list[int] = []
        parent_depths: list[int] = []
        for i, vin in enumerate(vins):
            vid = (vin.get("txid"), vin.get("vout"))
            if vid in self.utxo_index:
                pnid = self.utxo_index[vid]
                pn = self.nodes[pnid]
                if pn.taint_sats > 0 and pn.terminal is None and pn.spent_in_tx is None:
                    input_taints[i] = pn.taint_sats
                    matched_parents.append(pnid)
                    parent_depths.append(pn.depth)

        if not matched_parents:
            # No tainted inputs — nothing to do (defensive)
            return

        if len(vins) >= self.cluster_threshold:
            for pnid in matched_parents:
                pn = self.nodes[pnid]
                pn.terminal = Terminal.CLUSTER_ABSORBED
                pn.spent_in_tx = spend_txid
                pn.spent_at_block = block_height
                pn.spent_at_time = block_time
                pn.cluster_input_count = len(vins)
            return

        # Mark parents as spent
        for pnid in matched_parents:
            pn = self.nodes[pnid]
            pn.spent_in_tx = spend_txid
            pn.spent_at_block = block_height
            pn.spent_at_time = block_time

        # Distribute taint under the configured convention. Capture fee taint
        # so total conservation is algorithmic rather than empirical.
        output_taints, fee_taint = distribute(vins, vouts, input_taints, self.convention)
        if fee_taint > 0:
            self.fee_taint_by_tx[spend_txid] = self.fee_taint_by_tx.get(spend_txid, 0) + fee_taint
            self.total_fee_taint_sats += fee_taint

        # Output depth: max(parent_depth) + 1
        child_depth = max(parent_depths) + 1
        for vout_idx, taint_amt in enumerate(output_taints):
            if taint_amt <= 0:
                continue
            vout = vouts[vout_idx]
            self._add_or_update_node(
                depth=child_depth,
                txid=spend_txid,
                vout=vout_idx,
                vout_data=vout,
                amount_sats=vout["value"],
                taint_to_add=taint_amt,
                block_height=block_height,
                block_time=block_time,
                parent_ids=matched_parents,
            )

    def _compute_dormancy(self):
        for n in self.nodes:
            if n.spent_at_time and n.block_time:
                n.dormancy_days = round((n.spent_at_time - n.block_time) / 86400, 2)

    def to_rows(self) -> list[dict]:
        rows = []
        for n in self.nodes:
            d = n.__dict__.copy()
            d["parents"] = ";".join(str(p) for p in n.parents) if n.parents else ""
            rows.append(d)
        return rows

    def summary(self) -> dict:
        by_terminal_sats: dict[str, int] = defaultdict(int)
        for n in self.nodes:
            if n.terminal:
                by_terminal_sats[n.terminal] += n.taint_sats
        if self.total_fee_taint_sats > 0:
            by_terminal_sats[Terminal.FEE_ABSORBED] += self.total_fee_taint_sats
        anchor_taint = self.nodes[0].taint_sats if self.nodes else 0
        n_addresses = len({n.address for n in self.nodes if n.address})
        n_unique_txs = len({n.txid for n in self.nodes})
        max_depth = max((n.depth for n in self.nodes), default=0)
        terminal_total = sum(by_terminal_sats.values())
        # Conservation holds for FIFO and haircut against the anchor taint;
        # poison is intentionally non-conservative (it inflates output taint
        # whenever a tainted tx has un-tainted inputs).
        conserves_anchor_taint = (
            self.convention != "poison" and terminal_total == anchor_taint
        )
        return {
            "convention": self.convention,
            "anchor_taint_sats": anchor_taint,
            "anchor_taint_btc": anchor_taint / SATOSHI,
            "n_nodes": len(self.nodes),
            "n_unique_addresses": n_addresses,
            "n_unique_txs_in_tree": n_unique_txs,
            "max_depth_reached": max_depth,
            "by_terminal_sats": dict(by_terminal_sats),
            "by_terminal_btc": {k: v / SATOSHI for k, v in by_terminal_sats.items()},
            "fee_taint_sats": self.total_fee_taint_sats,
            "fee_taint_btc": self.total_fee_taint_sats / SATOSHI,
            "terminal_attributed_taint_btc": terminal_total / SATOSHI,
            "conserves_anchor_taint": conserves_anchor_taint,
            "warnings": self.warnings,
            "explorer_stats": self.explorer.stats,
        }
