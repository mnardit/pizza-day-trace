# Codex Review v2: Verification Pass

Confirmed history: `git log --oneline` shows `24d16fb Apply codex review fixes + add depth-3 consolidation investigation` on top of `9ccd516 Initial commit: forensic UTXO trace of the Pizza Day transaction`.

Tests run: `.venv/bin/python -m pytest -q tests/` -> 13 passed.

## A. Prior CRITICAL Fix Verification

**FIXED** - Strict FIFO vs haircut. `src/tracer.py:47-89` now implements strict positional FIFO: each input is represented as a tainted prefix plus clean suffix, outputs consume inputs left-to-right, and tainted portions are consumed before clean portions inside each input. The prior worked case now comes out correctly: input value 10 with taint 3 and outputs `[5, 5]` produces `[3, 0]`. That exact fixture is in `tests/test_fifo.py:16-22`. The real consolidation split test also now expects 11,022 BTC with 10,000 BTC taint split into 5,500 BTC and 4,500 BTC of taint (`tests/test_fifo.py:65-73`), and the committed tree matches that (`data/processed/utxo-tree.csv:7-11`).

**FIXED, with one robustness caveat** - Topological order by `(block, position)`. `src/tracer.py:176-181` sorts pending spends by `(block_height, in-block tx position)`, `_collect_pending_spends` resolves the spending tx position before enqueueing (`src/tracer.py:221-228`), and `Explorer.tx_position_in_block` fetches block txids and returns `txids.index(txid)` (`src/explorer.py:130-139`). For a confirmed same-block parent/child where both spending txs are in the pending set, this is the right tiebreaker: the parent must appear earlier in the block, so it will process first. The caveat is discussed in section C: the fallback sentinel `10**9` can hide bad position resolution.

**FIXED** - Headline #4 reframe. The old "still alive / all still moving" claim is gone. `data/processed/headline-summary.json:202` now says the trace stops at the depth-5 horizon and points readers to `depth_horizon_frontier`. That block exists at `data/processed/headline-summary.json:91-125`, and all three frontier UTXOs are explicitly marked `spent-beyond-horizon`.

## B. Prior HIGH Fix Verification

**FIXED** - Pruning rules are now framed as trace-budget thresholds. `METHODOLOGY.md:28-36` says the pruning buckets are budget stops, not forensic conclusions, and specifically calls the depth cutoff a horizon. The cluster language is also corrected to "the spending transaction" as the boundary (`METHODOLOGY.md:32-34`).

**FIXED** - "Almost never mentioned" was softened. The fee headline now says "rarely foregrounded in the coverage surveyed in analysis/prior-art.md" (`data/processed/headline-summary.json:197`), which matches the scope of `analysis/prior-art.md`.

**FIXED** - "Smallest possible memorial" was softened. The 546-sat headline now says "Bitcoin Core relay default dust threshold for P2PKH" and "among the smallest deposits a standard wallet will broadcast" (`data/processed/headline-summary.json:204`). This is much closer, though still see section D for a wording caveat.

**MOSTLY FIXED** - "Tributes" -> "deposits". The output file is now `data/processed/jercos-deposits.csv`, README refers to deposits (`README.md:16`, `README.md:39`), and headline #7 uses "deposits" (`data/processed/headline-summary.json:203`). Some internal docstrings still say "tributes" and even name the old output path (`src/run_jercos.py:1-16`). That is not data-breaking, but it is polish debt.

**FIXED** - `processed_txs` blocking issue. There is no remaining `processed_txs` short-circuit in `src/tracer.py`. Parents are instead skipped once their specific UTXO has `spent_in_tx` set (`src/tracer.py:241-249`), which removes the old "tx processed too early forever" failure mode.

**HIGH** - Fee-taint loss is still only empirically absent on this dataset, not proven by the tracer. `fifo_distribute` still distributes taint only across explicit outputs (`src/tracer.py:69-89`). If strict FIFO places tainted sats into the implicit fee remainder, that taint disappears from the node graph rather than landing in a `fee` terminal bucket. The committed dataset conserves 10,000 BTC (`data/processed/summary.json:8-14`), but the code-level guarantee in `src/tracer.py:24-26` is too broad. Minimum fix: either add explicit fee-taint accounting or downgrade the invariant claim to "checked for this run".

**MOSTLY FIXED** - README/Makefile reproducibility. `Makefile:10-26` now encodes the full pipeline as `all: trace anchor jercos analyze`, and `README.md:25-31` documents `make setup`, `make all`, and `make test`. A clean clone can regenerate the artifacts if it has network access and the mempool.space API behavior remains compatible. It is not a pinned historical reproduction because `data/cache.sqlite` is gitignored and live address history can change.

**PARTIAL** - Reproducibility pinned to chain tip. `headline-summary.json` records `chain_tip_at_trace_time` (`data/processed/headline-summary.json:2`), and `run_analyze.py` obtains it from the current API (`src/run_analyze.py:111-157`). That distinguishes snapshots, but it does not pin the query. A future `make all` still fetches address histories as of the future tip, so the current snapshot is identified but not exactly reproducible from first principles.

## C. New Issues Introduced or Exposed

**HIGH** - The methodology overstates convention insensitivity. `README.md:21` and `METHODOLOGY.md:61-64` say poison or haircut change per-output numbers but not which transactions/UTXOs are tainted. That is false in general. Poison taint marks every output of a tainted transaction; strict FIFO can assign zero taint to later outputs; haircut can assign sub-1-BTC taint that this project would then prune. Under the repo's own pruning rules, alternative conventions can absolutely change the descendant topology visited by the trace. Safer wording: "The already-observed transaction graph is the same, but which outputs remain above the taint/pruning threshold can change."

**HIGH** - Fee-taint remains unmodelled as a terminal. This is the same residual risk from section B, but it is also an edge case in the new strict-FIFO implementation. If a transaction has input taint greater than total explicit output capacity reachable before the fee remainder, `fifo_distribute` drops the difference silently (`src/tracer.py:69-89`). Tests cover positive conservation cases (`tests/test_fifo.py:32-45`) but not fee loss.

**MEDIUM** - `tx_position_in_block` hides position lookup failures. If a txid is not in the block returned by `block_hash_at(block_height)`, `Explorer.tx_position_in_block` returns `10**9` (`src/explorer.py:130-139`). That keeps the run moving, but it converts a reorg/cache/API inconsistency into a late sort position. In the exact same-block bug this fix was meant to prevent, a hidden lookup failure can reintroduce wrong order. Prefer raising or recording a warning that fails tests for confirmed transactions.

**MEDIUM** - Same-block consolidation address history is misordered. `_consolidation_address_history` sorts lifetime txs only by block height (`src/run_analyze.py:59-60`). The committed JSON lists the same-block spend of 11,022 BTC before the same-block receive that created it (`data/processed/headline-summary.json:71-87`). A transaction cannot spend an output that appears later in the same block, so this history should sort by `(block_height, tx_position)`, using the same helper as the tracer.

**MEDIUM** - `_add_or_update_node` remains a recovery path with ambiguous depth semantics. The `taint_sats += taint_to_add` branch is still reachable if a tx is processed once with incomplete taint and later revisited after another parent becomes visible, for example because position lookup failed or an unconfirmed/mis-cached tx later resolved (`src/tracer.py:125-138`). Incremental taint addition is plausible under positional FIFO, but `n.depth = min(n.depth, depth)` can understate depth when the later parent is deeper. In a correctly ordered confirmed graph this path should be unreachable; if it is retained, it should warn or recompute depth from all parents.

**MEDIUM** - Tests do not cover the topological fix. The 13 tests cover FIFO examples and committed dataset invariants (`tests/test_fifo.py:16-89`, `tests/test_trace_invariants.py:16-47`), but there is no synthetic same-block parent/child fixture. They would catch some poison-taint regressions in `fifo_distribute` because the expected vectors are not poison-compatible, but they would not catch a tracer-level same-block ordering regression, the `10**9` fallback, or fee-taint loss.

**LOW** - Edge cases in `fifo_distribute` are not validated. Zero-value outputs are harmless because `need` stays zero, OP_RETURN and P2PK-without-address outputs are traced because value/script data is independent of address (`src/tracer.py:145-146`, `src/tracer.py:277-291`), and P2PK without address already appears in the tree (`data/processed/utxo-tree.csv:4`). But there is no assertion that `0 <= input_taint <= prevout.value`; malformed fixture data could create negative clean ranges (`src/tracer.py:63-67`).

**LOW** - Documentation still claims raw tx JSON and Blockchair cross-checks. `METHODOLOGY.md:49-53` says each tx is stored under `data/raw/tx/<txid>.json` and sampled against Blockchair. `Explorer` only stores HTTP bodies in SQLite (`src/explorer.py:38-75`), and no cross-check script exists.

## D. Findings Quality on the 8 Headlines

**1. Fee rarely foregrounded** - Supported, mostly restated, slightly interpretive. The 0.99 BTC fee is directly supported by `data/processed/headline-summary.json:8-9`. "Rarely foregrounded" is scoped to the prior-art survey, which is acceptable if the article keeps that scope visible.

**2. 111 0.01 BTC crumbs** - Supported and useful. The count is in `data/processed/headline-summary.json:10-11`. "Typical of consolidated mining residue" is plausible and softened by "not coinbase outputs directly", but it is still an inference rather than a chain fact.

**3. Largest input 3753.88 BTC, 5.2 days old** - Supported and likely novel relative to the prior-art survey. Backed by `data/processed/headline-summary.json:12-13`; keep it.

**4. 45-day dormancy before consolidation** - Partly supported, but over-claimed as written. The consolidation event is supported (`data/processed/headline-summary.json:31-41`). The problem is "Both pizza-output halves sat untouched for ~45 days" (`data/processed/headline-summary.json:200`): one depth-1 half moved after about 0.03 days (`data/processed/utxo-tree.csv:3-5`), and its successor then sat until July 7. Better: "The two FIFO-tainted branches that fed the July 7 consolidation had each been dormant for about 45 days by then." Also, "unrelated provenance" should be "non-pizza-tainted under this convention" unless independently analyzed.

**5. Consolidation address as one-off transit point** - Supported stats, over-claimed label. The 4 lifetime txs, May-July 2010 window, and zero balance are in `data/processed/headline-summary.json:43-50`. That supports "one-off transit address" and "not a long-lived hot wallet". It does not prove "not an exchange wallet"; a service can use short-lived addresses.

**6. Depth-5 frontier** - Supported and correctly reframed. `data/processed/headline-summary.json:91-125` shows all three frontier UTXOs are `spent-beyond-horizon`, and the headline at `data/processed/headline-summary.json:202` no longer treats the horizon as a terminal state. "Sits in 3 frontier UTXOs" is accurate as a trace-horizon statement, not a present-day balance statement.

**7. Recipient address funded 14 times, spent once** - Supported, mostly restated. `data/processed/headline-summary.json:126-143` and `data/processed/jercos-summary.json:2-11` support the address counts and unspent deposit total. "Some land on May-22 anniversaries" is supported by two rows (`data/processed/jercos-deposits.csv:8-9`) but should stay phrased as "some", not a strong pattern.

**8. Two 546-sat anniversary deposits** - Supported but still wording-sensitive. The rows are in `data/processed/jercos-deposits.csv:8-9`, and the headline correctly says "Bitcoin Core relay default dust threshold for P2PKH" (`data/processed/headline-summary.json:204`). "Among the smallest deposits a standard wallet will broadcast" is directionally fine, but "standard wallet" varies by script type, fee policy, and wallet behavior.

## E. Low-Cost Additional Analyses Opened by Fresh Data

**MEDIUM** - Add counterparties for the consolidation address's other three lifetime txs. `headline-summary.json` currently records only role, amount, and input/output counts (`data/processed/headline-summary.json:51-88`). Adding sender/receiver addresses and values would tell whether the 250 BTC round trip and the 11,022 BTC same-block spend connect to the same actor, a change address, or a broader wallet pattern.

**MEDIUM** - Explain the 250 BTC May 22 round trip. The address receives 250 BTC at 2010-05-22 19:13 and spends 250 BTC at 19:28 (`data/processed/headline-summary.json:52-69`). A tiny table of prevout/source, destination, fee, and whether either side touches Hanyecz-adjacent addresses would be cheap and narratively useful.

**LOW** - Add same-block position and fee columns to consolidation history. Because two July 7 txs share block/time, `(block_height, tx_position)` is needed for correct ordering. Including tx position would also align the headline data with the tracer's topological methodology.

## F. Final Verdict

The prior CRITICAL blockers are fixed, and the concept is now publishable in shape: the FIFO convention is real, the depth horizon is honestly framed, and the main headline set is much cleaner. I would not ship the repo/article yet without a small final pass.

Minimum must-fix before publication:

1. Add explicit fee-taint accounting or remove the code/doc claim that taint conservation is guaranteed generally (`src/tracer.py:24-26`, `src/tracer.py:69-89`).
2. Fix the methodology claim that poison/haircut do not change which outputs/transactions are tainted (`README.md:21`, `METHODOLOGY.md:61-64`).
3. Rewrite the 45-day headline so it describes the two FIFO-tainted branches that fed consolidation, not both original pizza-output halves sitting untouched (`data/processed/headline-summary.json:200`).
4. Sort consolidation address lifetime history by same-block position, not block height alone (`src/run_analyze.py:59-60`).

Updated verdict: ship-with-fixes.
